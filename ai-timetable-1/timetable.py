from db import db_cursor
from utils import FIXED_SLOTS, time_to_minutes
import random

def generate_timetable_for_course(course_id: int) -> int:
    """
    Auto-generation algorithm:
    - Fetch sections, subjects, teachers
    - Loop days and slots
    - Assign teachers without overlaps
    - Dynamic lab scheduling
    """
    with db_cursor(commit=True) as cur:
        # Fetch sections
        cur.execute('SELECT id FROM sections WHERE course_id=%s', (course_id,))
        sections = [s['id'] for s in cur.fetchall()]
        if not sections:
            raise Exception("No sections found")

        # Fetch subjects
        cur.execute('SELECT * FROM subjects WHERE course_id=%s', (course_id,))
        subjects = cur.fetchall()
        if not subjects:
            raise Exception("No subjects found")

        # Map subjects to teachers
        teacher_map = {}
        for subj in subjects:
            cur.execute('SELECT teacher_id FROM teacher_subjects WHERE subject_id=%s', (subj['id'],))
            teacher_map[subj['id']] = [t['teacher_id'] for t in cur.fetchall()]
            if not teacher_map[subj['id']]:
                raise Exception(f"No teachers assigned to subject {subj['name']}")

        # Clear old timetable entries
        cur.execute(
            'DELETE t FROM timetable_entries t '
            'JOIN sections sec ON t.section_id=sec.id '
            'WHERE sec.course_id=%s',
            (course_id,)
        )

        entries = []
        teacher_schedule = {}  # (teacher_id, day) -> list of (start,end)
        section_schedule = {}  # (section_id, day) -> list of (start,end)
        days = list(range(5))  # Monday-Friday

        for section_id in sections:
            for subj in subjects:
                random.shuffle(days)
                scheduled = False

                for day in days:
                    # Prepare schedules
                    t_key = (subj['id'], day)  # temp for checking teachers
                    section_key = (section_id, day)
                    teacher_schedule.setdefault(day, {})
                    section_schedule.setdefault(day, {})
                    section_schedule.setdefault(section_key, [])
                    
                    # Determine slots
                    if subj['is_lab']:
                        # pick any 120-min slot outside lunch (12:30-13:30)
                        possible_slots = []
                        for slot_start, slot_end in FIXED_SLOTS:
                            slot_start_min = time_to_minutes(slot_start)
                            slot_end_min = time_to_minutes(slot_end)
                            # lab needs 120 min
                            lab_end = slot_start_min + 120
                            # skip if overlaps lunch
                            if not (lab_end <= 750 or slot_start_min >= 810):  # 12:30-13:30 = 750-810
                                continue
                            # check teacher availability
                            for tid in teacher_map[subj['id']]:
                                teacher_schedule.setdefault(tid, {}).setdefault(day, [])
                                conflict = any(
                                    not (lab_end <= s or slot_start_min >= e)
                                    for s, e in teacher_schedule[tid][day]
                                )
                                if conflict:
                                    continue
                                possible_slots.append((slot_start_min, lab_end, tid))
                        if not possible_slots:
                            continue
                        start_min, end_min, teacher_id = random.choice(possible_slots)
                    else:
                        # Theory: pick any FIXED_SLOT where teacher free
                        possible_slots = []
                        for slot_start, slot_end in FIXED_SLOTS:
                            start_min = time_to_minutes(slot_start)
                            end_min = time_to_minutes(slot_end)
                            for tid in teacher_map[subj['id']]:
                                teacher_schedule.setdefault(tid, {}).setdefault(day, [])
                                section_schedule.setdefault((section_id, day), [])
                                # check teacher overlap
                                t_conflict = any(not (end_min <= s or start_min >= e)
                                                 for s, e in teacher_schedule[tid][day])
                                # check section overlap
                                s_conflict = any(not (end_min <= s or start_min >= e)
                                                 for s, e in section_schedule[(section_id, day)])
                                if not t_conflict and not s_conflict:
                                    possible_slots.append((start_min, end_min, tid))
                        if not possible_slots:
                            continue
                        start_min, end_min, teacher_id = random.choice(possible_slots)

                    # Save entry
                    entries.append((section_id, subj['id'], teacher_id, day, start_min, end_min))
                    # Update schedules
                    teacher_schedule[teacher_id][day].append((start_min, end_min))
                    section_schedule[(section_id, day)].append((start_min, end_min))
                    scheduled = True
                    break  # move to next subject

        # Insert entries into DB
        for section_id, subj_id, teacher_id, day, start_min, end_min in entries:
            cur.execute(
                'INSERT INTO timetable_entries (section_id,subject_id,teacher_id,day_of_week,start_time,end_time) '
                'VALUES (%s,%s,%s,%s,%s,%s)',
                (section_id, subj_id, teacher_id, day,
                 f"{start_min//60:02d}:{start_min%60:02d}:00",
                 f"{end_min//60:02d}:{end_min%60:02d}:00")
            )

    return len(entries)
