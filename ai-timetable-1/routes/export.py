from flask import Blueprint, request, send_file, flash, redirect, url_for
from db import db_cursor
from io import BytesIO
import pandas as pd
from utils import safe_fmt_time

export_bp = Blueprint('export', __name__, url_prefix='/export')

def export_timetable(entries, fmt='xlsx'):
    # Build a clean table for export
    day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    
    data = []
    for t in entries:
        day = day_names[t['day_of_week']] if t['day_of_week'] is not None else ''
        start = safe_fmt_time(t['start_time'])
        end = safe_fmt_time(t['end_time'])
        data.append({
            "Day": day,
            "Section": t.get('section_name',''),
            "Subject": t.get('subject_name',''),
            "Teacher": t.get('teacher_name',''),
            "Start": start,
            "End": end
        })

    df = pd.DataFrame(data)

    buf = BytesIO()
    fname = f"timetable.{fmt}"
    if fmt == 'csv':
        df.to_csv(buf, index=False)
        mimetype = 'text/csv'
    else:
        df.to_excel(buf, index=False)
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    buf.seek(0)
    return buf, mimetype, fname

@export_bp.route('/course/<int:course_id>')
def export_course(course_id):
    fmt = request.args.get('format','xlsx')
    with db_cursor() as cur:
        cur.execute('''SELECT t.*, s.name AS subject_name, sec.name AS section_name, th.name AS teacher_name
                       FROM timetable_entries t
                       LEFT JOIN subjects s ON t.subject_id=s.id
                       LEFT JOIN sections sec ON t.section_id=sec.id
                       LEFT JOIN teachers th ON t.teacher_id=th.id
                       WHERE sec.course_id=%s''', (course_id,))
        entries = cur.fetchall()

    if not entries:
        flash("No timetable entries found for export","warning")
        return redirect(url_for('admin.view_timetable'))

    # --- Sort by day and start_time like view ---
    day_order = {'Monday':0,'Tuesday':1,'Wednesday':2,'Thursday':3,'Friday':4,'Saturday':5,'Sunday':6}
    def safe_minutes(val):
        val_str = safe_fmt_time(val)
        from utils import time_to_minutes
        return time_to_minutes(val_str) if val_str else 0
    entries.sort(key=lambda t: (day_order.get(["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"][t['day_of_week']],7),
                                safe_minutes(t['start_time'])))

    buf, mimetype, fname = export_timetable(entries, fmt)
    return send_file(buf, mimetype=mimetype, as_attachment=True, download_name=fname)
