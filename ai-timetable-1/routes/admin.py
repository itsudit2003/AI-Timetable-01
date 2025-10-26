from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import db_cursor
from functools import wraps
from utils import safe_fmt_time
from gemini import build_prompt_from_constraints, call_gemini, parse_gemini_output, validate_entries
from utils import FIXED_SLOTS
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

# ✅ Add Course (single route for GET + POST)
@admin_bp.route('/courses/add', methods=['GET', 'POST'])
@hod_required
def add_course():
    if request.method == 'POST':
        name = request.form.get('name')
        degree = request.form.get('degree')
        if not name:
            flash("Course name is required", "danger")
            return redirect(url_for('admin.add_course'))

        with db_cursor(commit=True) as cur:
            cur.execute('INSERT INTO courses (name, degree) VALUES (%s, %s)', (name, degree))
        flash("Course added successfully", "success")
        return redirect(url_for('admin.courses'))

    # show form (reuse edit template or separate)
    return render_template('courses_edit.html', course={'name': '', 'degree': ''})

# ✅ Edit Course
@admin_bp.route('/courses/edit/<int:course_id>', methods=['GET', 'POST'])
@hod_required
def edit_course(course_id):
    with db_cursor() as cur:
        if request.method == 'POST':
            name = request.form.get('name')
            degree = request.form.get('degree')

            cur.execute(
                'UPDATE courses SET name=%s, degree=%s WHERE id=%s',
                (name, degree, course_id)
            )

            # ✅ Ensure the transaction is committed
            cur._connection.commit()

            flash("Course updated successfully", "success")
            return redirect(url_for('admin.courses'))

        # Fetch course details for edit page
        cur.execute('SELECT * FROM courses WHERE id=%s', (course_id,))
        course = cur.fetchone()

    if not course:
        flash("Course not found", "danger")
        return redirect(url_for('admin.courses'))

    return render_template('courses_edit.html', course=course)


# ✅ Delete Course
@admin_bp.route('/courses/delete/<int:course_id>', methods=['POST', 'GET'])
@hod_required
def delete_course(course_id):
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM courses WHERE id = %s", (course_id,))
    flash("Course deleted successfully!", "success")
    return redirect(url_for('admin.courses'))

# --- SECTIONS ---
@admin_bp.route('/sections')
@hod_required
def sections():
    with db_cursor() as cur:
        # Fetch all courses first
        cur.execute('SELECT * FROM courses')
        courses = cur.fetchall()

        # Fetch sections joined with course names
        cur.execute('''SELECT s.id, s.name, c.name AS course_name, s.course_id
                       FROM sections s
                       JOIN courses c ON s.course_id = c.id''')
        sections = cur.fetchall()

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
@admin_bp.route('/sections/edit/<int:section_id>', methods=['POST'])
@hod_required
def edit_section(section_id):
    name = request.form.get('name')
    course_id = request.form.get('course_id')
    if not name or not course_id:
        flash("All fields are required", "danger")
        return redirect(url_for('admin.sections'))

    with db_cursor(commit=True) as cur:
        cur.execute('UPDATE sections SET name = %s, course_id = %s WHERE id = %s', (name, course_id, section_id))

    flash("Section updated successfully", "success")
    return redirect(url_for('admin.sections'))


@admin_bp.route('/sections/delete/<int:section_id>', methods=['POST'])
@hod_required
def delete_section(section_id):
    with db_cursor(commit=True) as cur:
        cur.execute('DELETE FROM sections WHERE id = %s', (section_id,))
    flash("Section deleted successfully", "success")
    return redirect(url_for('admin.sections'))


# --- SUBJECTS ---
@admin_bp.route('/subjects')
@hod_required
def subjects():
    with db_cursor() as cur:
        # Fetch subjects with course names
        cur.execute('''
            SELECT s.id, s.name, s.is_lab, s.default_duration_minutes, s.course_id, c.name AS course_name
            FROM subjects s LEFT JOIN courses c ON s.course_id=c.id
            ORDER BY s.id
        ''')
        subjects = cur.fetchall()

        # Fetch courses for dropdowns
        cur.execute('SELECT id, name FROM courses ORDER BY name')
        courses = cur.fetchall()

    return render_template('subjects.html', subjects=subjects, courses=courses)


