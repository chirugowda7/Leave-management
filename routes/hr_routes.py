import os
import uuid
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from database.db import query_db, execute_db
from middleware.auth import login_required, roles_required, get_current_user, log_audit
from services.leave_service import process_hr_approval
from services.report_service import generate_excel_leave_report, generate_pdf_leave_report
from services.id_card_service import generate_id_card_image

hr_bp = Blueprint('hr', __name__, url_prefix='/hr')

@hr_bp.route('/dashboard')
@login_required
@roles_required('HR', 'Admin')
def dashboard():
    user = get_current_user()

    # Total stats
    total_employees = query_db("SELECT COUNT(*) as cnt FROM users WHERE status = 'Active'", one=True)['cnt']
    pending_hr_approvals_cnt = query_db("SELECT COUNT(*) as cnt FROM leave_requests WHERE status IN ('Pending HR', 'Escalated')", one=True)['cnt']
    active_departments_cnt = query_db("SELECT COUNT(*) as cnt FROM departments", one=True)['cnt']

    # Escalated / Special Leave Requests queue
    pending_requests = query_db("""
        SELECT lr.*, u.full_name as applicant_name, u.emp_id, d.name as dept_name,
               lt.name as leave_type_name, lt.code as leave_type_code
        FROM leave_requests lr
        JOIN users u ON lr.user_id = u.id
        LEFT JOIN departments d ON u.department_id = d.id
        JOIN leave_types lt ON lr.leave_type_id = lt.id
        WHERE lr.status IN ('Pending HR', 'Escalated')
        ORDER BY lr.id ASC
    """, ())

    # Recent HR actions / Transfers
    recent_leaves = query_db("""
        SELECT lr.*, u.full_name as applicant_name, lt.code as leave_type_code
        FROM leave_requests lr
        JOIN users u ON lr.user_id = u.id
        JOIN leave_types lt ON lr.leave_type_id = lt.id
        ORDER BY lr.id DESC LIMIT 5
    """, ())

    return render_template(
        'hr/dashboard.html',
        user=user,
        total_employees=total_employees,
        pending_hr_approvals_cnt=pending_hr_approvals_cnt,
        active_departments_cnt=active_departments_cnt,
        pending_requests=pending_requests,
        recent_leaves=recent_leaves
    )

@hr_bp.route('/approvals')
@login_required
@roles_required('HR', 'Admin')
def pending_approvals():
    user = get_current_user()

    pending_list = query_db("""
        SELECT lr.*, u.full_name as applicant_name, u.emp_id, d.name as dept_name,
               lt.name as leave_type_name, lt.code as leave_type_code
        FROM leave_requests lr
        JOIN users u ON lr.user_id = u.id
        LEFT JOIN departments d ON u.department_id = d.id
        JOIN leave_types lt ON lr.leave_type_id = lt.id
        WHERE lr.status IN ('Pending HR', 'Escalated')
        ORDER BY lr.id ASC
    """, ())

    return render_template('hr/approvals.html', user=user, requests=pending_list)

@hr_bp.route('/action/<int:request_id>', methods=['POST'])
@login_required
@roles_required('HR', 'Admin')
def handle_action(request_id):
    user = get_current_user()
    action = request.form.get('action', '').strip() # approve, reject
    comment = request.form.get('comment', '').strip()

    if not comment:
        comment = f"Processed by HR ({action.capitalize()})"

    success, msg = process_hr_approval(request_id, user['id'], action, comment)

    if success:
        log_audit(user['id'], f'HR_{action.upper()}', 'HR', f"HR performed '{action}' on leave request ID {request_id}. Comment: {comment}")
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    return redirect(url_for('hr.pending_approvals'))

@hr_bp.route('/employees')
@login_required
@roles_required('HR', 'Admin')
def employee_management():
    user = get_current_user()
    search = request.args.get('search', '').strip()
    dept_filter = request.args.get('dept_id', '', type=str)

    query = """
        SELECT u.*, d.name as dept_name
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        WHERE u.role = 'Employee'
    """
    args = []

    if search:
        query += " AND (u.full_name LIKE ? OR u.emp_id LIKE ? OR u.email LIKE ?)"
        args.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    if dept_filter.isdigit():
        query += " AND u.department_id = ?"
        args.append(int(dept_filter))

    query += " ORDER BY u.id DESC"
    employees_list = query_db(query, tuple(args))

    departments = query_db("SELECT * FROM departments ORDER BY name ASC")

    return render_template(
        'hr/employees.html',
        user=user,
        employees=employees_list,
        departments=departments,
        current_search=search,
        current_dept=dept_filter
    )

