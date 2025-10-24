from db import db_cursor
from utils import FIXED_SLOTS, time_to_minutes
import random

def generate_timetable_for_course(course_id: int) -> int:
    """
    Auto-generation algorithm:
    - Fetch sections, subjects, teachers
    - Loop days and slots
    - Assign teachers randomly without overlaps
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

        # Fetch teachers for subjects
        teacher_map = {}
        for subj in subjects:
            cur.execute('SELECT teacher_id FROM teacher_subjects WHERE subject_id=%s', (subj['id'],))
            teacher_map[subj['id']] = [t['teacher_id'] for t in cur.fetchall()]
            if not teacher_map[subj['id']]:
                raise Exception(f"No teachers assigned to subject {subj['name']}")

        # Clear old timetable entries
        cur.execute(
            'DELETE t FROM timetable_entries t JOIN sections sec ON t.section_id=sec.id WHERE sec.course_id=%s',
            (course_id,)
        )

        entries = []
        assigned = set()    # Track (section_id, day, subject_id)
        occupied = set()    # Track (teacher_id, day, start_time)
        days = list(range(5))  # Monday-Friday

        for section_id in sections:
            for subj in subjects:
                random.shuffle(days)
                for day in days:
                    if (section_id, day, subj['id']) in assigned:
                        continue  # already scheduled

                    # Determine slot
                    if subj['is_lab']:
                        start, end = FIXED_SLOTS[4][0], FIXED_SLOTS[5][1]  # Afternoon lab
                    else:
                        # Pick a random available slot that no teacher is occupied
                        available_slots = [
                            slot for slot in FIXED_SLOTS
                            if all((tid, day, slot[0]) not in occupied for tid in teacher_map[subj['id']])
                        ]
                        if not available_slots:
                            continue
                        start, end = random.choice(available_slots)

                    # Pick a free teacher
                    random.shuffle(teacher_map[subj['id']])
                    teacher_id = None
                    for tid in teacher_map[subj['id']]:
                        if (tid, day, start) not in occupied:
                            teacher_id = tid
                            break
                    if teacher_id is None:
                        continue  # no free teacher for this slot

                    # Add entry
                    entries.append((section_id, subj['id'], teacher_id, day, start, end))
                    assigned.add((section_id, day, subj['id']))
                    occupied.add((teacher_id, day, start))
                    break  # move to next subject

        # Insert entries into DB
        for e in entries:
            cur.execute(
                'INSERT INTO timetable_entries (section_id,subject_id,teacher_id,day_of_week,start_time,end_time) '
                'VALUES (%s,%s,%s,%s,%s,%s)',
                e
            )

    return len(entries)
