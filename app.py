import os
from datetime import date
from flask import Flask, redirect, url_for, session, g
from config import Config
from database.seed import seed_database
from database.db import query_db
from middleware.auth import get_current_user

# Blueprints
from routes.auth_routes import auth_bp, redirect_by_role
from routes.employee_routes import emp_bp
from routes.hr_routes import hr_bp
from routes.admin_routes import admin_bp
from routes.api_routes import api_bp

app = Flask(__name__)
app.config.from_object(Config)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(emp_bp)
app.register_blueprint(hr_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

@app.context_processor
def inject_global_template_vars():
    user = get_current_user()
    unread_count = 0
    if user:
        res = query_db("SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND is_read = 0", (user['id'],), one=True)
        if res:
            unread_count = res['count']

    return {
        'user': user,
        'unread_count': unread_count,
        'str': str,
        'min_date': date.today().strftime('%Y-%m-%d')
    }

@app.route('/')
def index():
    if 'user_id' in session:
        user = get_current_user()
        if user:
            return redirect_by_role(user['role'])
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    # Ensure Database exists and is seeded
    seed_database()
    
    print("\n" + "="*70)
    print("Smart Role-Based Enterprise Leave Management System (HRMS)")
    print("==============================================================")
    print("Pre-configured Demo Login Credentials:")
    print(" - Admin User:       ADM001 / Password123! (System Settings & HR creation)")
    print(" - HR Manager:       HR001  / Password123! (Designations, Transfers & Approvals)")
    print(" - Employee 1:       EMP001 / Password123! (Self Service & Applications)")
    print("==============================================================\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
