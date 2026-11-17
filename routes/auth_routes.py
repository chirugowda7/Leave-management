import os
import uuid
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, current_app, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database.db import query_db, execute_db
from middleware.auth import login_required, get_current_user, log_audit
from services.notification_service import notify_role, send_notification

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
ALLOWED_DOC_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_doc_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_DOC_EXTENSIONS

def generate_next_emp_id():
    user_ids = query_db("SELECT emp_id FROM users")
    verif_ids = query_db("SELECT emp_id FROM employee_verification")
    all_ids = [r['emp_id'] for r in user_ids if r['emp_id']] + [r['emp_id'] for r in verif_ids if r['emp_id']]
    
    nums = []
    for emp_id in all_ids:
        match = re.search(r'EMP(\d+)', emp_id, re.IGNORECASE)
        if match:
            nums.append(int(match.group(1)))
            
    next_num = (max(nums) + 1) if nums else 1
    return f"EMP{next_num:03d}"

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/generate-emp-id', methods=['GET'])
def generate_emp_id_route():
    email = request.args.get('email', '').strip().lower()
    dob = request.args.get('dob', '').strip()
    
    if email and dob:
        verif = query_db("""
            SELECT emp_id FROM employee_verification 
            WHERE LOWER(company_email) = ? AND dob = ? AND is_registered = 0
        """, (email, dob), one=True)
        if verif and verif['emp_id']:
            return jsonify({'emp_id': verif['emp_id']})
            
    return jsonify({'emp_id': generate_next_emp_id()})

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        user = get_current_user()
        if user:
            return redirect_by_role(user['role'])

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip() # emp_id or email
        password = request.form.get('password', '')

        user = query_db("""
            SELECT * FROM users 
            WHERE (emp_id = ? OR email = ?) AND status = 'Active'
        """, (identifier, identifier), one=True)

        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['user_role'] = user['role']
            session['user_name'] = user['full_name']

            log_audit(user['id'], 'LOGIN_SUCCESS', 'Auth', f"User {user['emp_id']} logged in successfully")
            flash(f"Welcome back, {user['full_name']}!", 'success')

            return redirect_by_role(user['role'])
        else:
            log_audit(None, 'LOGIN_FAILED', 'Auth', f"Failed login attempt for identifier: {identifier}")
            flash('Invalid Employee ID/Email or Password. Please try again.', 'danger')

    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Self-Registration Automation:
    Automatically generates Employee ID upon uploading required verification document.
    Verifies & maps employee data, provisioning account & leave balances automatically.
    """
    if request.method == 'POST':
        emp_id = request.form.get('emp_id', '').strip().upper()
        email = request.form.get('email', '').strip().lower()
        dob = request.form.get('dob', '').strip()
        full_name_input = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        phone = request.form.get('phone', '').strip()

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('auth/register.html')

        # Handle required document upload
        uploaded_doc = request.files.get('required_doc')
        doc_filename = None
        if uploaded_doc and uploaded_doc.filename:
            if allowed_doc_file(uploaded_doc.filename):
                filename = secure_filename(uploaded_doc.filename)
                unique_prefix = uuid.uuid4().hex[:8]
                doc_filename = f"doc_{unique_prefix}_{filename}"
                doc_dir = os.path.join(current_app.static_folder, 'uploads', 'documents')
                os.makedirs(doc_dir, exist_ok=True)
                uploaded_doc.save(os.path.join(doc_dir, doc_filename))
            else:
                flash('Invalid document type. Allowed types: PDF, PNG, JPG, JPEG, DOC, DOCX, WEBP.', 'danger')
                return render_template('auth/register.html')

        # Check if email is already registered in users table
        existing_email = query_db("SELECT id FROM users WHERE email = ?", (email,), one=True)
        if existing_email:
            flash('An account with this Email already exists. Please log in.', 'warning')
            return redirect(url_for('auth.login'))

        # Verify against employee_verification table
        verif = query_db("""
            SELECT * FROM employee_verification 
            WHERE LOWER(company_email) = ? AND dob = ?
        """, (email, dob), one=True)

        if verif:
            if verif['is_registered'] == 1:
                flash('This employee record has already been registered. Please log in or use Forgot Password.', 'info')
                return redirect(url_for('auth.login'))
            emp_id = verif['emp_id']
            full_name = verif['full_name']
            dept_id = verif['department_id']
            designation = verif['designation']
            execute_db("UPDATE employee_verification SET is_registered = 1, verification_doc = ? WHERE id = ?", (doc_filename, verif['id']))
        else:
            # Dynamic generation if no pre-seeded verification record
            if not emp_id:
                emp_id = generate_next_emp_id()
            full_name = full_name_input or email.split('@')[0].replace('.', ' ').title()
            dept = query_db("SELECT id FROM departments ORDER BY id ASC LIMIT 1", one=True)
            dept_id = dept['id'] if dept else 1
            designation = 'Software Engineer'

            execute_db("""
                INSERT INTO employee_verification (
                    emp_id, company_email, dob, full_name, department_id, designation, verification_doc, is_registered
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (emp_id, email, dob, full_name, dept_id, designation, doc_filename))

        # Check if emp_id exists in users table
        existing_emp_id = query_db("SELECT id FROM users WHERE emp_id = ?", (emp_id,), one=True)
        if existing_emp_id:
            emp_id = generate_next_emp_id()

        # Provision user account
        password_hash = generate_password_hash(password)
        new_user_id = execute_db("""
            INSERT INTO users (
                emp_id, email, password_hash, full_name, dob, role,
                department_id, designation, phone, status, verification_doc
            ) VALUES (?, ?, ?, ?, ?, 'Employee', ?, ?, ?, 'Active', ?)
        """, (
            emp_id, email, password_hash, full_name,
            dob, dept_id, designation, phone, doc_filename
        ))

        # Provision initial leave balances for current year
        current_year = 2026
        leave_types = query_db("SELECT id, max_days_per_year FROM leave_types")
        for lt in leave_types:
            max_days = float(lt['max_days_per_year'])
            execute_db("""
                INSERT INTO leave_balances (user_id, leave_type_id, year, total_allocated, used, pending, remaining)
                VALUES (?, ?, ?, ?, 0.0, 0.0, ?)
            """, (new_user_id, lt['id'], current_year, max_days, max_days))

        # Audit Log & HR Notification
        log_audit(new_user_id, 'REGISTER_SELF', 'Auth', f"Employee {emp_id} ({full_name}) self-registered with uploaded verification document")
        notify_role('HR', "New Employee Self-Registered", f"New employee {full_name} ({emp_id}) registered with document upload and was assigned to department.", "info")

        flash(f'Registration Successful! Official Employee ID {emp_id} assigned automatically. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        emp_id = request.form.get('emp_id', '').strip().upper()

        user = query_db("SELECT * FROM users WHERE email = ? AND emp_id = ?", (email, emp_id), one=True)
        if user:
            # Simulate password reset token generation
            flash(f"Password reset instructions have been generated for {user['full_name']}. You may now reset your password.", 'success')
            return redirect(url_for('auth.reset_password', user_id=user['id']))
        else:
            flash('No active account found with the matching Email and Employee ID.', 'danger')

    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    user_id = request.args.get('user_id') or request.form.get('user_id')
    if not user_id:
        flash('Invalid password reset link.', 'danger')
        return redirect(url_for('auth.login'))

    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        new_pass = request.form.get('password', '')
        confirm_pass = request.form.get('confirm_password', '')

        if new_pass != confirm_pass:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', user=user)

        if len(new_pass) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('auth/reset_password.html', user=user)

        execute_db("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new_pass), user_id))
        log_audit(user_id, 'PASSWORD_RESET', 'Auth', f"User {user['emp_id']} reset their password")
        flash('Your password has been successfully reset. Please log in with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', user=user)

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = get_current_user()
    if request.method == 'POST':
        action = request.form.get('action', '')
        
        if action == 'remove_pic':
            execute_db("UPDATE users SET profile_pic = NULL WHERE id = ?", (user['id'],))
            g.current_user = None
            flash('Profile picture removed.', 'info')
            return redirect(url_for('auth.profile'))

        phone = request.form.get('phone', '').strip()
        blood_group = request.form.get('blood_group', '').strip()
        address = request.form.get('address', '').strip()
        current_pass = request.form.get('current_password', '')
        new_pass = request.form.get('new_password', '')

        # Profile picture file upload
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = f"user_{user['id']}_{uuid.uuid4().hex[:8]}.{ext}"
                    upload_folder = os.path.join(current_app.static_folder, 'uploads', 'profile_pics')
                    os.makedirs(upload_folder, exist_ok=True)
                    file_path = os.path.join(upload_folder, filename)
                    file.save(file_path)
                    execute_db("UPDATE users SET profile_pic = ? WHERE id = ?", (filename, user['id']))
                    g.current_user = None
                else:
                    flash('Invalid image format. Allowed formats: PNG, JPG, JPEG, GIF, WEBP, SVG.', 'danger')

        execute_db("UPDATE users SET phone = ?, blood_group = ?, address = ? WHERE id = ?", (phone, blood_group, address, user['id']))

        if current_pass and new_pass:
            if not check_password_hash(user['password_hash'], current_pass):
                flash('Incorrect current password.', 'danger')
                return render_template('auth/profile.html', user=get_current_user())
            if len(new_pass) < 8:
                flash('New password must be at least 8 characters.', 'danger')
                return render_template('auth/profile.html', user=get_current_user())
            execute_db("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new_pass), user['id']))
            flash('Profile details and password updated successfully.', 'success')
        else:
            flash('Profile details updated successfully.', 'success')

        log_audit(user['id'], 'PROFILE_UPDATE', 'Auth', f"User {user['emp_id']} updated profile details")
        g.current_user = None
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html', user=user)

@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        log_audit(user_id, 'LOGOUT', 'Auth', 'User logged out')
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/unauthorized')
def unauthorized():
    return render_template('auth/unauthorized.html'), 403

def redirect_by_role(role):
    if role == 'Admin':
        return redirect(url_for('admin.dashboard'))
    elif role == 'HR':
        return redirect(url_for('hr.dashboard'))
    else:
        return redirect(url_for('employee.dashboard'))
