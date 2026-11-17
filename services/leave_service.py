from datetime import datetime, date, timedelta
from database.db import query_db, execute_db, get_db_connection
from services.notification_service import send_notification, notify_role

def calculate_working_days(start_date_str, end_date_str, is_half_day=False):
    """
    Calculates exact working days between start_date and end_date,
    excluding weekends (Saturday, Sunday) and company holidays.
    """
    if is_half_day:
        return 0.5

    start_d = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_d = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    if end_d < start_d:
        return 0.0

    # Fetch holidays
    holidays = query_db("SELECT holiday_date FROM holidays")
    holiday_dates = {h['holiday_date'] for h in holidays}

    curr = start_d
    working_days = 0.0
    while curr <= end_d:
        curr_str = curr.strftime('%Y-%m-%d')
        # Skip Saturday (5) and Sunday (6)
        if curr.weekday() not in (5, 6) and curr_str not in holiday_dates:
            working_days += 1.0
        curr += timedelta(days=1)

    return working_days

def check_team_availability(department_id, start_date_str, end_date_str, exclude_user_id=None):
    """
    Computes team availability metrics for a department over a date range:
    - Total active department members
    - Count on leave during overlap
    - Availability percentage
    - Staffing threshold check & status
    - Suggested alternative start dates if below threshold
    """
    if not department_id:
        return {
            'total_dept_members': 1,
            'members_on_leave': 0,
            'available_members': 1,
            'availability_pct': 100.0,
            'min_threshold_pct': 50.0,
            'is_below_threshold': False,
            'suggested_dates': []
        }

    dept = query_db("SELECT * FROM departments WHERE id = ?", (department_id,), one=True)
    min_threshold = dept['min_staffing_percentage'] if dept else 50.0

    # Total active employees in department
    total_members = query_db("""
        SELECT COUNT(*) as count FROM users 
        WHERE department_id = ? AND status = 'Active'
    """, (department_id,), one=True)['count']

    if total_members == 0:
        total_members = 1

    # Query overlapping approved/pending leaves in department
    query = """
        SELECT DISTINCT lr.user_id 
        FROM leave_requests lr
        JOIN users u ON lr.user_id = u.id
        WHERE u.department_id = ? 
          AND lr.status IN ('Approved', 'Pending TL', 'Pending HR', 'Escalated')
          AND lr.start_date <= ? AND lr.end_date >= ?
    """
    args = [department_id, end_date_str, start_date_str]
    if exclude_user_id:
        query += " AND lr.user_id != ?"
        args.append(exclude_user_id)

    on_leave_users = query_db(query, tuple(args))
    members_on_leave = len(on_leave_users)

    # Calculate available members if current application is approved (+1 on leave)
    projected_on_leave = members_on_leave + 1
    projected_available = max(0, total_members - projected_on_leave)
    availability_pct = round((projected_available / total_members) * 100.0, 1)

    is_below_threshold = availability_pct < min_threshold

    suggested_dates = []
    if is_below_threshold:
        # Suggest dates 7 days and 14 days later
        start_d = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_d = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        duration = (end_d - start_d).days

        for offset in [7, 14, 21]:
            alt_start = start_d + timedelta(days=offset)
            alt_end = alt_start + timedelta(days=duration)
            # Check availability for alternative dates
            alt_on_leave = len(query_db("""
                SELECT DISTINCT lr.user_id FROM leave_requests lr
                JOIN users u ON lr.user_id = u.id
                WHERE u.department_id = ? 
                  AND lr.status IN ('Approved', 'Pending TL', 'Pending HR')
                  AND lr.start_date <= ? AND lr.end_date >= ?
            """, (department_id, alt_end.strftime('%Y-%m-%d'), alt_start.strftime('%Y-%m-%d'))))

            alt_pct = round(((total_members - (alt_on_leave + 1)) / total_members) * 100.0, 1)
            if alt_pct >= min_threshold:
                suggested_dates.append({
                    'start_date': alt_start.strftime('%Y-%m-%d'),
                    'end_date': alt_end.strftime('%Y-%m-%d'),
                    'availability_pct': alt_pct
                })
                if len(suggested_dates) >= 2:
                    break

    return {
        'total_dept_members': total_members,
        'members_on_leave': members_on_leave,
        'available_members': projected_available,
        'availability_pct': availability_pct,
        'min_threshold_pct': min_threshold,
        'is_below_threshold': is_below_threshold,
        'suggested_dates': suggested_dates
    }

