from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db
from functools import wraps
from config import HOD_USERNAME, HOD_PASSWORD

auth_bp = Blueprint('auth', __name__)

def hod_required(f):
    @wraps(f)
    def decorated(*args,**kwargs):
        if session.get('role') != 'hod':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def teacher_required(f):
    @wraps(f)
    def decorated(*args,**kwargs):
        if session.get('role') != 'teacher':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@auth_bp.route('/')
def home(): return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email')
        password=request.form.get('password')
        conn=get_db()
        cur=conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM hods WHERE email=%s",(email,))
        hod=cur.fetchone()
        cur.execute("SELECT * FROM teachers WHERE email=%s",(email,))
        teacher=cur.fetchone()
        cur.close(); conn.close()
        if hod and check_password_hash(hod['password'],password):
            session.clear(); session['hod_id']=hod['id']; session['role']='hod'; session['user']=hod['name']
            return redirect(url_for('admin.admin'))
        if teacher and check_password_hash(teacher['password'],password):
            session.clear(); session['teacher_id']=teacher['id']; session['role']='teacher'; session['user']=teacher['name']
            return redirect(url_for('teacher.teacher_dashboard'))
        if email==HOD_USERNAME and password==HOD_PASSWORD:
            session.clear(); session['role']='hod'; session['user']=HOD_USERNAME
            return redirect(url_for('admin.admin'))
        flash("Invalid email or password","danger")
        return redirect(url_for('auth.login'))
    return render_template('login.html')

@auth_bp.route('/signup', methods=['GET','POST'])
def signup():
    if request.method=='POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        role = request.form.get('role')
        max_hours = int(request.form.get('max_hours') or 20)

        if password != confirm:
            flash("Passwords do not match", "danger")
            return render_template('signup.html')

        hashed = generate_password_hash(password)
        conn = get_db()
        cur = conn.cursor()

        cur.execute('SELECT id FROM teachers WHERE email=%s', (email,))
        if cur.fetchone():
            flash("User already exists", "danger")
            cur.close(); conn.close()
            return render_template('signup.html')

        cur.execute('''
            INSERT INTO teachers (name, email, password, max_hours_per_week)
            VALUES (%s, %s, %s, %s)
        ''', (name, email, hashed, max_hours))
        conn.commit()
        cur.close(); conn.close()

        flash("Signup successful!", "success")
        return redirect(url_for('auth.login'))

    return render_template('signup.html')


@auth_bp.route('/logout')
def logout(): session.clear(); return redirect(url_for('auth.login'))
