from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import db_cursor
from functools import wraps
from utils import safe_fmt_time
from timetable import generate_timetable_for_course

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# --- HOD access decorator ---
def hod_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'hod':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

# --- Admin Home ---
@admin_bp.route('/')
@hod_required
def admin():
    return render_template('admin.html', user=session.get('user'))

# --- COURSES ---
@admin_bp.route('/courses')
@hod_required
def courses():
    with db_cursor() as cur:
        cur.execute('SELECT * FROM courses')
        courses = cur.fetchall()
    return render_template('courses.html', courses=courses)

@admin_bp.route('/courses/add', methods=['GET'])
@hod_required
def add_course_form():
    return render_template('course_add.html')

@admin_bp.route('/courses/add', methods=['POST'])
@hod_required
def add_course():
    name = request.form.get('name')
    degree = request.form.get('degree')
    if not name:
        flash("Course name is required", "danger")
        return redirect(url_for('admin.add_course_form'))
    with db_cursor(commit=True) as cur:
        cur.execute('INSERT INTO courses (name, degree) VALUES (%s, %s)', (name, degree))
    flash("Course added successfully", "success")
    return redirect(url_for('admin.courses'))

@admin_bp.route('/courses/edit/<int:course_id>', methods=['GET','POST'])
@hod_required
def edit_course(course_id):
    with db_cursor() as cur:
        if request.method == 'POST':
            name = request.form.get('name')
            degree = request.form.get('degree')
            cur.execute('UPDATE courses SET name=%s, degree=%s WHERE id=%s', (name, degree, course_id))
            cur.connection.commit()
            flash("Course updated successfully","success")
            return redirect(url_for('admin.courses'))
        cur.execute('SELECT * FROM courses WHERE id=%s', (course_id,))
        course = cur.fetchone()
    return render_template('course_edit.html', course=course)

@admin_bp.route('/courses/delete/<int:course_id>')
@hod_required
def delete_course(course_id):
    with db_cursor(commit=True) as cur:
        cur.execute('DELETE FROM courses WHERE id=%s', (course_id,))
    flash("Course deleted successfully","success")
    return redirect(url_for('admin.courses'))

# --- SECTIONS ---
@admin_bp.route('/sections')
@hod_required
def sections():
    with db_cursor() as cur:
        cur.execute('''SELECT s.id, s.name, c.name AS course_name, s.course_id
                       FROM sections s JOIN courses c ON s.course_id=c.id''')
        sections = cur.fetchall()
        cur.execute('SELECT * FROM courses')
        courses = cur.fetchall()
    return render_template('sections.html', sections=sections, courses=courses)

@admin_bp.route('/sections/add', methods=['POST'])
@hod_required
def add_section():
    name = request.form.get('name')
    course_id = request.form.get('course_id')
    if not name or not course_id:
        flash("All fields are required","danger")
        return redirect(url_for('admin.sections'))
    with db_cursor(commit=True) as cur:
        cur.execute('INSERT INTO sections (name, course_id) VALUES (%s, %s)', (name, course_id))
    flash("Section added successfully","success")
    return redirect(url_for('admin.sections'))

@admin_bp.route('/sections/delete/<int:section_id>')
@hod_required
def delete_section(section_id):
    with db_cursor(commit=True) as cur:
        cur.execute('DELETE FROM sections WHERE id=%s', (section_id,))
    flash("Section deleted successfully","success")
    return redirect(url_for('admin.sections'))

# --- SUBJECTS ---
@admin_bp.route('/subjects')
@hod_required
def subjects():
    with db_cursor() as cur:
        cur.execute('''SELECT s.id, s.name, s.is_lab, s.default_duration_minutes, s.course_id, c.name AS course_name
                       FROM subjects s LEFT JOIN courses c ON s.course_id=c.id''')
        subjects = cur.fetchall()
        cur.execute('SELECT * FROM courses')
        courses = cur.fetchall()
    return render_template('subjects.html', subjects=subjects, courses=courses)