def validate_leave_request(user_id, leave_type_id, start_date_str, end_date_str, is_half_day=False):
    """
    Performs comprehensive smart validations:
    1. Valid dates (start <= end, start >= today)
    2. Working days calculation
    3. Notice period check
    4. Balance check
    5. Duplicate date overlap check
    6. Minimum staffing threshold check
    Returns: (is_valid: bool, errors: list, warning_msg: str, calculated_days: float)
    """
    errors = []
    warning = None

    today = date.today()
    try:
        start_d = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_d = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return False, ["Invalid date format. Use YYYY-MM-DD."], None, 0.0

    if end_d < start_d:
        errors.append("End date cannot be earlier than start date.")

    if start_d < today:
        errors.append("Leave start date cannot be in the past.")

    # Calculate actual working days
    total_days = calculate_working_days(start_date_str, end_date_str, is_half_day)
    if total_days <= 0:
        errors.append("The selected date range contains no working days (all weekends or company holidays).")

    # Fetch Leave Type details
    lt = query_db("SELECT * FROM leave_types WHERE id = ?", (leave_type_id,), one=True)
    if not lt:
        errors.append("Invalid leave type selected.")
        return False, errors, None, 0.0

    # Section 5.05 Policy Specific Rule Validations
    if lt['code'] == 'CL' and total_days > 3.0:
        errors.append("Casual Leave (CL) policy rule: Maximum 3 consecutive days allowed per application.")

    if lt['code'] == 'PL' and total_days > 4.0:
        errors.append("Paternity Leave (PL) policy rule: Maximum 4 days allowed within 15 days of childbirth.")

    if lt['code'] == 'RH':
        # Check if selected date is in Restricted Holiday list
        rh_match = query_db("SELECT * FROM holidays WHERE holiday_date = ? AND type = 'Optional'", (start_date_str,), one=True)
        if not rh_match:
            errors.append("Selected start date does not fall on an official Restricted Holiday (RH). Please select a date from the 2026 Restricted Holiday List.")

    # Notice Period Validation
    if lt['notice_period_days'] > 0:
        notice_required_date = today + timedelta(days=lt['notice_period_days'])
        if start_d < notice_required_date:
            errors.append(f"{lt['name']} requires a minimum notice period of {lt['notice_period_days']} day(s). Minimum valid start date is {notice_required_date.strftime('%Y-%m-%d')}.")

    # Leave Balance Check
    current_year = today.year
    balance = query_db("""
        SELECT * FROM leave_balances 
        WHERE user_id = ? AND leave_type_id = ? AND year = ?
    """, (user_id, leave_type_id, current_year), one=True)

    if not balance:
        errors.append("No leave balance record found for this leave type.")
    elif balance['remaining'] < total_days:
        errors.append(f"Insufficient leave balance. Requested: {total_days} day(s), Remaining: {balance['remaining']} day(s).")

    # Duplicate / Overlapping Leave Check
    overlap = query_db("""
        SELECT request_number, start_date, end_date, status 
        FROM leave_requests 
        WHERE user_id = ? 
          AND status IN ('Pending HR', 'Approved', 'Escalated')
          AND start_date <= ? AND end_date >= ?
    """, (user_id, end_date_str, start_date_str), one=True)

    if overlap:
        errors.append(f"You already have an active leave request ({overlap['request_number']} - {overlap['status']}) overlapping from {overlap['start_date']} to {overlap['end_date']}.")

    # Department Minimum Staffing Check
    user = query_db("SELECT department_id FROM users WHERE id = ?", (user_id,), one=True)
    if user and user['department_id']:
        avail = check_team_availability(user['department_id'], start_date_str, end_date_str, exclude_user_id=user_id)
        if avail['is_below_threshold']:
            warning = f"Notice: Department staffing will fall to {avail['availability_pct']}% during this period (Minimum required: {avail['min_threshold_pct']}%)."

    is_valid = len(errors) == 0
    return is_valid, errors, warning, total_days

