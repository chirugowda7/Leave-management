from functools import wraps
from flask import session, redirect, url_for, flash, request, abort, g
from database.db import query_db, execute_db

def get_current_user():
    if 'user_id' not in session:
        return None
    if not hasattr(g, 'current_user') or g.current_user is None:
        user = query_db("""
            SELECT u.*, d.name as department_name, d.code as department_code
            FROM users u
            LEFT JOIN departments d ON u.department_id = d.id
            WHERE u.id = ? AND u.status = 'Active'
        """, (session['user_id'],), one=True)
        g.current_user = user
    return g.current_user

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        user = get_current_user()
        if not user:
            session.clear()
            flash('Your account is inactive or session is invalid.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            user = get_current_user()
            if not user or user['role'] not in roles:
                log_audit(
                    session.get('user_id'),
                    'UNAUTHORIZED_ACCESS',
                    'Security',
                    f"User attempted to access endpoint requiring roles {roles}. Current role: {user['role'] if user else 'None'}"
                )
                flash('Access Denied: You do not have permission to perform this action.', 'danger')
                return redirect(url_for('auth.unauthorized'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_audit(user_id, action, module, details):
    try:
        user_name = 'System'
        role = 'System'
        if user_id:
            user = query_db("SELECT full_name, role FROM users WHERE id = ?", (user_id,), one=True)
            if user:
                user_name = user['full_name']
                role = user['role']
        
        ip_addr = request.remote_addr if request else '127.0.0.1'
        execute_db("""
            INSERT INTO audit_logs (user_id, user_name, role, action, module, details, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, user_name, role, action, module, details, ip_addr))
    except Exception as e:
        print(f"Error logging audit: {e}")
