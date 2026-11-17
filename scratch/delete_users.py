import os
import sys
import sqlite3

db_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'leave_management.db')
db_path = os.path.abspath(db_path)

print(f"Connecting to database at: {db_path}")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get non-admin user IDs
cur.execute("SELECT id, emp_id, email, full_name, role FROM users WHERE role != 'Admin'")
non_admin_users = cur.fetchall()
non_admin_ids = [u['id'] for u in non_admin_users]

print(f"Found {len(non_admin_users)} non-admin user(s): {[dict(u) for u in non_admin_users]}")

if non_admin_ids:
    placeholders = ', '.join(['?'] * len(non_admin_ids))
    
    # 1. Delete leave requests
    cur.execute(f"DELETE FROM leave_requests WHERE user_id IN ({placeholders}) OR tl_id IN ({placeholders}) OR hr_id IN ({placeholders})", non_admin_ids * 3)
    print("Deleted related leave_requests.")

    # 2. Delete leave balances
    cur.execute(f"DELETE FROM leave_balances WHERE user_id IN ({placeholders})", non_admin_ids)
    print("Deleted related leave_balances.")

    # 3. Delete notifications
    cur.execute(f"DELETE FROM notifications WHERE user_id IN ({placeholders})", non_admin_ids)
    print("Deleted related notifications.")

    # 4. Delete audit logs
    cur.execute(f"DELETE FROM audit_logs WHERE user_id IN ({placeholders})", non_admin_ids)
    print("Deleted related audit_logs.")

    # 5. Delete users
    cur.execute(f"DELETE FROM users WHERE id IN ({placeholders})", non_admin_ids)
    print(f"Deleted {cur.rowcount} users from users table.")

# 6. Delete all employee verification pre-registrations
cur.execute("DELETE FROM employee_verification")
print(f"Deleted {cur.rowcount} employee verification records.")

conn.commit()

print("\n--- DB STATE AFTER DELETION ---")
users_after = cur.execute("SELECT id, emp_id, email, full_name, role FROM users").fetchall()
print("Remaining Users:", [dict(u) for u in users_after])

verif_after = cur.execute("SELECT COUNT(*) FROM employee_verification").fetchone()[0]
print("Remaining Verifications Count:", verif_after)

balances_after = cur.execute("SELECT COUNT(*) FROM leave_balances").fetchone()[0]
print("Remaining Leave Balances Count:", balances_after)

conn.close()