@admin_bp.route('/subjects/add', methods=['POST'])
@hod_required
def add_subject():
    name = request.form.get('name')
    course_id = request.form.get('course_id')
    is_lab = int(request.form.get('is_lab', 0))
    duration = int(request.form.get('duration') or 60)

    if not name or not course_id:
        flash("All fields are required", "danger")
        return redirect(url_for('admin.subjects'))

    with db_cursor(commit=True) as cur:
        cur.execute(
            'INSERT INTO subjects (name, course_id, is_lab, default_duration_minutes) VALUES (%s,%s,%s,%s)',
            (name, course_id, is_lab, duration)
        )
    flash("Subject added successfully", "success")
    return redirect(url_for('admin.subjects'))


@admin_bp.route('/subjects/edit/<int:subject_id>', methods=['GET', 'POST'])
@hod_required
def edit_subject(subject_id):
    if request.method == 'POST':
        name = request.form.get('name')
        course_id = request.form.get('course_id')
        is_lab = int(request.form.get('is_lab', 0))
        duration = int(request.form.get('duration') or 60)

        # ✅ Commit the update properly
        with db_cursor(commit=True) as cur:
            cur.execute(
                'UPDATE subjects SET name=%s, course_id=%s, is_lab=%s, default_duration_minutes=%s WHERE id=%s',
                (name, course_id, is_lab, duration, subject_id)
            )

        flash("Subject updated successfully", "success")
        return redirect(url_for('admin.subjects'))

    # GET: fetch subject and courses
    with db_cursor() as cur:
        cur.execute('SELECT * FROM subjects WHERE id=%s', (subject_id,))
        subject = cur.fetchone()
        cur.execute('SELECT id, name FROM courses ORDER BY name')
        courses = cur.fetchall()

    return render_template('subjects_edit.html', subject=subject, courses=courses)


@admin_bp.route('/subjects/delete/<int:subject_id>', methods=['POST'])
@hod_required
def delete_subject(subject_id):
    with db_cursor(commit=True) as cur:
        cur.execute('DELETE FROM subjects WHERE id=%s', (subject_id,))
    flash("Subject deleted successfully", "success")
    return redirect(url_for('admin.subjects'))


# --- ASSIGN SUBJECTS TO TEACHERS ---
@admin_bp.route('/assign')
@hod_required
def assign():
    with db_cursor() as cur:
        cur.execute('SELECT id, name FROM teachers')
        teachers = cur.fetchall()

        cur.execute('''
            SELECT s.id, s.name, c.name AS course_name, c.id AS course_id
            FROM subjects s
            JOIN courses c ON s.course_id = c.id
        ''')
        subjects = cur.fetchall()

        cur.execute('''
            SELECT sec.id, sec.name, c.name AS course_name, c.id AS course_id
            FROM sections sec
            JOIN courses c ON sec.course_id = c.id
        ''')
        sections = cur.fetchall()

        # ✅ Fix: No ts.id since teacher_subjects may not have it
        cur.execute('''
    SELECT 
        ts.teacher_id,
        ts.subject_id,
        t.name AS teacher_name,
        s.name AS subject_name,
        c.name AS course_name,
        GROUP_CONCAT(DISTINCT sec.name SEPARATOR ', ') AS section_names
    FROM teacher_subjects ts
    JOIN teachers t ON ts.teacher_id = t.id
    JOIN subjects s ON ts.subject_id = s.id
    JOIN courses c ON s.course_id = c.id
    LEFT JOIN sections sec ON sec.id = ts.section_id
    GROUP BY ts.teacher_id, ts.subject_id, t.name, s.name, c.name
    ORDER BY t.name
''')

        assignments = cur.fetchall()

    return render_template(
        'assign.html',
        teachers=teachers,
        subjects=subjects,
        sections=sections,
        assignments=assignments
    )


# ✅ POST: assign subject to teacher
@admin_bp.route('/assign', methods=['POST'])
@hod_required
def do_assign():
    teacher_id = request.form.get('teacher_id')
    subject_ids = request.form.getlist('subject_ids')  # list of selected subjects
    section_ids = request.form.getlist('section_ids')  # list of selected sections

    if not teacher_id or not subject_ids or not section_ids:
        flash("Please select a teacher, at least one subject, and at least one section", "danger")
        return redirect(url_for('admin.assign'))

    with db_cursor(commit=True) as cur:
        for subject_id in subject_ids:
            for section_id in section_ids:
                cur.execute(
                    'INSERT IGNORE INTO teacher_subjects (teacher_id, subject_id, section_id) VALUES (%s, %s, %s)',
                    (teacher_id, subject_id, section_id)
                )

    flash("Subjects assigned successfully!", "success")
    return redirect(url_for('admin.assign'))

