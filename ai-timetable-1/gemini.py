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
    - Fixed lecture slots
    - Lab rules
    - No overlaps
    - Lunch break respected
    - Output JSON array only
    """
    fixed_slots = fixed_slots or []

    prompt_lines = [
        "You are an assistant that creates college timetables with fixed lecture slots and flexible lab timings.",
        "OUTPUT FORMAT: JSON array of entries with keys: section_id, subject_id, teacher_id, day_of_week (0=Mon), start_time, end_time.",
        "Rules:",
        "- Lectures must strictly follow these 50-minute slots (no recess):",
        json.dumps(fixed_slots, indent=2),
        "- Labs must last exactly 120 minutes but cannot overlap lunch/recess (12:30–13:30).",
        "- No teacher or section can have overlapping sessions.",
        "- Schedule only between 09:00–17:00 Monday to Friday.",
        "- Maintain lunch break 12:30–13:30 free for everyone.",
        "- Balance the workload through the week.",
        "Input constraints:",
        json.dumps(constraints, indent=2, default=sanitize_constraints),
        "Return ONLY valid JSON array (no markdown, no explanation).",
        "IMPORTANT: Do NOT schedule anything between 12:30 and 13:30. Skip this period entirely.",
        "Use only the fixed lecture slots above. Labs can start at any valid time outside the lunch period."
    ]
    return "\n".join(prompt_lines)
