from flask import Blueprint, redirect, render_template, session, url_for
from db import db_cursor
from functools import wraps
from utils import safe_fmt_time

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

def teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'teacher':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@teacher_bp.route('/')
@teacher_required
def teacher_dashboard():
    teacher_id = session.get('teacher_id')
    with db_cursor() as cur:
        cur.execute('''
            SELECT t.day_of_week, sec.name AS section_name, s.name AS subject_name,
                   t.start_time, t.end_time
            FROM timetable_entries t
            LEFT JOIN subjects s ON t.subject_id=s.id
            LEFT JOIN sections sec ON t.section_id=sec.id
            WHERE t.teacher_id=%s
            ORDER BY t.day_of_week, t.start_time, sec.name
        ''', (teacher_id,))
        rows = cur.fetchall()

    # Map days
    day_map = {0:'Monday', 1:'Tuesday', 2:'Wednesday', 3:'Thursday', 4:'Friday', 5:'Saturday', 6:'Sunday'}
    
    # Organize into dict: section -> day -> list of entries
    timetable = {}
    for r in rows:
        sec = r['section_name']
        day = day_map.get(r['day_of_week'], r['day_of_week'])
        if sec not in timetable:
            timetable[sec] = {}
        if day not in timetable[sec]:
            timetable[sec][day] = []
        timetable[sec][day].append({
            'subject_name': r['subject_name'],
            'start_time': safe_fmt_time(r['start_time']),
            'end_time': safe_fmt_time(r['end_time'])
        })

    # Get sorted list of days for table header
    all_days = [day_map[d] for d in range(5)]  # Mon-Fri

    return render_template('teacher_dashboard.html', timetable=timetable, days=all_days)