# ✅ DELETE an assignment
@admin_bp.route('/assign/delete/<int:teacher_id>/<int:subject_id>', methods=['POST'])
@hod_required
def delete_assignment(teacher_id, subject_id):
    with db_cursor(commit=True) as cur:
        cur.execute(
            'DELETE FROM teacher_subjects WHERE teacher_id = %s AND subject_id = %s',
            (teacher_id, subject_id)
        )
    flash("Assignment deleted successfully!", "success")
    return redirect(url_for('admin.assign'))

# --- Edit an Assignment ---
@admin_bp.route('/assign/edit/<int:teacher_id>/<int:subject_id>', methods=['GET', 'POST'])
@hod_required
def edit_assignment(teacher_id, subject_id):
    with db_cursor() as cur:
        # Fetch teachers, subjects, sections for form
        cur.execute('SELECT id, name FROM teachers')
        teachers = cur.fetchall()
        cur.execute('''
            SELECT s.id, s.name, c.name AS course_name
            FROM subjects s
            JOIN courses c ON s.course_id=c.id
        ''')
        subjects = cur.fetchall()
        cur.execute('SELECT sec.id, sec.name, c.name AS course_name FROM sections sec JOIN courses c ON sec.course_id=c.id')
        sections = cur.fetchall()

        # GET: load current sections for this assignment
        cur.execute('SELECT section_id FROM teacher_subjects WHERE teacher_id=%s AND subject_id=%s',
                    (teacher_id, subject_id))
        current_sections = [r['section_id'] for r in cur.fetchall()]

        if request.method == 'POST':
            # POST: update assignment
            new_section_ids = request.form.getlist('section_ids')
            if not new_section_ids:
                flash("Select at least one section", "danger")
                return redirect(url_for('admin.edit_assignment', teacher_id=teacher_id, subject_id=subject_id))

            with db_cursor(commit=True) as cur2:
                cur2.execute('DELETE FROM teacher_subjects WHERE teacher_id=%s AND subject_id=%s',
                             (teacher_id, subject_id))
                for sec_id in new_section_ids:
                    cur2.execute('INSERT INTO teacher_subjects (teacher_id, subject_id, section_id) VALUES (%s,%s,%s)',
                                 (teacher_id, subject_id, sec_id))
            flash("Assignment updated successfully!", "success")
            return redirect(url_for('admin.assign'))

    return render_template(
        'assign_edit.html',
        teacher_id=teacher_id,
        subject_id=subject_id,
        teachers=teachers,
        subjects=subjects,
        sections=sections,
        current_sections=current_sections
    )
@admin_bp.route('/assign/edit/<int:teacher_id>/<int:subject_id>', methods=['POST'])
@hod_required
def update_assignment(teacher_id, subject_id):
    # Multi-select section IDs
    new_section_ids = request.form.getlist('section_ids')  

    if not new_section_ids:
        flash("Select at least one section", "danger")
        return redirect(url_for('admin.edit_assignment', teacher_id=teacher_id, subject_id=subject_id))

    with db_cursor(commit=True) as cur:
        # Delete old assignments
        cur.execute(
            'DELETE FROM teacher_subjects WHERE teacher_id=%s AND subject_id=%s',
            (teacher_id, subject_id)
        )
        # Insert new assignments
        for sec_id in new_section_ids:
            cur.execute(
                'INSERT INTO teacher_subjects (teacher_id, subject_id, section_id) VALUES (%s, %s, %s)',
                (teacher_id, subject_id, sec_id)
            )

    flash("Assignment updated successfully!", "success")
    return redirect(url_for('admin.assign'))  # Back to main assign page


