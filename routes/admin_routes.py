from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from database.db import query_db, execute_db
from middleware.auth import login_required, roles_required, get_current_user, log_audit

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
@roles_required('Admin')
def dashboard():
    user = get_current_user()

    total_users = query_db("SELECT COUNT(*) as cnt FROM users WHERE status = 'Active'", one=True)['cnt']
    hr_users_cnt = query_db("SELECT COUNT(*) as cnt FROM users WHERE role = 'HR' AND status = 'Active'", one=True)['cnt']
    total_depts = query_db("SELECT COUNT(*) as cnt FROM departments", one=True)['cnt']
    audit_logs_cnt = query_db("SELECT COUNT(*) as cnt FROM audit_logs", one=True)['cnt']

    recent_audits = query_db("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 10")
    hr_list = query_db("SELECT * FROM users WHERE role = 'HR' AND status = 'Active'")

    return render_template(
        'admin/dashboard.html',
        user=user,
        total_users=total_users,
        hr_users_cnt=hr_users_cnt,
        total_depts=total_depts,
        audit_logs_cnt=audit_logs_cnt,
        recent_audits=recent_audits,
        hr_list=hr_list
    )

@admin_bp.route('/employees', methods=['GET', 'POST'])
@login_required
@roles_required('Admin')
def employee_management():
    user = get_current_user()
    current_year = date.today().year

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create_employee':
            emp_id = request.form.get('emp_id', '').strip().upper()
            email = request.form.get('email', '').strip().lower()
            full_name = request.form.get('full_name', '').strip()
            password = request.form.get('password', '')
            role = request.form.get('role', 'Employee').strip()
            dept_id = request.form.get('department_id', type=int)
            designation = request.form.get('designation', '').strip()
            phone = request.form.get('phone', '').strip()

            existing = query_db("SELECT id FROM users WHERE emp_id = ? OR email = ?", (emp_id, email), one=True)
            if existing:
                flash("An account with this Employee ID or Email already exists.", 'danger')
            else:
                pass_hash = generate_password_hash(password)
                new_user_id = execute_db("""
                    INSERT INTO users (emp_id, email, password_hash, full_name, role, department_id, designation, phone, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active')
                """, (emp_id, email, pass_hash, full_name, role, dept_id, designation, phone))

                # Provision leave balances for current year
                leave_types = query_db("SELECT id, max_days_per_year FROM leave_types")
                for lt in leave_types:
                    max_days = float(lt['max_days_per_year'])
                    execute_db("""
                        INSERT INTO leave_balances (user_id, leave_type_id, year, total_allocated, used, pending, remaining)
                        VALUES (?, ?, ?, ?, 0.0, 0.0, ?)
                    """, (new_user_id, lt['id'], current_year, max_days, max_days))

                log_audit(user['id'], 'ADMIN_CREATE_EMPLOYEE', 'Admin', f"Admin created employee {emp_id} ({full_name}) with role {role}")
                flash(f"Employee account for {full_name} ({emp_id}) created successfully.", 'success')

        elif action == 'update_employee':
            user_id = request.form.get('user_id', type=int)
            full_name = request.form.get('full_name', '').strip()
            role = request.form.get('role', 'Employee').strip()
            dept_id = request.form.get('department_id', type=int)
            designation = request.form.get('designation', '').strip()
            phone = request.form.get('phone', '').strip()
            status = request.form.get('status', 'Active').strip()

            target = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
            if target and target['role'] != 'Admin':
                execute_db("""
                    UPDATE users
                    SET full_name = ?, role = ?, department_id = ?, designation = ?, phone = ?, status = ?
                    WHERE id = ?
                """, (full_name, role, dept_id, designation, phone, status, user_id))

                log_audit(user['id'], 'ADMIN_UPDATE_EMPLOYEE', 'Admin', f"Admin updated employee {target['emp_id']} ({full_name})")
                flash(f"Employee details updated for {full_name}.", 'success')

        elif action == 'toggle_status':
            user_id = request.form.get('user_id', type=int)
            target = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
            if target and target['role'] != 'Admin':
                new_status = 'Inactive' if target['status'] == 'Active' else 'Active'
                execute_db("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
                log_audit(user['id'], 'ADMIN_TOGGLE_STATUS', 'Admin', f"Changed status of user {target['emp_id']} to {new_status}")
                flash(f"Account for {target['full_name']} set to {new_status}.", 'info')

        elif action == 'reset_password':
            user_id = request.form.get('user_id', type=int)
            new_password = request.form.get('new_password', '').strip()
            target = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
            if target and len(new_password) >= 8:
                execute_db("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new_password), user_id))
                log_audit(user['id'], 'ADMIN_RESET_PASSWORD', 'Admin', f"Admin reset password for user {target['emp_id']} ({target['full_name']})")
                flash(f"Password reset successfully for {target['full_name']}.", 'success')

        elif action == 'delete_employee':
            user_id = request.form.get('user_id', type=int)
            target = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
            if not target:
                flash("Employee record not found.", 'danger')
            elif target['id'] == user['id']:
                flash("You cannot delete your own logged-in account.", 'danger')
            elif target['role'] == 'Admin':
                flash("Cannot delete Admin accounts.", 'danger')
            else:
                execute_db("DELETE FROM leave_requests WHERE user_id = ?", (user_id,))
                execute_db("DELETE FROM leave_balances WHERE user_id = ?", (user_id,))
                execute_db("DELETE FROM notifications WHERE user_id = ?", (user_id,))
                execute_db("DELETE FROM audit_logs WHERE user_id = ?", (user_id,))
                execute_db("DELETE FROM employee_verification WHERE UPPER(emp_id) = ? OR LOWER(company_email) = ?", (target['emp_id'].upper(), target['email'].lower()))
                execute_db("DELETE FROM users WHERE id = ?", (user_id,))
                log_audit(user['id'], 'ADMIN_DELETE_EMPLOYEE', 'Admin', f"Admin deleted employee {target['emp_id']} ({target['full_name']})")
                flash(f"Employee {target['full_name']} ({target['emp_id']}) has been permanently deleted.", 'success')

        return redirect(url_for('admin.employee_management'))

    # GET Query handling
    search = request.args.get('search', '').strip()
    dept_filter = request.args.get('dept_id', '', type=str)
    role_filter = request.args.get('role', '', type=str)
    status_filter = request.args.get('status', '', type=str)

    query = """
        SELECT u.*, d.name as dept_name
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        WHERE u.role != 'Admin'
    """
    args = []

    if search:
        query += " AND (u.full_name LIKE ? OR u.emp_id LIKE ? OR u.email LIKE ? OR u.designation LIKE ?)"
        args.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])

    if dept_filter.isdigit():
        query += " AND u.department_id = ?"
        args.append(int(dept_filter))

    if role_filter in ('Employee', 'HR'):
        query += " AND u.role = ?"
        args.append(role_filter)

    if status_filter in ('Active', 'Inactive'):
        query += " AND u.status = ?"
        args.append(status_filter)

    query += " ORDER BY u.id DESC"
    employees_list = query_db(query, tuple(args))
    departments = query_db("SELECT * FROM departments ORDER BY name ASC")

    return render_template(
        'admin/employees.html',
        user=user,
        employees=employees_list,
        departments=departments,
        current_search=search,
        current_dept=dept_filter,
        current_role=role_filter,
        current_status=status_filter
    )

