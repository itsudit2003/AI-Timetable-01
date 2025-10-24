from flask import Blueprint, render_template, session, redirect, url_for, flash
from models.teacher import Teacher

main_bp = Blueprint('main', __name__)

def login_required(func):
    """Simple decorator to check login"""
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please login first")
            return redirect(url_for('auth.login'))
        return func(*args, **kwargs)
    return wrapper

@main_bp.route('/')
def home():
    return render_template('main/home.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    teacher = Teacher.query.get(session['user_id'])
    return render_template('main/dashboard.html', teacher=teacher)
