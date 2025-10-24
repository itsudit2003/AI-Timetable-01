from db import get_db
from werkzeug.security import generate_password_hash
from config import HOD_USERNAME, HOD_PASSWORD

CREATE_TABLES_SQL = [
    """CREATE TABLE IF NOT EXISTS teachers (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE,
        password VARCHAR(255) DEFAULT '',
        max_hours_per_week INT DEFAULT 20
    ) ENGINE=InnoDB;""",
    """CREATE TABLE IF NOT EXISTS hods (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE,
        password VARCHAR(255) NOT NULL
    ) ENGINE=InnoDB;""",
    """CREATE TABLE IF NOT EXISTS courses (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        degree VARCHAR(100)
    ) ENGINE=InnoDB;""",
    """CREATE TABLE IF NOT EXISTS sections (
        id INT AUTO_INCREMENT PRIMARY KEY,
        course_id INT NOT NULL,
        name VARCHAR(50),
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
    ) ENGINE=InnoDB;""",
    """CREATE TABLE IF NOT EXISTS subjects (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        course_id INT,
        is_lab BOOLEAN DEFAULT FALSE,
        default_duration_minutes INT DEFAULT 60,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL
    ) ENGINE=InnoDB;""",
    """CREATE TABLE IF NOT EXISTS teacher_subjects (
        teacher_id INT,
        subject_id INT,
        PRIMARY KEY (teacher_id, subject_id),
        FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
    ) ENGINE=InnoDB;""",
    """CREATE TABLE IF NOT EXISTS teacher_availability (
        id INT AUTO_INCREMENT PRIMARY KEY,
        teacher_id INT,
        day_of_week INT,
        start_time TIME,
        end_time TIME,
        FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
    ) ENGINE=InnoDB;""",
    """CREATE TABLE IF NOT EXISTS timetable_entries (
        id INT AUTO_INCREMENT PRIMARY KEY,
        section_id INT,
        subject_id INT,
        teacher_id INT,
        day_of_week INT,
        start_time TIME,
        end_time TIME,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL,
        FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE SET NULL
    ) ENGINE=InnoDB;"""
]

def init_db():
    conn = get_db()
    try:
        cur = conn.cursor()
        for sql in CREATE_TABLES_SQL:
            cur.execute(sql)
        cur.execute('SELECT id FROM hods WHERE email=%s', (HOD_USERNAME,))
        if not cur.fetchone():
            cur.execute('INSERT INTO hods (name,email,password) VALUES (%s,%s,%s)',
                        (HOD_USERNAME, HOD_USERNAME, generate_password_hash(HOD_PASSWORD)))
        conn.commit()
        cur.close()
    finally:
        conn.close()
