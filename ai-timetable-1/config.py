import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24)
DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
DB_PORT = int(os.environ.get('DB_PORT', 3306))
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASS = os.environ.get('DB_PASS', '')
DB_NAME = os.environ.get('DB_NAME', 'timetabledb')

HOD_USERNAME = os.environ.get('HOD_USERNAME', 'hod')
HOD_PASSWORD = os.environ.get('HOD_PASSWORD', 'hodpass')

GEMINI_API_URL = os.getenv("GEMINI_API_URL", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

FIXED_SLOTS = [
    ("09:10", "10:00"), ("10:00", "10:50"), ("10:50", "11:40"),
    ("11:40", "12:30"), ("13:30", "14:30"), ("14:30", "15:20"),
    ("15:20", "16:10"), ("16:10", "17:00")
]

# Configure Gemini model
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        GEMINI_MODEL = genai.GenerativeModel("models/gemini-2.0-flash")
    except Exception:
        GEMINI_MODEL = None
else:
    GEMINI_MODEL = None
