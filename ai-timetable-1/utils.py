from datetime import datetime, time, timedelta
import io, pandas as pd, json
from config import FIXED_SLOTS

def safe_time_to_str(val):
    if isinstance(val, str):
        if val in ('0 day', '0:00:00', None):
            return ""
        return val[:5]
    if isinstance(val, (datetime, time)):
        return val.strftime("%H:%M")
    if isinstance(val, timedelta):
        total_seconds = int(val.total_seconds())
        return f"{total_seconds//3600:02d}:{(total_seconds%3600)//60:02d}"
    return ""

def safe_fmt_time(val):
    return safe_time_to_str(val)

def parse_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

def time_to_minutes(t: str) -> int:
    hh, mm = map(int, t.split(':')[:2])
    return hh*60 + mm

def is_valid_slot(start: str, end: str, duration: int, is_lab=False) -> bool:
    smin, emin = time_to_minutes(start), time_to_minutes(end)
    if smin < 750 < emin or smin < 810 < emin:  # lunch
        return False
    if not is_lab and (start, end) in FIXED_SLOTS and duration == 50:
        return True
    if is_lab:
        afternoon_slots = FIXED_SLOTS[4:]
        for i in range(len(afternoon_slots)-1):
            slot1, slot2 = afternoon_slots[i], afternoon_slots[i+1]
            if smin == time_to_minutes(slot1[0]) and emin == time_to_minutes(slot2[1]):
                return True
    return False

def sanitize_constraints(obj):
    if isinstance(obj, timedelta):
        return str(obj)
    if isinstance(obj, time):
        return obj.strftime("%H:%M")
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

def export_dataframe(rows, fmt='csv', filename_prefix='hod_timetable'):
    for r in rows:
        r['start_time'] = safe_fmt_time(r.get('start_time'))
        r['end_time'] = safe_fmt_time(r.get('end_time'))

    df = pd.DataFrame(rows)
    df['Day'] = df['day_of_week'].apply(lambda x:['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'][x])
    df['Slot'] = df['start_time']+' - '+df['end_time']
    df['Section'] = df['section_name'].str.upper()
    df['Subject'] = df['subject_name'].str.title()
    df['Teacher'] = df['teacher_name'].str.title()
    df = df[['Day','Slot','Section','Subject','Teacher']]
    day_order={'Monday':0,'Tuesday':1,'Wednesday':2,'Thursday':3,'Friday':4,'Saturday':5,'Sunday':6}
    df['day_order'] = df['Day'].map(day_order)
    df = df.sort_values(by=['day_order','Slot','Section']).drop(columns=['day_order'])

    buf = io.BytesIO()
    download_name = f"{filename_prefix}.{fmt}"

    if fmt=='csv':
        csv_buf = io.StringIO()
        df.to_csv(csv_buf,index=False)
        csv_buf.seek(0)
        buf.write(csv_buf.getvalue().encode('utf-8'))
        buf.seek(0)
        mimetype = 'text/csv'
    elif fmt=='xlsx':
        with pd.ExcelWriter(buf,engine='openpyxl') as writer:
            df.to_excel(writer,index=False,sheet_name='Timetable')
        buf.seek(0)
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        return None,f"Unsupported format: {fmt}"

    return buf,mimetype,download_name