@admin_bp.route('/hr-management', methods=['GET', 'POST'])
@login_required
@roles_required('Admin')
def hr_management():
    user = get_current_user()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create_hr':
            emp_id = request.form.get('emp_id', '').strip().upper()
            email = request.form.get('email', '').strip().lower()
            full_name = request.form.get('full_name', '').strip()
            password = request.form.get('password', '')

            existing = query_db("SELECT id FROM users WHERE emp_id = ? OR email = ?", (emp_id, email), one=True)
            if existing:
                flash("User with this Employee ID or Email already exists.", 'danger')
            else:
                pass_hash = generate_password_hash(password)
                hr_dept = query_db("SELECT id FROM departments WHERE code = 'HR'", one=True)
                dept_id = hr_dept['id'] if hr_dept else 1

                execute_db("""
                    INSERT INTO users (emp_id, email, password_hash, full_name, role, department_id, designation, status)
                    VALUES (?, ?, ?, ?, 'HR', ?, 'HR Executive', 'Active')
                """, (emp_id, email, pass_hash, full_name, dept_id))

                log_audit(user['id'], 'ADMIN_CREATE_HR', 'Admin', f"Admin created HR user {emp_id} ({full_name})")
                flash(f"HR Account for {full_name} created successfully.", 'success')

        elif action == 'toggle_hr_role':
            user_id = request.form.get('user_id', type=int)
            new_role = request.form.get('new_role', '').strip() # 'HR' or 'Employee'

            target = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
            if target and target['role'] != 'Admin':
                execute_db("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
                log_audit(user['id'], 'ADMIN_TOGGLE_ROLE', 'Admin', f"Changed role of user {target['emp_id']} to {new_role}")
                flash(f"Role for {target['full_name']} changed to {new_role}.", 'success')

    hr_users = query_db("SELECT u.*, d.name as dept_name FROM users u LEFT JOIN departments d ON u.department_id = d.id WHERE u.role = 'HR'")
    non_hr_users = query_db("SELECT id, emp_id, full_name, role FROM users WHERE role = 'Employee' AND status = 'Active'")

    return render_template('admin/hr_management.html', user=user, hr_users=hr_users, non_hr_users=non_hr_users)

@admin_bp.route('/departments', methods=['GET', 'POST'])
@login_required
@roles_required('Admin')
def departments():
    user = get_current_user()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            name = request.form.get('name', '').strip()
            code = request.form.get('code', '').strip().upper()
            min_staffing = request.form.get('min_staffing_percentage', type=float) or 50.0
            description = request.form.get('description', '').strip()

            execute_db("""
                INSERT INTO departments (name, code, min_staffing_percentage, description)
                VALUES (?, ?, ?, ?)
            """, (name, code, min_staffing, description))

            log_audit(user['id'], 'ADMIN_ADD_DEPT', 'Admin', f"Added department {name} ({code})")
            flash(f"Department '{name}' added successfully.", 'success')

        elif action == 'edit':
            dept_id = request.form.get('dept_id', type=int)
            name = request.form.get('name', '').strip()
            min_staffing = request.form.get('min_staffing_percentage', type=float) or 50.0
            description = request.form.get('description', '').strip()

            execute_db("""
                UPDATE departments 
                SET name = ?, min_staffing_percentage = ?, description = ?
                WHERE id = ?
            """, (name, min_staffing, description, dept_id))

            log_audit(user['id'], 'ADMIN_EDIT_DEPT', 'Admin', f"Updated department ID {dept_id}")
            flash("Department updated successfully.", 'success')

    dept_list = query_db("SELECT d.*, COUNT(u.id) as emp_count FROM departments d LEFT JOIN users u ON d.id = u.department_id GROUP BY d.id")
    return render_template('admin/departments.html', user=user, departments=dept_list)

@admin_bp.route('/policies', methods=['GET', 'POST'])
@login_required
@roles_required('Admin')
def policies():
    user = get_current_user()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_leave_type':
            lt_id = request.form.get('leave_type_id', type=int)
            max_days = request.form.get('max_days_per_year', type=int)
            requires_hr = 1 if request.form.get('requires_hr_approval') == '1' else 0
            notice = request.form.get('notice_period_days', type=int) or 0

            execute_db("""
                UPDATE leave_types 
                SET max_days_per_year = ?, requires_hr_approval = ?, notice_period_days = ?
                WHERE id = ?
            """, (max_days, requires_hr, notice, lt_id))

            log_audit(user['id'], 'ADMIN_UPDATE_LEAVE_TYPE', 'Admin', f"Updated leave type ID {lt_id}")
            flash("Leave type policy updated successfully.", 'success')

        elif action == 'toggle_rule':
            rule_id = request.form.get('rule_id', type=int)
            is_enabled = request.form.get('is_enabled', type=int)

            execute_db("UPDATE leave_rules SET is_enabled = ? WHERE id = ?", (is_enabled, rule_id))
            log_audit(user['id'], 'ADMIN_TOGGLE_RULE', 'Admin', f"Set rule ID {rule_id} enabled status to {is_enabled}")
            flash("Auto-approval rule status updated.", 'success')

    leave_types = query_db("SELECT * FROM leave_types ORDER BY id ASC")
    leave_rules = query_db("SELECT r.*, lt.name as leave_type_name FROM leave_rules r LEFT JOIN leave_types lt ON r.leave_type_id = lt.id")

    return render_template('admin/policies.html', user=user, leave_types=leave_types, leave_rules=leave_rules)

@admin_bp.route('/holidays', methods=['GET', 'POST'])
@login_required
@roles_required('Admin')
def holidays():
    user = get_current_user()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            title = request.form.get('title', '').strip()
            h_date = request.form.get('holiday_date', '').strip()
            day_of_week = request.form.get('day_of_week', '').strip()
            htype = request.form.get('type', 'National')
            desc = request.form.get('description', '').strip()

            try:
                execute_db("""
                    INSERT INTO holidays (title, holiday_date, day_of_week, type, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (title, h_date, day_of_week, htype, desc))

                log_audit(user['id'], 'ADMIN_ADD_HOLIDAY', 'Admin', f"Added holiday {title} on {h_date}")
                flash(f"Holiday '{title}' added successfully.", 'success')
            except Exception as e:
                flash(f"Error adding holiday: {e}", 'danger')

        elif action == 'delete':
            h_id = request.form.get('holiday_id', type=int)
            execute_db("DELETE FROM holidays WHERE id = ?", (h_id,))
            log_audit(user['id'], 'ADMIN_DELETE_HOLIDAY', 'Admin', f"Deleted holiday ID {h_id}")
            flash("Holiday removed.", 'success')

    holiday_list = query_db("SELECT * FROM holidays ORDER BY holiday_date ASC")
    return render_template('admin/holidays.html', user=user, holidays=holiday_list)

@admin_bp.route('/audit-logs')
@login_required
@roles_required('Admin')
def audit_logs():
    user = get_current_user()
    search = request.args.get('search', '').strip()

    query = "SELECT * FROM audit_logs"
    args = []

    if search:
        query += " WHERE user_name LIKE ? OR action LIKE ? OR module LIKE ? OR details LIKE ?"
        args.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])

    query += " ORDER BY id DESC LIMIT 200"
    logs = query_db(query, tuple(args))

    return render_template('admin/audit_logs.html', user=user, logs=logs, current_search=search)

@admin_bp.route('/reset-user-password', methods=['POST'])
@login_required
@roles_required('Admin')
def reset_user_password():
    user = get_current_user()
    target_user_id = request.form.get('user_id', type=int)
    new_password = request.form.get('new_password', '').strip()

    if len(new_password) < 8:
        flash("Password must be at least 8 characters long.", 'danger')
        return redirect(request.referrer or url_for('admin.dashboard'))

    target = query_db("SELECT * FROM users WHERE id = ?", (target_user_id,), one=True)
    if target:
        execute_db("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new_password), target_user_id))
        log_audit(user['id'], 'ADMIN_RESET_PASSWORD', 'Admin', f"Admin reset password for user {target['emp_id']} ({target['full_name']})")
        flash(f"Password reset successfully for {target['full_name']}.", 'success')

    return redirect(request.referrer or url_for('admin.dashboard'))

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@roles_required('Admin')
def settings():
    user = get_current_user()

    if request.method == 'POST':
        for key in request.form:
            if key != 'csrf_token':
                val = request.form.get(key)
                execute_db("UPDATE company_settings SET setting_value = ? WHERE setting_key = ?", (val, key))

        log_audit(user['id'], 'ADMIN_UPDATE_SETTINGS', 'Admin', "Updated system company settings")
        flash("Company settings saved successfully.", 'success')

    settings_rows = query_db("SELECT * FROM company_settings")
    return render_template('admin/settings.html', user=user, settings=settings_rows)