@admin_bp.route('/subjects/add', methods=['POST'])
@hod_required
def add_subject():
    name = request.form.get('name')
    course_id = request.form.get('course_id')
    is_lab = bool(request.form.get('is_lab'))
    duration = int(request.form.get('duration') or 60)
    if not name:
        flash("Subject name is required","danger")
        return redirect(url_for('admin.subjects'))
    with db_cursor(commit=True) as cur:
        cur.execute('INSERT INTO subjects (name, course_id, is_lab, default_duration_minutes) VALUES (%s,%s,%s,%s)',
                    (name, course_id, is_lab, duration))
    flash("Subject added successfully","success")
    return redirect(url_for('admin.subjects'))

@admin_bp.route('/subjects/delete/<int:subject_id>')
@hod_required
def delete_subject(subject_id):
    with db_cursor(commit=True) as cur:
        cur.execute('DELETE FROM subjects WHERE id=%s', (subject_id,))
    flash("Subject deleted successfully","success")
    return redirect(url_for('admin.subjects'))

# --- ASSIGN SUBJECTS TO TEACHERS ---
@admin_bp.route('/assign')
@hod_required
def assign():
    with db_cursor() as cur:
        cur.execute('SELECT id, name FROM teachers')
        teachers = cur.fetchall()
        cur.execute('SELECT id, name FROM subjects')
        subjects = cur.fetchall()
    return render_template('assign.html', teachers=teachers, subjects=subjects)

@admin_bp.route('/assign', methods=['POST'])
@hod_required
def do_assign():
    teacher_id = request.form.get('teacher_id')
    subject_ids = request.form.getlist('subject_ids')
    with db_cursor(commit=True) as cur:
        for sid in subject_ids:
            cur.execute('INSERT IGNORE INTO teacher_subjects (teacher_id, subject_id) VALUES (%s,%s)', (teacher_id, sid))
    flash("Subjects assigned successfully","success")
    return redirect(url_for('admin.assign'))

# --- GENERATE TIMETABLE ---
@admin_bp.route('/generate', methods=['GET','POST'])
@hod_required
def generate():
    timetable = None  # always define
    course_id = None  # initialize

    # Fetch all courses for the dropdown
    with db_cursor() as cur:
        cur.execute('SELECT * FROM courses')
        courses = cur.fetchall()

    if request.method == 'POST':
        course_id = request.form.get('course_id')
        if course_id:
            try:
                # Generate timetable for the selected course
                count = generate_timetable_for_course(course_id)
                flash(f"Timetable generated successfully ({count} entries)","success")
            except Exception as e:
                flash(f"Error: {e}","danger")

    # Fetch timetable entries if course_id is set (after POST)
    if course_id:
        with db_cursor() as cur:
            cur.execute('''
                SELECT t.*, s.name AS subject_name, sec.name AS section_name, th.name AS teacher_name
                FROM timetable_entries t
                LEFT JOIN subjects s ON t.subject_id=s.id
                LEFT JOIN sections sec ON t.section_id=sec.id
                LEFT JOIN teachers th ON t.teacher_id=th.id
                WHERE sec.course_id=%s
            ''', (course_id,))
            timetable = cur.fetchall()
            for e in timetable:
                e['start_time'] = safe_fmt_time(e['start_time'])
                e['end_time'] = safe_fmt_time(e['end_time'])

    return render_template('generate.html', courses=courses, timetable=timetable)



# --- VIEW TIMETABLE ---
@admin_bp.route('/timetable/<int:course_id>')
@hod_required
def view_timetable(course_id):
    with db_cursor() as cur:
        cur.execute('''SELECT t.*, s.name AS subject_name, sec.name AS section_name, th.name AS teacher_name
                       FROM timetable_entries t
                       LEFT JOIN subjects s ON t.subject_id=s.id
                       LEFT JOIN sections sec ON t.section_id=sec.id
                       LEFT JOIN teachers th ON t.teacher_id=th.id
                       WHERE sec.course_id=%s''', (course_id,))
        entries = cur.fetchall()
    for e in entries:
        e['start_time'] = safe_fmt_time(e['start_time'])
        e['end_time'] = safe_fmt_time(e['end_time'])
    return render_template('timetable_view.html', entries=entries)
