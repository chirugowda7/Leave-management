-- Database DDL Schema for Smart Role-Based Hierarchical Leave Management System

CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL UNIQUE,
    min_staffing_percentage REAL DEFAULT 50.0,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    dob DATE,
    role TEXT NOT NULL CHECK(role IN ('Admin', 'HR', 'Employee')),
    department_id INTEGER,
    designation TEXT,
    phone TEXT,
    blood_group TEXT,
    address TEXT,
    profile_pic TEXT,
    verification_doc TEXT,
    status TEXT DEFAULT 'Active' CHECK(status IN ('Active', 'Inactive')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE IF NOT EXISTS employee_verification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id TEXT NOT NULL UNIQUE,
    company_email TEXT NOT NULL UNIQUE,
    dob DATE NOT NULL,
    full_name TEXT NOT NULL,
    department_id INTEGER NOT NULL,
    designation TEXT DEFAULT 'Software Engineer',
    blood_group TEXT,
    address TEXT,
    verification_doc TEXT,
    is_registered INTEGER DEFAULT 0,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE IF NOT EXISTS leave_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL UNIQUE,
    max_days_per_year INTEGER NOT NULL DEFAULT 12,
    requires_hr_approval INTEGER DEFAULT 0,
    is_paid INTEGER DEFAULT 1,
    notice_period_days INTEGER DEFAULT 0,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS leave_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    leave_type_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    total_allocated REAL NOT NULL,
    used REAL DEFAULT 0.0,
    pending REAL DEFAULT 0.0,
    remaining REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (leave_type_id) REFERENCES leave_types(id),
    UNIQUE(user_id, leave_type_id, year)
);

CREATE TABLE IF NOT EXISTS leave_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_number TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    leave_type_id INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    total_days REAL NOT NULL,
    is_half_day INTEGER DEFAULT 0,
    half_day_session TEXT CHECK(half_day_session IN ('Morning', 'Afternoon', NULL)),
    reason TEXT NOT NULL,
    status TEXT DEFAULT 'Pending HR' CHECK(status IN ('Pending HR', 'Approved', 'Rejected', 'Cancelled', 'Escalated')),
    tl_id INTEGER,
    tl_comment TEXT,
    tl_action_at TIMESTAMP,
    hr_id INTEGER,
    hr_comment TEXT,
    hr_action_at TIMESTAMP,
    is_auto_approved INTEGER DEFAULT 0,
    auto_approval_reason TEXT,
    is_escalated INTEGER DEFAULT 0,
    escalated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (leave_type_id) REFERENCES leave_types(id),
    FOREIGN KEY (tl_id) REFERENCES users(id),
    FOREIGN KEY (hr_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS leave_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL,
    rule_code TEXT NOT NULL UNIQUE,
    leave_type_id INTEGER,
    condition_type TEXT NOT NULL, -- e.g. 'half_day', 'duration_less_eq', 'duration_greater', 'medical_greater_3'
    threshold_value REAL,
    action TEXT NOT NULL CHECK(action IN ('auto_approve', 'require_hr')),
    is_enabled INTEGER DEFAULT 1,
    description TEXT,
    FOREIGN KEY (leave_type_id) REFERENCES leave_types(id)
);

CREATE TABLE IF NOT EXISTS holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    holiday_date DATE NOT NULL UNIQUE,
    day_of_week TEXT,
    type TEXT DEFAULT 'National' CHECK(type IN ('National', 'Regional', 'Optional')),
    description TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT DEFAULT 'info' CHECK(type IN ('info', 'success', 'warning', 'danger')),
    link TEXT,
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    user_name TEXT,
    role TEXT,
    action TEXT NOT NULL,
    module TEXT NOT NULL,
    details TEXT,
    ip_address TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS company_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key TEXT NOT NULL UNIQUE,
    setting_value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
