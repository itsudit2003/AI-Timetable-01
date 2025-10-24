from flask import Blueprint, request, send_file, flash, redirect, url_for
from db import db_cursor
from utils import export_dataframe

export_bp = Blueprint('export', __name__, url_prefix='/export')

@export_bp.route('/course/<int:course_id>')
def export_course(course_id):
    fmt = request.args.get('format','csv')
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
        return redirect(url_for('admin.admin'))
    buf, mimetype, fname = export_dataframe(entries, fmt=fmt)
    return send_file(buf, mimetype=mimetype, as_attachment=True, download_name=fname)
