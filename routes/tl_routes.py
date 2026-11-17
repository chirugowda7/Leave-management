# Team Leader routes removed as per workflow updates.
from flask import Blueprint

tl_bp = Blueprint('tl', __name__, url_prefix='/team-leader')
