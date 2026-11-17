# Smart Role-Based Enterprise Leave Management System (HRMS)

An enterprise-grade, role-based Leave Management & Human Resource Management System built with Python Flask and SQLite.

## Features

- **Multi-Role Access Control**:
  - **Admin**: System configuration, manage HR personnel, audit logging, system settings.
  - **HR Manager**: Department management, employee onboarding/verification, designations, leave balance allocations, final approvals, ID card generation, PDF/Excel reports.
  - **Manager / Team Lead**: Direct report leave approvals, team availability calendar, staffing threshold safety checks, auto-escalation handling.
  - **Employee**: Apply for leave, view status & history, leave balances, company holidays, notifications, profile management.
- **Intelligent Leave Management**:
  - Support for Casual Leave (CL), Earned Leave (EL), Sick Leave (SL), Maternity Leave (ML), Paternity Leave (PL), and Restricted Holidays (RH).
  - Department minimum staffing threshold protection.
  - Auto-escalation SLA for pending requests.
  - Multi-tier approval workflow (Manager $\rightarrow$ HR).
- **ID Card & Report Generation**:
  - Dynamic employee ID card generation with QR code.
  - Export leave reports and analytics in PDF and Excel formats.

## Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/chirugowda7/Leave-management.git
   cd Leave-management
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application**:
   ```bash
   python app.py
   ```
   The database schema is automatically created and seeded on the first run.

5. **Access the application**:
   Open [http://localhost:5000](http://localhost:5000) in your browser.

### Default Login Credentials

- **Admin**: `ADM001` / `Password123!`
- **HR Manager**: `HR001` / `Password123!`
- **Employee**: `EMP001` / `Password123!`
