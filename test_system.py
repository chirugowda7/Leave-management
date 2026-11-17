import os
import sys
import io
import unittest
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

from config import Config
from app import app
from database.db import init_db, get_db_connection, execute_db, query_db
from database.seed import seed_database
from services.leave_service import (
    validate_leave_request, evaluate_auto_approval_rules, create_leave_request,
    check_team_availability, process_hr_approval
)
from services.report_service import generate_excel_leave_report, generate_pdf_leave_report

class TestLeaveManagementSystem(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        self.client = app.test_client()
        db_path = app.config.get('DATABASE_PATH', Config.DATABASE_PATH)
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass
        seed_database()

    def test_01_database_and_admin_seed(self):
        """Test database seed integrity."""
        admin = query_db("SELECT * FROM users WHERE role = 'Admin'", one=True)
        self.assertIsNotNone(admin)
        self.assertEqual(admin['emp_id'], 'ADM001')

        emp = query_db("SELECT * FROM users WHERE role = 'Employee'", one=True)
        self.assertIsNotNone(emp)

    def test_02_self_registration_verification(self):
        """Test Employee Self-Registration verification logic."""
        # Unregistered record EMP004
        verif = query_db("SELECT * FROM employee_verification WHERE emp_id = 'EMP004'", one=True)
        self.assertIsNotNone(verif)
        self.assertEqual(verif['is_registered'], 0)

        # Submit registration form via test client
        res = self.client.post('/register', data={
            'email': 'new.emp4@company.com',
            'dob': '1995-05-15',
            'password': 'NewPassword123!',
            'confirm_password': 'NewPassword123!',
            'phone': '+1 555-0999'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)

        # Verify user created in DB with auto-matched emp_id
        new_emp = query_db("SELECT * FROM users WHERE email = 'new.emp4@company.com'", one=True)
        self.assertIsNotNone(new_emp)
        self.assertEqual(new_emp['emp_id'], 'EMP004')
        self.assertEqual(new_emp['role'], 'Employee')

    def test_03_smart_leave_validation(self):
        """Test leave validations (balance, duplicates, past dates)."""
        emp = query_db("SELECT * FROM users WHERE emp_id = 'EMP001'", one=True)
        lt_cl = query_db("SELECT * FROM leave_types WHERE code = 'CL'", one=True)

        today_str = date.today().strftime('%Y-%m-%d')
        future_date = date.today() + timedelta(days=1)
        while future_date.weekday() >= 5:
            future_date += timedelta(days=1)
        future_str = future_date.strftime('%Y-%m-%d')

        # Test valid request
        is_valid, errors, warning, days = validate_leave_request(emp['id'], lt_cl['id'], future_str, future_str)
        self.assertTrue(is_valid)
        self.assertEqual(days, 1.0)

        # Test invalid past date
        is_valid_past, errors_past, _, _ = validate_leave_request(emp['id'], lt_cl['id'], '2020-01-01', '2020-01-02')
        self.assertFalse(is_valid_past)
        self.assertIn("Leave start date cannot be in the past.", errors_past)

    def test_04_auto_approval_engine(self):
        """Test auto-approval rule evaluation for 1-day casual leave and maternity leave."""
        lt_cl = query_db("SELECT * FROM leave_types WHERE code = 'CL'", one=True)
        lt_ml = query_db("SELECT * FROM leave_types WHERE code = 'ML'", one=True)

        # 1-day Casual Leave -> Auto Approve
        action_cl, reason_cl = evaluate_auto_approval_rules(lt_cl['id'], 1.0)
        self.assertEqual(action_cl, 'auto_approve')

        # Maternity Leave -> Require HR
        action_ml, reason_ml = evaluate_auto_approval_rules(lt_ml['id'], 90.0)
        self.assertEqual(action_ml, 'require_hr')

    def test_05_team_availability_checker(self):
        """Test team staffing percentage calculation."""
        dept = query_db("SELECT * FROM departments WHERE code = 'ENG'", one=True)
        today_str = date.today().strftime('%Y-%m-%d')

        avail = check_team_availability(dept['id'], today_str, today_str)
        self.assertIn('availability_pct', avail)
        self.assertIn('total_dept_members', avail)

    def test_06_report_generation(self):
        """Test PDF and Excel report generation."""
        excel_buf = generate_excel_leave_report()
        self.assertIsNotNone(excel_buf)
        self.assertTrue(len(excel_buf.getvalue()) > 0)

        pdf_buf = generate_pdf_leave_report()
        self.assertIsNotNone(pdf_buf)
        self.assertTrue(len(pdf_buf.getvalue()) > 0)

    def test_07_employee_deletion(self):
        """Test employee deletion functionality by Admin/HR."""
        # Create a temporary user to delete
        temp_id = execute_db("""
            INSERT INTO users (emp_id, email, password_hash, full_name, role, status)
            VALUES ('DEL001', 'delete.me@company.com', 'hash', 'Delete Me', 'Employee', 'Active')
        """)
        self.assertIsNotNone(temp_id)

        # Login as Admin
        with self.client.session_transaction() as sess:
            admin = query_db("SELECT * FROM users WHERE role = 'Admin'", one=True)
            sess['user_id'] = admin['id']
            sess['user_role'] = 'Admin'

        res = self.client.post('/admin/employees', data={
            'action': 'delete_employee',
            'user_id': temp_id
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        deleted = query_db("SELECT * FROM users WHERE id = ?", (temp_id,), one=True)
        self.assertIsNone(deleted)

    def test_08_hr_id_card_access_control(self):
        """Test HR-only access to Employee ID Card Generator."""
        emp = query_db("SELECT * FROM users WHERE role = 'Employee'", one=True)
        hr = query_db("SELECT * FROM users WHERE role = 'HR'", one=True)
        self.assertIsNotNone(emp)
        self.assertIsNotNone(hr)

        # 1. Access by Employee -> Redirected to unauthorized (302)
        with self.client.session_transaction() as sess:
            sess['user_id'] = emp['id']
            sess['user_role'] = 'Employee'

        res_emp = self.client.get(f"/hr/id-card/{emp['id']}")
        self.assertEqual(res_emp.status_code, 302)
        self.assertIn('/unauthorized', res_emp.location)

        # 2. Access by HR -> Authorized / 200 OK
        with self.client.session_transaction() as sess:
            sess['user_id'] = hr['id']
            sess['user_role'] = 'HR'

        res_hr = self.client.get(f"/hr/id-card/{emp['id']}")
        self.assertEqual(res_hr.status_code, 200)

    def test_09_hr_update_id_card(self):
        """Test HR updating employee ID card details."""
        emp = query_db("SELECT * FROM users WHERE role = 'Employee'", one=True)
        hr = query_db("SELECT * FROM users WHERE role = 'HR'", one=True)

        with self.client.session_transaction() as sess:
            sess['user_id'] = hr['id']
            sess['user_role'] = 'HR'

        res = self.client.post(f"/hr/id-card/update/{emp['id']}", data={
            'full_name': 'Edward Miller',
            'emp_id': emp['emp_id'],
            'blood_group': 'O +ve',
            'email': emp['email'],
            'phone': '9148765643',
            'address': 'Hubli'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        updated = query_db("SELECT * FROM users WHERE id = ?", (emp['id'],), one=True)
        self.assertEqual(updated['full_name'], 'Edward Miller')
        self.assertEqual(updated['blood_group'], 'O +ve')
        self.assertEqual(updated['phone'], '9148765643')
        self.assertEqual(updated['address'], 'Hubli')

if __name__ == '__main__':
    unittest.main()