@hr_bp.route('/update-employee/<int:emp_user_id>', methods=['POST'])
@login_required
@roles_required('HR', 'Admin')
def update_employee(emp_user_id):
    user = get_current_user()
    new_role = request.form.get('role', 'Employee').strip()
    new_dept_id = request.form.get('department_id', type=int)
    designation = request.form.get('designation', '').strip()
    phone = request.form.get('phone', '').strip()
    blood_group = request.form.get('blood_group', '').strip()
    address = request.form.get('address', '').strip()

    target = query_db("SELECT * FROM users WHERE id = ?", (emp_user_id,), one=True)
    if not target or target['role'] in ('Admin', 'HR'):
        flash("Cannot modify Admin or HR user designations from this panel.", 'danger')
        return redirect(url_for('hr.employee_management'))

    execute_db("""
        UPDATE users 
        SET role = ?, department_id = ?, designation = ?, phone = ?, blood_group = ?, address = ?
        WHERE id = ?
    """, (new_role, new_dept_id, designation, phone, blood_group, address, emp_user_id))

    log_audit(
        user['id'],
        'HR_EMP_UPDATE',
        'HR',
        f"HR updated user {target['emp_id']} ({target['full_name']}): Role={new_role}, DeptID={new_dept_id}"
    )

    send_notification(
        emp_user_id,
        "Profile & Designation Updated by HR",
        f"Your role/department/profile details have been updated by HR.",
        "info"
    )

    flash(f"Successfully updated records for {target['full_name']}.", 'success')
    return redirect(url_for('hr.employee_management'))

@hr_bp.route('/id-card/<int:emp_user_id>')
@login_required
@roles_required('HR', 'Admin')
def generate_id_card(emp_user_id):
    user = get_current_user()
    emp = query_db("""
        SELECT u.*, d.name as dept_name
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        WHERE u.id = ?
    """, (emp_user_id,), one=True)

    if not emp:
        flash("Employee record not found.", "danger")
        return redirect(url_for('hr.employee_management'))

    return render_template(
        'hr/id_card.html',
        user=user,
        emp=emp
    )

@hr_bp.route('/id-card-image/<int:emp_user_id>/<string:side>')
@login_required
@roles_required('HR', 'Admin')
def render_id_card_image_route(emp_user_id, side):
    emp = query_db("SELECT * FROM users WHERE id = ?", (emp_user_id,), one=True)
    if not emp:
        return "Employee not found", 404

    img_buf = generate_id_card_image(emp, side=side)
    return send_file(img_buf, mimetype='image/jpeg')

@hr_bp.route('/id-card/update/<int:emp_user_id>', methods=['POST'])
@login_required
@roles_required('HR', 'Admin')
def update_id_card_details(emp_user_id):
    user = get_current_user()
    emp = query_db("SELECT * FROM users WHERE id = ?", (emp_user_id,), one=True)
    if not emp:
        flash("Employee record not found.", "danger")
        return redirect(url_for('hr.employee_management'))

    full_name = request.form.get('full_name', '').strip()
    emp_id = request.form.get('emp_id', '').strip().upper()
    blood_group = request.form.get('blood_group', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()

    if not full_name or not emp_id or not email:
        flash("Full Name, Employee ID, and Email are required fields.", "danger")
        return redirect(url_for('hr.generate_id_card', emp_user_id=emp_user_id))

    # Duplicate Employee ID check
    if emp_id != emp['emp_id']:
        dup = query_db("SELECT id FROM users WHERE emp_id = ? AND id != ?", (emp_id, emp_user_id), one=True)
        if dup:
            flash(f"Employee ID '{emp_id}' is already assigned to another employee.", "danger")
            return redirect(url_for('hr.generate_id_card', emp_user_id=emp_user_id))

    # Duplicate Email check
    if email != emp['email']:
        dup = query_db("SELECT id FROM users WHERE email = ? AND id != ?", (email, emp_user_id), one=True)
        if dup:
            flash(f"Email '{email}' is already registered to another user.", "danger")
            return redirect(url_for('hr.generate_id_card', emp_user_id=emp_user_id))

    # Profile picture file upload
    filename = emp['profile_pic']
    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file and file.filename != '':
            ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            if ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
                unique_name = f"user_{emp_user_id}_{uuid.uuid4().hex[:8]}.{ext}"
                upload_folder = os.path.join(current_app.static_folder, 'uploads', 'profile_pics')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, unique_name))
                filename = unique_name
            else:
                flash("Invalid image format. Allowed formats: PNG, JPG, JPEG, GIF, WEBP.", "danger")
                return redirect(url_for('hr.generate_id_card', emp_user_id=emp_user_id))

    execute_db("""
        UPDATE users 
        SET full_name = ?, emp_id = ?, blood_group = ?, email = ?, phone = ?, address = ?, profile_pic = ?
        WHERE id = ?
    """, (full_name, emp_id, blood_group, email, phone, address, filename, emp_user_id))

    log_audit(user['id'], 'UPDATE_ID_CARD', 'HR', f"Updated ID Card details for {full_name} ({emp_id})")
    flash(f"ID Card details for {full_name} updated successfully!", "success")

    return redirect(url_for('hr.generate_id_card', emp_user_id=emp_user_id))

