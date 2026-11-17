from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import date, datetime
from database.db import query_db, execute_db
from middleware.auth import login_required, roles_required, get_current_user, log_audit
from services.leave_service import (
    validate_leave_request, create_leave_request, cancel_leave_request,
    check_team_availability, calculate_working_days
)
from services.notification_service import (
    get_user_notifications, get_unread_count, mark_notifications_read
)

emp_bp = Blueprint('employee', __name__, url_prefix='/employee')

@emp_bp.route('/dashboard')
@login_required
@roles_required('Employee', 'HR', 'Admin')
def dashboard():
    user = get_current_user()
    current_year = date.today().year

    # Leave Balances
    balances = query_db("""
        SELECT lb.*, lt.name as leave_type_name, lt.code as leave_type_code, lt.is_paid
        FROM leave_balances lb
        JOIN leave_types lt ON lb.leave_type_id = lt.id
        WHERE lb.user_id = ? AND lb.year = ?
        ORDER BY lt.id ASC
    """, (user['id'], current_year))

    # Recent Leave Requests
    recent_requests = query_db("""
        SELECT lr.*, lt.name as leave_type_name, lt.code as leave_type_code,
               tl.full_name as tl_name, hr.full_name as hr_name
        FROM leave_requests lr
        JOIN leave_types lt ON lr.leave_type_id = lt.id
        LEFT JOIN users tl ON lr.tl_id = tl.id
        LEFT JOIN users hr ON lr.hr_id = hr.id
        WHERE lr.user_id = ?
        ORDER BY lr.id DESC LIMIT 5
    """, (user['id'],))

    # Upcoming Holidays
    today_str = date.today().strftime('%Y-%m-%d')
    upcoming_holidays = query_db("""
        SELECT * FROM holidays 
        WHERE holiday_date >= ? 
        ORDER BY holiday_date ASC LIMIT 5
    """, (today_str,))

    # Team Staffing Availability Widget
    avail = check_team_availability(user['department_id'], today_str, today_str, exclude_user_id=user['id'])

    # Notifications
    notifications = get_user_notifications(user['id'], limit=5)
    unread_count = get_unread_count(user['id'])

    return render_template(
        'employee/dashboard.html',
        user=user,
        balances=balances,
        recent_requests=recent_requests,
        upcoming_holidays=upcoming_holidays,
        avail=avail,
        notifications=notifications,
        unread_count=unread_count
    )

@emp_bp.route('/apply-leave', methods=['GET', 'POST'])
@login_required
@roles_required('Employee', 'HR', 'Admin')
def apply_leave():
    user = get_current_user()
    leave_types = query_db("SELECT * FROM leave_types ORDER BY id ASC")
    current_year = date.today().year

    # Balances for dropdown inspection
    balances = query_db("""
        SELECT lb.*, lt.name as leave_type_name, lt.code as leave_type_code, lt.notice_period_days
        FROM leave_balances lb
        JOIN leave_types lt ON lb.leave_type_id = lt.id
        WHERE lb.user_id = ? AND lb.year = ?
    """, (user['id'], current_year))

    if request.method == 'POST':
        leave_type_id = request.form.get('leave_type_id', type=int)
        start_date = request.form.get('start_date', '').strip()
        end_date = request.form.get('end_date', '').strip()
        is_half_day = request.form.get('is_half_day') == '1'
        half_day_session = request.form.get('half_day_session', 'Morning')
        reason = request.form.get('reason', '').strip()

        if is_half_day:
            end_date = start_date

        success, msgs, req_id = create_leave_request(
            user_id=user['id'],
            leave_type_id=leave_type_id,
            start_date_str=start_date,
            end_date_str=end_date,
            is_half_day=is_half_day,
            half_day_session=half_day_session,
            reason=reason
        )

        if success:
            log_audit(user['id'], 'APPLY_LEAVE_SUCCESS', 'Leave', f"Applied for leave from {start_date} to {end_date}")
            flash(msgs[0], 'success')
            return redirect(url_for('employee.history'))
        else:
            log_audit(user['id'], 'APPLY_LEAVE_FAILED', 'Leave', f"Validation failed: {', '.join(msgs)}")
            for err in msgs:
                flash(err, 'danger')

    return render_template('employee/apply_leave.html', user=user, leave_types=leave_types, balances=balances)

@emp_bp.route('/history')
@login_required
@roles_required('Employee', 'HR', 'Admin')
def history():
    user = get_current_user()
    status_filter = request.args.get('status', 'all')

    query = """
        SELECT lr.*, lt.name as leave_type_name, lt.code as leave_type_code,
               tl.full_name as tl_name, hr.full_name as hr_name
        FROM leave_requests lr
        JOIN leave_types lt ON lr.leave_type_id = lt.id
        LEFT JOIN users tl ON lr.tl_id = tl.id
        LEFT JOIN users hr ON lr.hr_id = hr.id
        WHERE lr.user_id = ?
    """
    args = [user['id']]

    if status_filter != 'all':
        query += " AND lr.status = ?"
        args.append(status_filter)

    query += " ORDER BY lr.id DESC"
    requests_list = query_db(query, tuple(args))

    return render_template('employee/history.html', user=user, requests=requests_list, current_filter=status_filter)

@emp_bp.route('/cancel-leave/<int:request_id>', methods=['POST'])
@login_required
@roles_required('Employee', 'HR', 'Admin')
def cancel_leave(request_id):
    user = get_current_user()
    success, msg = cancel_leave_request(request_id, user['id'])

    if success:
        log_audit(user['id'], 'CANCEL_LEAVE', 'Leave', f"Cancelled leave request ID {request_id}")
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    return redirect(url_for('employee.history'))

@emp_bp.route('/holidays')
@login_required
@roles_required('Employee', 'HR', 'Admin')
def holidays():
    user = get_current_user()
    holidays_list = query_db("SELECT * FROM holidays ORDER BY holiday_date ASC")
    return render_template('employee/holidays.html', user=user, holidays=holidays_list)

@emp_bp.route('/notifications')
@login_required
@roles_required('Employee', 'HR', 'Admin')
def notifications():
    user = get_current_user()
    mark_notifications_read(user['id'])
    notifications_list = get_user_notifications(user['id'], limit=30)
    return render_template('employee/notifications.html', user=user, notifications=notifications_list)
