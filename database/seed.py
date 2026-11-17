import os
import sys
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import init_db, get_db_connection, execute_db, query_db

def seed_database():
    print("Initializing Database Schema...")
    init_db()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if already seeded
    existing_users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing_users > 0:
        print("Database already contains data. Skipping re-seed.")
        conn.close()
        return

    print("Seeding Departments...")
    departments = [
        ('Engineering', 'ENG', 50.0, 'Software Development, Quality Assurance, and Infrastructure'),
        ('Human Resources', 'HR', 50.0, 'Talent Acquisition, People Operations, and Compliance'),
        ('Sales & Marketing', 'SALES', 40.0, 'Business Development, Marketing, and Client Relations'),
        ('Finance', 'FIN', 60.0, 'Accounting, Financial Planning, and Payroll'),
        ('Operations', 'OPS', 50.0, 'Facilities, IT Helpdesk, and Logistics')
    ]
    cur.executemany("""
        INSERT INTO departments (name, code, min_staffing_percentage, description)
        VALUES (?, ?, ?, ?)
    """, departments)
    conn.commit()

    # Get department IDs
    cur.execute("SELECT id, code FROM departments")
    dept_map = {row['code']: row['id'] for row in cur.fetchall()}

    print("Seeding Leave Types (Section 5.05 Policy)...")
    leave_types = [
        ('Casual Leave', 'CL', 6, 0, 1, 1, 'Casual Leave: 6 days/year. Max 3 consecutive days. Lapses at year end.'),
        ('Earned Leave', 'EL', 6, 0, 1, 3, 'Earned Leave: 6 days/year. Carried forward up to max 10 days. Encashment allowed during separation.'),
        ('Sick Leave', 'SL', 12, 0, 1, 0, 'Sick Leave: 12 days/year. Medical certificate required for absence exceeding 2 consecutive days.'),
        ('Maternity Leave', 'ML', 90, 1, 1, 7, 'Maternity Leave: Granted as per Maternity Benefit Act, 2016.'),
        ('Paternity Leave', 'PL', 4, 0, 1, 1, 'Paternity Leave: Eligible male employees may avail 4 days leave within 15 days of childbirth.'),
        ('Restricted Holiday', 'RH', 2, 0, 1, 1, 'Restricted Holiday: Employees may avail any 2 restricted holidays from notified list per year.'),
        ('Compensatory Off', 'COMP', 6, 0, 1, 1, 'Compensatory Off: Eligible for working on off/holidays. Must be availed within 30 days.'),
        ('Bereavement Leave', 'BL', 3, 0, 1, 0, 'Bereavement Leave: Granted in case of death of immediate family members.'),
        ('Loss of Pay', 'LOP', 0, 1, 0, 0, 'Loss of Pay: Applicable when all eligible paid leave balances are exhausted.')
    ]
    cur.executemany("""
        INSERT INTO leave_types (name, code, max_days_per_year, requires_hr_approval, is_paid, notice_period_days, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, leave_types)
    conn.commit()

    # Get leave type IDs
    cur.execute("SELECT id, code FROM leave_types")
    lt_map = {row['code']: row['id'] for row in cur.fetchall()}

    print("Seeding Auto-Approval Rules...")
    leave_rules = [
        ('Casual Leave Max 3 Days Check', 'RULE_CL_MAX3', lt_map['CL'], 'duration_less_eq', 3.0, 'auto_approve', 1, 'Casual leave up to 3 consecutive days auto-approved'),
        ('Sick Leave > 2 Days Medical Cert Rule', 'RULE_SL_MED_CERT', lt_map['SL'], 'duration_greater', 2.0, 'require_hr', 1, 'Sick leave exceeding 2 consecutive days requires medical certificate note'),
        ('Medical / Maternity Leave HR Escalation', 'RULE_ML_HR', lt_map['ML'], 'duration_greater', 0.0, 'require_hr', 1, 'Maternity leave requires HR review'),
        ('Loss of Pay HR Escalation', 'RULE_LOP_HR', lt_map['LOP'], 'duration_greater', 0.0, 'require_hr', 1, 'Loss of Pay requires HR review')
    ]
    cur.executemany("""
        INSERT INTO leave_rules (rule_name, rule_code, leave_type_id, condition_type, threshold_value, action, is_enabled, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, leave_rules)

    print("Seeding Official 2026 Public & Restricted Holidays...")
    holidays = [
        # Official Public Holidays 2026
        ('Makara Sankranti', '2026-01-15', 'Thursday', 'National', 'Public Holiday 2026'),
        ('Republic Day', '2026-01-26', 'Monday', 'National', 'Public Holiday 2026'),
        ('Ugadi Festival', '2026-03-19', 'Thursday', 'National', 'Public Holiday 2026'),
        ('Khutub-E-Ramzan', '2026-03-21', 'Saturday', 'National', 'Public Holiday 2026'),
        ('May Day', '2026-05-01', 'Friday', 'National', 'Public Holiday 2026'),
        ('Bakrid', '2026-05-28', 'Thursday', 'National', 'Public Holiday 2026'),
        ('Independence Day', '2026-08-15', 'Saturday', 'National', 'Public Holiday 2026'),
        ('Eid-Milad', '2026-08-26', 'Wednesday', 'National', 'Public Holiday 2026'),
        ('Gandhi Jayanthi', '2026-10-02', 'Friday', 'National', 'Public Holiday 2026'),
        ('Mahannavami, Ayudha Pooja', '2026-10-20', 'Tuesday', 'National', 'Public Holiday 2026'),
        ('Balipadyami, Deepavali', '2026-11-10', 'Tuesday', 'National', 'Public Holiday 2026'),
        ('Christmas', '2026-12-25', 'Friday', 'National', 'Public Holiday 2026'),

        # Official Restricted Holidays 2026
        ('Shah-e-Barath', '2026-02-04', 'Wednesday', 'Optional', 'Restricted Holiday 2026'),
        ('Holi Festival', '2026-03-02', 'Monday', 'Optional', 'Restricted Holiday 2026'),
        ('Shab-e-Qadar', '2026-03-17', 'Tuesday', 'Optional', 'Restricted Holiday 2026'),
        ('Sri Ramanavami', '2026-03-27', 'Friday', 'Optional', 'Restricted Holiday 2026'),
        ('Mahaveera Jayanthi', '2026-03-31', 'Tuesday', 'Optional', 'Restricted Holiday 2026'),
        ('Good Friday', '2026-04-03', 'Friday', 'Optional', 'Restricted Holiday 2026'),
        ('Dr. B.R. Ambedkar Jayanthi', '2026-04-14', 'Tuesday', 'Optional', 'Restricted Holiday 2026'),
        ('Basava Jayanthi', '2026-04-20', 'Monday', 'Optional', 'Restricted Holiday 2026'),
        ('Last Day of Moharam', '2026-06-26', 'Friday', 'Optional', 'Restricted Holiday 2026'),
        ('Raksha Bandhan', '2026-08-28', 'Friday', 'Optional', 'Restricted Holiday 2026'),
        ('Vijayadasami', '2026-10-21', 'Wednesday', 'Optional', 'Restricted Holiday 2026'),
        ('Guru Nanak Jayanthi', '2026-11-24', 'Tuesday', 'Optional', 'Restricted Holiday 2026'),
        ('Kanakadasa Jayanthi', '2026-11-27', 'Friday', 'Optional', 'Restricted Holiday 2026')
    ]
    cur.executemany("""
        INSERT INTO holidays (title, holiday_date, day_of_week, type, description)
        VALUES (?, ?, ?, ?, ?)
    """, holidays)

    print("Seeding Company Settings...")
    settings = [
        ('company_name', 'Abhyudaya Techno Solutions Pvt Ltd', 'Official Company Name'),
        ('escalation_sla_hours', '24', 'Time in hours after which unattended leave requests escalate'),
        ('min_staffing_threshold_default', '50.0', 'Minimum department staffing percentage required'),
        ('system_email_sender', 'hr@abhyudayatechno.com', 'System email sender address'),
        ('auto_approval_enabled', '1', 'Global toggle for smart auto-approval rules')
    ]
    cur.executemany("""
        INSERT INTO company_settings (setting_key, setting_value, description)
        VALUES (?, ?, ?)
    """, settings)

    print("Seeding Core Users...")
    pass_hash = generate_password_hash('Password123!')

    # 1. Admin User
    cur.execute("""
        INSERT INTO users (emp_id, email, password_hash, full_name, dob, role, department_id, designation, phone, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ('ADM001', 'admin@company.com', pass_hash, 'Arthur Pendelton', '1985-03-10', 'Admin', dept_map['HR'], 'System Administrator', '+1 555-0100', 'Active'))
    admin_id = cur.lastrowid

    # 2. HR User
    cur.execute("""
        INSERT INTO users (emp_id, email, password_hash, full_name, dob, role, department_id, designation, phone, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ('HR001', 'hr@company.com', pass_hash, 'Helen Vance', '1988-07-22', 'HR', dept_map['HR'], 'HR Manager', '+1 555-0101', 'Active'))
    hr_id = cur.lastrowid

    # 3. Employees
    employees_data = [
        ('EMP001', 'emp1@company.com', pass_hash, 'Edward Miller', '1994-09-05', 'Employee', dept_map['ENG'], 'Senior Software Engineer', '+1 555-0104'),
        ('EMP002', 'emp2@company.com', pass_hash, 'Emma Davis', '1996-01-30', 'Employee', dept_map['ENG'], 'Frontend Developer', '+1 555-0105'),
        ('EMP003', 'emp3@company.com', pass_hash, 'Ethan Clark', '1995-12-12', 'Employee', dept_map['SALES'], 'Senior Sales Manager', '+1 555-0106')
    ]
    cur.executemany("""
        INSERT INTO users (emp_id, email, password_hash, full_name, dob, role, department_id, designation, phone, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
    """, employees_data)

    print("Seeding Employee Verification Registry (For Self-Registration)...")
    verifications = [
        ('EMP004', 'new.emp4@company.com', '1995-05-15', 'Evelyn Taylor', dept_map['ENG'], 'Backend Engineer'),
        ('EMP005', 'new.emp5@company.com', '1998-08-20', 'Eric White', dept_map['SALES'], 'Account Executive'),
        ('EMP006', 'new.emp6@company.com', '1997-03-25', 'Ella Scott', dept_map['FIN'], 'Financial Analyst')
    ]
    cur.executemany("""
        INSERT INTO employee_verification (emp_id, company_email, dob, full_name, department_id, designation)
        VALUES (?, ?, ?, ?, ?, ?)
    """, verifications)

    # Get all users for creating leave balances
    cur.execute("SELECT id, role FROM users")
    all_users = cur.fetchall()
    
    current_year = datetime.now().year
    print(f"Seeding Leave Balances for {current_year}...")
    
    cur.execute("SELECT id, max_days_per_year FROM leave_types")
    all_leave_types = cur.fetchall()

    balance_rows = []
    for user in all_users:
        u_id = user['id']
        for lt in all_leave_types:
            lt_id = lt['id']
            max_days = float(lt['max_days_per_year'])
            balance_rows.append((u_id, lt_id, current_year, max_days, 0.0, 0.0, max_days))

    cur.executemany("""
        INSERT INTO leave_balances (user_id, leave_type_id, year, total_allocated, used, pending, remaining)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, balance_rows)

    conn.commit()
    conn.close()
    print("Database seeding completed cleanly!")

if __name__ == '__main__':
    seed_database()
