import json
import io
import pandas as pd
from config import GEMINI_MODEL
from utils import sanitize_constraints

def call_gemini(prompt: str):
    """
    Call Gemini model with a prompt and safely extract raw text.
    Returns None on failure.
    """
    if not GEMINI_MODEL:
        return None
    try:
        resp = GEMINI_MODEL.generate_content(contents=prompt)
        # Extract text safely from response
        text = getattr(resp, 'text', None)
        if not text and isinstance(resp, dict):
            text = resp.get('text', str(resp))
        return text or None
    except Exception as e:
        print(f"[Gemini] Error: {e}")
        return None

def parse_gemini_output(text: str):
    """
    Parse Gemini output to a list of dict entries.
    Handles JSON, CSV, markdown fences, nested keys.
    Deduplicates entries automatically.
    Returns None if parsing fails.
    """
    if not text:
        return None

    text = text.strip()

    # Remove markdown fences
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1].strip() if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:].strip()

    parsed = None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            pass
        elif isinstance(parsed, dict):
            # Try common wrapper keys
            for k in ("timetable", "result", "data", "output", "items"):
                if k in parsed and isinstance(parsed[k], list):
                    parsed = parsed[k]
                    break
            else:
                parsed = [parsed]  # wrap single dict
        else:
            parsed = None
    except Exception:
        parsed = None

    # Fallback to CSV parsing
    if parsed is None:
        try:
            parsed = pd.read_csv(io.StringIO(text)).to_dict(orient='records')
        except Exception:
            return None

    if not parsed:
        return None

    # Deduplicate exact entries
    unique_entries = [dict(t) for t in {tuple(sorted(e.items())) for e in parsed}]
    return unique_entries

def validate_entries(entries: list):
    """
    Validate Gemini output entries for:
    - No overlaps for teachers or sections
    - Day and time correctness
    Returns only valid entries
    """
    if not entries:
        return []

    # Track teacher/section schedule
    teacher_schedule = {}
    section_schedule = {}
    valid_entries = []

    for e in entries:
        try:
            teacher_id = e['teacher_id']
            section_id = e['section_id']
            day = e['day_of_week']
            start = e['start_time']
            end = e['end_time']

            # Skip invalid or missing data
            if None in (teacher_id, section_id, day, start, end):
                continue

            # Skip lunch period
            if start < "12:30:00" < end or start < "13:30:00" < end:
                continue

            # Check teacher overlap
            t_key = (teacher_id, day)
            s_key = (section_id, day)
            teacher_schedule.setdefault(t_key, [])
            section_schedule.setdefault(s_key, [])

            overlap = lambda st, en, intervals: any(not (en <= i[0] or st >= i[1]) for i in intervals)

            if overlap(start, end, teacher_schedule[t_key]):
                continue
            if overlap(start, end, section_schedule[s_key]):
                continue

            # No overlaps → accept
            teacher_schedule[t_key].append((start, end))
            section_schedule[s_key].append((start, end))
            valid_entries.append(e)
        except Exception:
            continue

    return valid_entries

def build_prompt_from_constraints(constraints: dict, fixed_slots=None):
    """
    Build detailed prompt for Gemini:
    - Fixed lecture slots (50 min)
    - Labs 100 min fully before or after lunch
    - No overlaps
    - Lunch break 12:30–13:30 respected
    - Output JSON array only
    """
    fixed_slots = fixed_slots or []

    prompt_lines = [
        "You are an assistant that creates college timetables.",
        "OUTPUT FORMAT: JSON array of entries with keys:",
        "section_id, subject_id, teacher_id, day_of_week (0=Mon), start_time, end_time.",
        "RULES:",
        "- Lectures must strictly follow these 50-minute slots (no splitting, no overlaps):",
        json.dumps(fixed_slots, indent=2),
        "- Labs must last exactly 100 minutes and must fully fit either before lunch (before 12:30) or after lunch (after 13:30). Do NOT split labs across lunch.",
        "- No teacher or section can have overlapping sessions.",
        "- Schedule only between 09:10–17:00 Monday to Friday.",
        "- Lunch break 12:30–13:30 must be free for everyone.",
        "- Balance the workload through the week as evenly as possible.",
        "Input constraints:",
        json.dumps(constraints, indent=2),
        "Return ONLY valid JSON array (no markdown, no explanation).",
        "IMPORTANT:",
        "- Labs cannot start before lunch and end after lunch.",
        "- Use only the fixed lecture slots above for lectures.",
        "- Labs can start at any valid time outside lunch but must fully fit 100 minutes."
    ]

    return "\n".join(prompt_lines)
