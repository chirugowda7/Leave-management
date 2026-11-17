from database.db import execute_db, query_db

def send_notification(user_id, title, message, notif_type='info', link=None):
    """
    Sends a system notification to a specified user.
    Types: 'info', 'success', 'warning', 'danger'
    """
    try:
        execute_db("""
            INSERT INTO notifications (user_id, title, message, type, link)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, title, message, notif_type, link))
        return True
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False

def notify_role(role, title, message, notif_type='info', link=None):
    """
    Sends notification to all active users with a given role (e.g. HR, Admin).
    """
    users = query_db("SELECT id FROM users WHERE role = ? AND status = 'Active'", (role,))
    for u in users:
        send_notification(u['id'], title, message, notif_type, link)

def get_user_notifications(user_id, limit=10):
    return query_db("""
        SELECT * FROM notifications 
        WHERE user_id = ? 
        ORDER BY created_at DESC LIMIT ?
    """, (user_id, limit))

def get_unread_count(user_id):
    res = query_db("""
        SELECT COUNT(*) as count FROM notifications 
        WHERE user_id = ? AND is_read = 0
    """, (user_id,), one=True)
    return res['count'] if res else 0

def mark_notifications_read(user_id):
    execute_db("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
