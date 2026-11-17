import os
import sys
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash

db_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'leave_management.db')
db_path = os.path.abspath(db_path)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get department IDs
cur.execute("SELECT id, code FROM departments")
dept_map = {row['code']: row['id'] for row in cur.fetchall()}

pass_hash = generate_password_hash('Password123!')

# 1. HR User
cur.execute("""
    INSERT INTO users (emp_id, email, password_hash, full_name, dob, role, department_id, designation, phone, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('HR001', 'hr@company.com', pass_hash, 'Helen Vance', '1988-07-22', 'HR', dept_map['HR'], 'HR Manager', '+1 555-0101', 'Active'))
hr_id = cur.lastrowid
print(f"Created HR User: Helen Vance (ID: {hr_id}, emp_id: HR001, email: hr@company.com)")

# Add to employee_verification as registered
cur.execute("""
    INSERT INTO employee_verification (emp_id, company_email, dob, full_name, department_id, designation, is_registered)
    VALUES (?, ?, ?, ?, ?, ?, 1)
""", ('HR001', 'hr@company.com', '1988-07-22', 'Helen Vance', dept_map['HR'], 'HR Manager'))

# 2. Employee User
cur.execute("""
    INSERT INTO users (emp_id, email, password_hash, full_name, dob, role, department_id, designation, phone, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('EMP001', 'emp1@company.com', pass_hash, 'Edward Miller', '1994-09-05', 'Employee', dept_map['ENG'], 'Senior Software Engineer', '+1 555-0104', 'Active'))
emp_id = cur.lastrowid
print(f"Created Employee User: Edward Miller (ID: {emp_id}, emp_id: EMP001, email: emp1@company.com)")

# Add to employee_verification as registered
cur.execute("""
    INSERT INTO employee_verification (emp_id, company_email, dob, full_name, department_id, designation, is_registered)
    VALUES (?, ?, ?, ?, ?, ?, 1)
""", ('EMP001', 'emp1@company.com', '1994-09-05', 'Edward Miller', dept_map['ENG'], 'Senior Software Engineer'))

# 3. Seed Leave Balances for 2026 for both users
cur.execute("SELECT id, max_days_per_year FROM leave_types")
all_leave_types = cur.fetchall()
current_year = datetime.now().year

balance_rows = []
for u_id in [hr_id, emp_id]:
    for lt in all_leave_types:
        lt_id = lt['id']
        max_days = float(lt['max_days_per_year'])
        balance_rows.append((u_id, lt_id, current_year, max_days, 0.0, 0.0, max_days))

cur.executemany("""
    INSERT INTO leave_balances (user_id, leave_type_id, year, total_allocated, used, pending, remaining)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", balance_rows)

print(f"Seeded {len(balance_rows)} leave balance records for the new users.")

conn.commit()

print("\n--- DB USERS CURRENTLY ---")
users = cur.execute("SELECT id, emp_id, email, full_name, role, status FROM users").fetchall()
for u in users:
    print(dict(u))

conn.close()