def evaluate_auto_approval_rules(leave_type_id, total_days, is_half_day=False):
    """
    Evaluates configurable rules in `leave_rules` table.
    Returns: (action: 'auto_approve' | 'require_hr', rule_reason: str)
    """
    # Fetch active rules
    rules = query_db("SELECT * FROM leave_rules WHERE is_enabled = 1 ORDER BY id ASC")
    lt = query_db("SELECT code, name, requires_hr_approval FROM leave_types WHERE id = ?", (leave_type_id,), one=True)

    if lt and lt['requires_hr_approval'] == 1:
        return 'require_hr', f"Special Leave Type ({lt['name']}) requires HR approval"

    for r in rules:
        c_type = r['condition_type']
        val = r['threshold_value']
        target_lt = r['leave_type_id']

        # Rule filter by leave type if specified
        if target_lt and target_lt != leave_type_id:
            continue

        if c_type == 'half_day' and is_half_day:
            return r['action'], f"Rule '{r['rule_name']}': Half-Day auto approval"
        elif c_type == 'duration_less_eq' and total_days <= val:
            return r['action'], f"Rule '{r['rule_name']}': Duration <= {val} day(s)"
        elif c_type == 'medical_greater_3' and lt and lt['code'] == 'ML' and total_days > val:
            return r['action'], f"Rule '{r['rule_name']}': Medical leave > {val} days requires HR"
        elif c_type == 'duration_greater' and total_days > val:
            return r['action'], f"Rule '{r['rule_name']}': Duration > {val} days requires HR"

    # Default routing: Normal leave requires HR
    return 'require_hr', "Standard Leave Routing to HR"