# --- GENERATE TIMETABLE ---
@admin_bp.route('/generate', methods=['GET','POST'])
@hod_required
def generate():
    timetable = None
    course_id = None

    # Fetch courses for dropdown
    with db_cursor() as cur:
        cur.execute('SELECT * FROM courses')
        courses = cur.fetchall()

    if request.method == 'POST':
        course_id = request.form.get('course_id')
        if course_id:
            try:
                # Fetch course constraints (sections, subjects, teachers)
                with db_cursor() as cur:
                    # Sections
                    cur.execute('SELECT id FROM sections WHERE course_id=%s', (course_id,))
                    sections = [s['id'] for s in cur.fetchall()]
                    if not sections:
                        raise Exception("No sections found for this course")

                    # Subjects
                    cur.execute('SELECT * FROM subjects WHERE course_id=%s', (course_id,))
                    subjects = cur.fetchall()
                    if not subjects:
                        raise Exception("No subjects found for this course")

                    # Teachers per subject
                    teacher_map = {}
                    for subj in subjects:
                        cur.execute('SELECT teacher_id FROM teacher_subjects WHERE subject_id=%s', (subj['id'],))
                        t_list = [t['teacher_id'] for t in cur.fetchall()]
                        if not t_list:
                            raise Exception(f"No teachers assigned to subject {subj['name']}")
                        teacher_map[subj['id']] = t_list

                # Build prompt for Gemini
                constraints = {
                    "sections": sections,
                    "subjects": subjects,
                    "teacher_map": teacher_map
                }
                from config import FIXED_SLOTS
                prompt = build_prompt_from_constraints(constraints, fixed_slots=FIXED_SLOTS)

                # Call Gemini
                raw_output = call_gemini(prompt)
                entries = parse_gemini_output(raw_output)
                valid_entries = validate_entries(entries)

                if not valid_entries:
                    raise Exception("No valid timetable entries generated by Gemini")

                # Insert into DB
                with db_cursor(commit=True) as cur:
                    # Delete old timetable for this course
                    cur.execute(
                        'DELETE t FROM timetable_entries t '
                        'JOIN sections sec ON t.section_id=sec.id '
                        'WHERE sec.course_id=%s',
                        (course_id,)
                    )

                    for e in valid_entries:
                        cur.execute(
                            'INSERT INTO timetable_entries '
                            '(section_id, subject_id, teacher_id, day_of_week, start_time, end_time) '
                            'VALUES (%s,%s,%s,%s,%s,%s)',
                            (
                                e['section_id'], e['subject_id'], e['teacher_id'],
                                e['day_of_week'], e['start_time'], e['end_time']
                            )
                        )

                # Fetch timetable entries for display
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

                # Pre-format times and sort by day/slot
                for t in timetable:
                    t['start_time_str'] = safe_fmt_time(t['start_time'])
                    t['end_time_str'] = safe_fmt_time(t['end_time'])

                timetable.sort(key=lambda x: (x['day_of_week'], x['start_time']))

                flash(f"Timetable generated successfully with ({len(valid_entries)} entries).", "success")

            except Exception as e:
                flash(f"Error generating timetable: {e}", "danger")

    return render_template('generate.html', courses=courses, timetable=timetable)

# --- VIEW TIMETABLE ---
@admin_bp.route('/view_timetable', methods=['GET', 'POST'])
@hod_required
def view_timetable():
    timetable = []
    courses = []
    selected_course_id = None

    with db_cursor() as cur:
        cur.execute('SELECT id, name FROM courses')
        courses = cur.fetchall()

        if request.method == 'POST':
            selected_course_id = int(request.form.get('course_id'))
            cur.execute('''SELECT t.*, s.name AS subject_name, sec.name AS section_name, th.name AS teacher_name
                           FROM timetable_entries t
                           LEFT JOIN subjects s ON t.subject_id=s.id
                           LEFT JOIN sections sec ON t.section_id=sec.id
                           LEFT JOIN teachers th ON t.teacher_id=th.id
                           WHERE sec.course_id=%s''', (selected_course_id,))
            timetable = cur.fetchall()

    # Sort timetable by day_of_week and start_time
    from utils import safe_fmt_time, time_to_minutes
    day_order = {'Monday':0,'Tuesday':1,'Wednesday':2,'Thursday':3,'Friday':4,'Saturday':5,'Sunday':6}
    day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

    def safe_minutes(val):
        val_str = safe_fmt_time(val)
        return time_to_minutes(val_str) if val_str else 0

    timetable.sort(key=lambda t: (day_order.get(day_names[t['day_of_week']],7), safe_minutes(t['start_time'])))

    for e in timetable:
        e['start_time'] = safe_fmt_time(e['start_time'])
        e['end_time'] = safe_fmt_time(e['end_time'])

    return render_template('timetable_view.html', courses=courses, timetable=timetable, selected_course_id=selected_course_id)
