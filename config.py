import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ats-leave-mgmt-enterprise-secret-key-2026'
    DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'leave_management.db')
    
    # Auto-escalation SLA in hours (e.g. 24 hours without TL response)
    DEFAULT_ESCALATION_HOURS = 24
    
    # Default minimum department staffing threshold percentage
    DEFAULT_MIN_STAFFING_PERCENTAGE = 50.0
    
    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