def create_leave_request(user_id, leave_type_id, start_date_str, end_date_str, is_half_day, half_day_session, reason):
    """
    Validates, applies auto-approval rules, deducts pending balance, creates request record and triggers notifications.
    """
    is_valid, errors, warning, total_days = validate_leave_request(
        user_id, leave_type_id, start_date_str, end_date_str, is_half_day
    )

    if not is_valid:
        return False, errors, None

    # Fetch user details
    user = query_db("""
        SELECT u.*, d.name as department_name 
        FROM users u 
        LEFT JOIN departments d ON u.department_id = d.id 
        WHERE u.id = ?
    """, (user_id,), one=True)

    # Determine auto-approval / workflow routing
    action, rule_reason = evaluate_auto_approval_rules(leave_type_id, total_days, is_half_day)

    # Generate request number
    req_num = f"LR-{datetime.now().strftime('%Y%m%d')}-{query_db('SELECT COUNT(*) as cnt FROM leave_requests', one=True)['cnt'] + 1:04d}"

    today_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    current_year = date.today().year

    if action == 'auto_approve':
        status = 'Approved'
        is_auto_approved = 1
        auto_approval_reason = rule_reason
        
        # Directly deduct balance
        execute_db("""
            UPDATE leave_balances 
            SET used = used + ?, remaining = remaining - ?
            WHERE user_id = ? AND leave_type_id = ? AND year = ?
        """, (total_days, total_days, user_id, leave_type_id, current_year))
        
    else: # require_hr
        status = 'Pending HR'
        is_auto_approved = 0
        auto_approval_reason = rule_reason
        
        # Add to pending balance
        execute_db("""
            UPDATE leave_balances 
            SET pending = pending + ?
            WHERE user_id = ? AND leave_type_id = ? AND year = ?
        """, (total_days, user_id, leave_type_id, current_year))

    # Insert Leave Request
    req_id = execute_db("""
        INSERT INTO leave_requests (
            request_number, user_id, leave_type_id, start_date, end_date, total_days,
            is_half_day, half_day_session, reason, status,
            is_auto_approved, auto_approval_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        req_num, user_id, leave_type_id, start_date_str, end_date_str, total_days,
        1 if is_half_day else 0, half_day_session if is_half_day else None, reason,
        status, is_auto_approved, auto_approval_reason
    ))

    # Notifications
    if status == 'Approved':
        send_notification(
            user_id, 
            "Leave Approved Automatically", 
            f"Your leave request {req_num} ({total_days} day(s)) has been automatically approved.",
            "success"
        )
    else: # Pending HR
        send_notification(
            user_id,
            "Leave Submitted for HR Review",
            f"Your leave request {req_num} ({total_days} day(s)) has been submitted and is pending HR approval.",
            "info"
        )
        notify_role('HR', "New Pending Leave Request", f"Leave request {req_num} from {user['full_name']} requires HR approval.", "warning")

    return True, [f"Leave request {req_num} submitted successfully ({status})."], req_id

def process_tl_approval(request_id, tl_user_id, action, comment):
    """
    Team Leader approval or rejection of leave request.
    If action == 'approve' -> status becomes 'Approved' & balance updated.
    If action == 'reject' -> status becomes 'Rejected' & pending balance restored.
    If action == 'escalate' -> status becomes 'Pending HR' & forwarded to HR.
    """
    req = query_db("""
        SELECT lr.*, u.full_name as applicant_name, u.email as applicant_email 
        FROM leave_requests lr
        JOIN users u ON lr.user_id = u.id
        WHERE lr.id = ?
    """, (request_id,), one=True)

    if not req:
        return False, "Leave request not found."

    if req['status'] not in ('Pending TL', 'Escalated'):
        return False, f"Request cannot be modified as it is currently '{req['status']}'."

    today_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    current_year = date.today().year

    if action == 'approve':
        # Update leave balance: deduct pending, add to used, remaining reduced
        execute_db("""
            UPDATE leave_balances 
            SET pending = max(0, pending - ?), used = used + ?, remaining = remaining - ?
            WHERE user_id = ? AND leave_type_id = ? AND year = ?
        """, (req['total_days'], req['total_days'], req['total_days'], req['user_id'], req['leave_type_id'], current_year))

        execute_db("""
            UPDATE leave_requests 
            SET status = 'Approved', tl_id = ?, tl_comment = ?, tl_action_at = ?
            WHERE id = ?
        """, (tl_user_id, comment, today_str, request_id))

        send_notification(
            req['user_id'],
            "Leave Approved",
            f"Your leave request {req['request_number']} was approved by your Team Leader.",
            "success"
        )
        return True, "Leave request approved successfully."

    elif action == 'reject':
        # Restore pending balance
        execute_db("""
            UPDATE leave_balances 
            SET pending = max(0, pending - ?)
            WHERE user_id = ? AND leave_type_id = ? AND year = ?
        """, (req['total_days'], req['user_id'], req['leave_type_id'], current_year))

        execute_db("""
            UPDATE leave_requests 
            SET status = 'Rejected', tl_id = ?, tl_comment = ?, tl_action_at = ?
            WHERE id = ?
        """, (tl_user_id, comment, today_str, request_id))

        send_notification(
            req['user_id'],
            "Leave Rejected",
            f"Your leave request {req['request_number']} was rejected by your Team Leader. Reason: {comment}",
            "danger"
        )
        return True, "Leave request rejected."

    elif action == 'escalate':
        execute_db("""
            UPDATE leave_requests 
            SET status = 'Pending HR', tl_id = ?, tl_comment = ?, tl_action_at = ?,
                is_escalated = 1, escalated_at = ?
            WHERE id = ?
        """, (tl_user_id, f"Escalated to HR: {comment}", today_str, today_str, request_id))

        notify_role('HR', "Leave Escalated by Team Leader", f"Leave {req['request_number']} for {req['applicant_name']} was manually escalated to HR.", "warning")
        send_notification(
            req['user_id'],
            "Leave Escalated to HR",
            f"Your leave request {req['request_number']} has been escalated to HR for review.",
            "info"
        )
        return True, "Leave request escalated to HR."

    return False, "Invalid action specified."

def process_hr_approval(request_id, hr_user_id, action, comment):
    """
    HR approval or rejection for escalated / special leave requests.
    """
    req = query_db("""
        SELECT lr.*, u.full_name as applicant_name 
        FROM leave_requests lr
        JOIN users u ON lr.user_id = u.id
        WHERE lr.id = ?
    """, (request_id,), one=True)

    if not req:
        return False, "Leave request not found."

    if req['status'] not in ('Pending HR', 'Escalated'):
        return False, f"Request cannot be modified by HR as it is currently '{req['status']}'."

    today_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    current_year = date.today().year

    if action == 'approve':
        execute_db("""
            UPDATE leave_balances 
            SET pending = max(0, pending - ?), used = used + ?, remaining = remaining - ?
            WHERE user_id = ? AND leave_type_id = ? AND year = ?
        """, (req['total_days'], req['total_days'], req['total_days'], req['user_id'], req['leave_type_id'], current_year))

        execute_db("""
            UPDATE leave_requests 
            SET status = 'Approved', hr_id = ?, hr_comment = ?, hr_action_at = ?
            WHERE id = ?
        """, (hr_user_id, comment, today_str, request_id))

        send_notification(
            req['user_id'],
            "Leave Approved by HR",
            f"Your special leave request {req['request_number']} has been approved by HR.",
            "success"
        )
        return True, "Leave request approved by HR."

    elif action == 'reject':
        execute_db("""
            UPDATE leave_balances 
            SET pending = max(0, pending - ?)
            WHERE user_id = ? AND leave_type_id = ? AND year = ?
        """, (req['total_days'], req['user_id'], req['leave_type_id'], current_year))

        execute_db("""
            UPDATE leave_requests 
            SET status = 'Rejected', hr_id = ?, hr_comment = ?, hr_action_at = ?
            WHERE id = ?
        """, (hr_user_id, comment, today_str, request_id))

        send_notification(
            req['user_id'],
            "Leave Rejected by HR",
            f"Your leave request {req['request_number']} was rejected by HR. Reason: {comment}",
            "danger"
        )
        return True, "Leave request rejected by HR."

    return False, "Invalid action specified."

def cancel_leave_request(request_id, user_id):
    """
    Allows employee to cancel pending leave request before approval.
    """
    req = query_db("SELECT * FROM leave_requests WHERE id = ? AND user_id = ?", (request_id, user_id), one=True)
    if not req:
        return False, "Leave request not found or unauthorized."

    if req['status'] not in ('Pending HR', 'Escalated'):
        return False, "Only pending leave requests can be cancelled."

    current_year = date.today().year

    # Restore pending balance
    execute_db("""
        UPDATE leave_balances 
        SET pending = max(0, pending - ?)
        WHERE user_id = ? AND leave_type_id = ? AND year = ?
    """, (req['total_days'], user_id, req['leave_type_id'], current_year))

    execute_db("UPDATE leave_requests SET status = 'Cancelled' WHERE id = ?", (request_id,))

    send_notification(
        user_id,
        "Leave Cancelled",
        f"Your leave request {req['request_number']} has been cancelled.",
        "info"
    )
    return True, "Leave request cancelled successfully."
