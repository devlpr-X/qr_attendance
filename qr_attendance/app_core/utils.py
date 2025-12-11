# utils.py
import os
from django.db import connection
import urllib.parse
import hashlib
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def _get_semesters(semester_id):    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, school_year, term, start_date, end_date, name, school_id
            FROM semester
            WHERE id = %s
        """, [semester_id]) 
        sem = cursor.fetchone()
    semester = {
        'id': sem[0],
        'school_year': sem[1],
        'term': sem[2],
        'start_date': sem[3],
        'end_date': sem[4],
        'name': sem[5],
        'school_id': sem[6],
    }
    return semester

def _get_room_types():
    with connection.cursor() as cursor:
        cursor.execute(""" SELECT id, code, name FROM room_type """) 
        cr = cursor.fetchall()
    room_types =[]
    if cr:
        for room_type in cr:
            c = {
                'id': room_type[0],
                'code': room_type[1],
                'name': room_type[2]
            }
            room_types.append(c)
    return room_types

def _get_class_rooms(school_id):
    with connection.cursor() as cursor:
        cursor.execute(""" 
            SELECT id, school_id, room_number, room_type_id, capacity
	        FROM class_room
            WHERE school_id = %s
        """, [school_id]) 
        cr = cursor.fetchall()

    class_rooms =[]
    if cr:
        for class_room in cr:
            c = {
                'id': class_room[0],
                'school_id': class_room[1],
                'room_number': class_room[2],
                'room_type_id': class_room[3],
                'capacity': class_room[4]
            }
            class_rooms.append(c)
    return class_rooms

def _get_programs(school_id):
    with connection.cursor() as cursor:
        cursor.execute(""" 
            SELECT A.id, A.name, A.code
	        FROM program A
            INNER JOIN department B ON B.id = A.department_id
            WHERE school_id = %s
        """, [school_id]) 
        cr = cursor.fetchall()

    programs =[]
    if cr:
        for program in cr:
            c = {
                'id': program[0],
                'code': program[1],
                'name': program[2],
            }
            programs.append(c)
    return programs

def _get_class_groups(school_id, year):
    with connection.cursor() as cursor:
        cursor.execute(""" 
			SELECT C.id, C.name, C.program_id,
				COUNT(D.class_group_id) AS student_count
			FROM program A
			INNER JOIN department B ON B.id = A.department_id
			INNER JOIN class_group C ON C.program_id = A.id
			LEFT JOIN student_class_group D ON D.class_group_id = C.id
			WHERE B.school_id = %s AND C.year = %s
			GROUP BY C.id, C.name, C.program_id
        """, [school_id, year]) 
        cr = cursor.fetchall()

    class_groups =[]
    if cr:
        for class_group in cr:
            c = {
                'id': class_group[0],
                'name': class_group[1],
                'program_id': class_group[2],
                'student_count': class_group[3],
            }
            class_groups.append(c)
    return class_groups

def _get_current_semester_pattern(semester_id):
    # 2) Load existing patterns for this semester
    with connection.cursor() as cursor:
            cursor.execute("""
                SELECT csp.id,
                    c.name AS course_name, c.code AS course_code,
                    t.name AS teacher_name, csp.day_of_week,
                    (F.start_time::text || ' - ' || F.end_time::text) AS timeslot,
                    lt.value AS lesson_type_name,  l.name AS location_name,
                    csp.frequency, lt.id AS lesson_type_id,
                    csp.time_setting_id
                FROM course_schedule_pattern csp
                JOIN course c ON c.id = csp.course_id
                JOIN teacher_profile t ON t.id = csp.teacher_id
                LEFT JOIN location l ON l.id = csp.location_id
                LEFT JOIN lesson_type lt ON lt.id = csp.lesson_type_id
                LEFT JOIN time_setting  F  ON csp.time_setting_id = F.id
                WHERE csp.semester_id = %s
                ORDER BY csp.day_of_week, (F.start_time::text || ' - ' || F.end_time::text)
            """, [semester_id])
            rows = cursor.fetchall()


    # Normalize patterns to dicts for template
    patterns = []
    # day_of_week numeric still available; also include day name and day_of_week for timetable mapping
    day_names = ['Даваа', 'Мягмар', 'Лхагва', 'Пүрэв', 'Баасан', 'Бямба', 'Ням']
    for r in rows:
        p = {
            'id': r[0],
            'course': r[1],
            'course_code': r[2],
            'teacher': r[3],
            'day_of_week': r[4],
            'timeslot': r[5],
            'lesson_type_name': r[6],
            'location': r[7] or 'Заагаагүй',
            'frequency': r[8],
            'frequency_text': 'Долоо хоног бүр' if r[8] == 1 else f'{r[8]} долоо хоног тутам',
            'lesson_type_id': r[9],
            'time_setting_id': r[10]   
        }
        try:
            p['day'] = day_names[int(p['day_of_week'])]
        except Exception:
            p['day'] = str(p['day_of_week'])
        patterns.append(p)

    return patterns

def classify_flash(status):
    try:
        code = int(status)
        if 200 <= code <= 299:
            return "success"
        elif 300 <= code <= 399:
            return "warning"
        else:
            return "error"
    except:
        return "error"

def set_cookie_safe(response, key, value, max_age=None):
    encoded = urllib.parse.quote(str(value))
    response.set_cookie(key, encoded, max_age=max_age)

def get_cookie_safe(request, key, default=None):
    raw = request.COOKIES.get(key)
    return urllib.parse.unquote(raw) if raw else default

def _is_admin(request):
    role = request.COOKIES.get('role_name', '')
    return role.lower() == 'admin'

def _generate_password(length=10):
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def _hash_md5(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()
    
def query(sql, params=None, fetchone=False, fetchall=False, commit=False):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])

        if commit:
            return True
        if fetchone:
            return cursor.fetchone()
        if fetchall:
            return cursor.fetchall()

    return None


SCHOOL_EMAIL = os.environ.get("SCHOOL_EMAIL")
SCHOOL_PASSWORD = os.environ.get("SCHOOL_PASSWORD")


def send_school_email(to, subject, message, button_text=None, button_link=None):
    msg = MIMEMultipart("alternative")
    msg["From"] = f"QR Attendance System <{SCHOOL_EMAIL}>"
    msg["To"] = to
    msg["Subject"] = subject

    html = f"""
    <html>
    <body style="font-family:Arial; background:#f5f6f7; padding:20px;">
        <div style="max-width:500px; margin:auto; background:white; padding:25px;
                    border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
            
            <h2 style="color:#1d5ede; text-align:center; margin-bottom:20px;">
                {subject}
            </h2>

            <p style="font-size:15px; color:#333; line-height:1.6;">
                {message}
            </p>
    """

    if button_link and button_text:
        html += f"""
            <div style="text-align:center; margin-top:25px;">
                <a href="{button_link}"
                   style="background:#1d5ede; padding:12px 25px; color:white;
                          text-decoration:none; border-radius:5px; font-weight:bold;">
                   {button_text}
                </a>
            </div>
        """

    html += """
            <p style="font-size:12px; color:#777; margin-top:30px; text-align:center;">
                © 2025 School Attendance System. Бүх эрх хуулиар хамгаалагдсан.
            </p>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SCHOOL_EMAIL, SCHOOL_PASSWORD)
            server.sendmail(SCHOOL_EMAIL, to, msg.as_string())
    except Exception as e:
        print("EMAIL ERROR:", e)