@hr_bp.route('/delete-employee/<int:emp_user_id>', methods=['POST'])
@login_required
@roles_required('HR', 'Admin')
def delete_employee(emp_user_id):
    user = get_current_user()
    target = query_db("SELECT * FROM users WHERE id = ?", (emp_user_id,), one=True)
    if not target:
        flash("Employee record not found.", 'danger')
        return redirect(url_for('hr.employee_management'))

    if target['id'] == user['id']:
        flash("You cannot delete your own logged-in account.", 'danger')
        return redirect(url_for('hr.employee_management'))

    if target['role'] in ('Admin', 'HR'):
        flash("Cannot delete Admin or HR accounts from this panel.", 'danger')
        return redirect(url_for('hr.employee_management'))

    execute_db("DELETE FROM leave_requests WHERE user_id = ?", (emp_user_id,))
    execute_db("DELETE FROM leave_balances WHERE user_id = ?", (emp_user_id,))
    execute_db("DELETE FROM notifications WHERE user_id = ?", (emp_user_id,))
    execute_db("DELETE FROM audit_logs WHERE user_id = ?", (emp_user_id,))
    execute_db("DELETE FROM employee_verification WHERE UPPER(emp_id) = ? OR LOWER(company_email) = ?", (target['emp_id'].upper(), target['email'].lower()))
    execute_db("DELETE FROM users WHERE id = ?", (emp_user_id,))

    log_audit(user['id'], 'HR_DELETE_EMPLOYEE', 'HR', f"HR deleted employee {target['emp_id']} ({target['full_name']})")
    flash(f"Employee {target['full_name']} ({target['emp_id']}) deleted successfully.", 'success')

    return redirect(url_for('hr.employee_management'))

@hr_bp.route('/balances', methods=['GET', 'POST'])
@login_required
@roles_required('HR', 'Admin')
def leave_balances():
    user = get_current_user()
    current_year = date.today().year

    if request.method == 'POST':
        target_user_id = request.form.get('user_id', type=int)
        leave_type_id = request.form.get('leave_type_id', type=int)
        new_allocated = request.form.get('total_allocated', type=float)

        bal = query_db("SELECT * FROM leave_balances WHERE user_id = ? AND leave_type_id = ? AND year = ?",
                       (target_user_id, leave_type_id, current_year), one=True)
        if bal:
            new_remaining = new_allocated - bal['used']
            execute_db("""
                UPDATE leave_balances 
                SET total_allocated = ?, remaining = ?
                WHERE id = ?
            """, (new_allocated, new_remaining, bal['id']))

            log_audit(user['id'], 'HR_BALANCE_ADJUST', 'HR', f"HR adjusted balance for User ID {target_user_id}, LT {leave_type_id} to {new_allocated} days")
            flash("Leave balance updated successfully.", 'success')

    users_list = query_db("SELECT id, full_name, emp_id FROM users WHERE status = 'Active' ORDER BY full_name ASC")
    leave_types = query_db("SELECT * FROM leave_types")

    selected_user_id = request.args.get('user_id', type=int)
    balances_data = []
    if selected_user_id:
        balances_data = query_db("""
            SELECT lb.*, lt.name as leave_type_name, lt.code as leave_type_code
            FROM leave_balances lb
            JOIN leave_types lt ON lb.leave_type_id = lt.id
            WHERE lb.user_id = ? AND lb.year = ?
        """, (selected_user_id, current_year))

    return render_template('hr/balances.html', user=user, users=users_list, leave_types=leave_types, selected_user_id=selected_user_id, balances=balances_data)

@hr_bp.route('/reports')
@login_required
@roles_required('HR', 'Admin')
def reports():
    user = get_current_user()
    departments = query_db("SELECT * FROM departments ORDER BY name ASC")
    return render_template('hr/reports.html', user=user, departments=departments)

@hr_bp.route('/reports/export/<fmt>')
@login_required
@roles_required('HR', 'Admin')
def export_report(fmt):
    dept_id = request.args.get('department_id', type=int)
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    if fmt == 'excel':
        excel_buf = generate_excel_leave_report(dept_id, start_date, end_date)
        return send_file(
            excel_buf,
            download_name=f"Leave_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    elif fmt == 'pdf':
        pdf_buf = generate_pdf_leave_report(dept_id, start_date, end_date)
        return send_file(
            pdf_buf,
            download_name=f"Leave_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            as_attachment=True,
            mimetype="application/pdf"
        )
    else:
        flash("Invalid report format requested.", 'danger')
        return redirect(url_for('hr.reports'))
