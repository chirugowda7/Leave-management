from flask import Blueprint, jsonify, request
from database.db import query_db
from middleware.auth import login_required, get_current_user
from services.leave_service import check_team_availability, calculate_working_days
from services.escalation_service import check_and_escalate_overdue_requests

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/check-availability', methods=['GET'])
@login_required
def api_check_availability():
    user = get_current_user()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        return jsonify({'error': 'Missing dates'}), 400

    dept_id = user['department_id']
    res = check_team_availability(dept_id, start_date, end_date, exclude_user_id=user['id'])
    return jsonify(res)

@api_bp.route('/check-working-days', methods=['GET'])
@login_required
def api_check_working_days():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    is_half_day = request.args.get('is_half_day') == 'true'

    if not start_date or not end_date:
        return jsonify({'working_days': 0.0})

    days = calculate_working_days(start_date, end_date, is_half_day)
    return jsonify({'working_days': days})

@api_bp.route('/chart-data', methods=['GET'])
@login_required
def api_chart_data():
    """
    Returns monthly leave count trends and department leave breakdown for Chart.js
    """
    user = get_current_user()

    # Department breakdown
    dept_breakdown = query_db("""
        SELECT d.name as dept_name, COUNT(lr.id) as leave_count
        FROM leave_requests lr
        JOIN users u ON lr.user_id = u.id
        JOIN departments d ON u.department_id = d.id
        WHERE lr.status = 'Approved'
        GROUP BY d.id
    """)

    # Monthly trends (last 6 months)
    monthly_trends = query_db("""
        SELECT strftime('%Y-%m', start_date) as month, COUNT(id) as count
        FROM leave_requests
        WHERE status = 'Approved'
        GROUP BY month
        ORDER BY month DESC LIMIT 6
    """)

    # Leave status distribution
    status_dist = query_db("""
        SELECT status, COUNT(id) as count
        FROM leave_requests
        GROUP BY status
    """)

    return jsonify({
        'department_breakdown': [dict(r) for r in dept_breakdown],
        'monthly_trends': [dict(r) for r in monthly_trends],
        'status_distribution': [dict(r) for r in status_dist]
    })

@api_bp.route('/run-escalations', methods=['POST'])
@login_required
def api_run_escalations():
    count = check_and_escalate_overdue_requests()
    return jsonify({'escalated_count': count})
