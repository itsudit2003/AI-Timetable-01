from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from models.teacher import Teacher
from extensions import db, limiter

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET','POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash("Please enter both username and password")
            return redirect(url_for('auth.login'))

        teacher = Teacher.query.filter_by(username=username).first()

        # Handle None password or invalid credentials
        if not teacher or not teacher.password or not check_password_hash(teacher.password, password):
            flash("Invalid credentials")
            return redirect(url_for('auth.login'))

        session['user_id'] = teacher.id
        flash(f"Welcome, {teacher.username}")
        return redirect(url_for('main.dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET','POST'])
@limiter.limit("2 per minute")
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash("Please fill all fields")
            return redirect(url_for('auth.register'))

        if Teacher.query.filter_by(username=username).first():
            flash("Username already exists")
            return redirect(url_for('auth.register'))

        hashed_pw = generate_password_hash(password)
        teacher = Teacher(username=username, password=hashed_pw)
        db.session.add(teacher)
        db.session.commit()

        flash("Account created successfully! Please login.")
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("Logged out successfully")
    return redirect(url_for('auth.login'))
