# app_core/views/teacher_schedule.py

from django.shortcuts import render, redirect
from django.db import connection
from django.utils import timezone

def teacher_schedules_list(request):
    teachers = []
    semesters = []

    # Load teachers
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM teacher_profile ORDER BY name")
        teachers = cursor.fetchall()

    # Load semesters
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, school_year, term FROM semester ORDER BY school_year DESC, term DESC")
        semesters = cursor.fetchall()

    # When selected → load schedules
    schedules = []
    teacher_id = request.GET.get("teacher_id")
    sem_id = request.GET.get("semester_id")

    if teacher_id and sem_id:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    p.id,
                    c.name,
                    c.code,
                    p.day_of_week,
                    p.timeslot,
                    lt.value AS lesson_type,
                    l.name AS location
                FROM course_schedule_pattern p
                JOIN course c ON c.id = p.course_id
                LEFT JOIN lesson_type lt ON lt.id = p.lesson_type_id
                LEFT JOIN location l ON l.id = p.location_id
                WHERE p.teacher_id = %s AND p.semester_id = %s
                ORDER BY p.day_of_week, p.timeslot
            """, [teacher_id, sem_id])

            rows = cursor.fetchall()

        schedules = [
            {
                'id': r[0],
                'course': r[1],
                'course_code': r[2],
                'day': r[3],
                'timeslot': r[4],
                'lesson_type': r[5],
                'location': r[6],
            }
            for r in rows
        ]

    return render(request, "teacher/schedules_list.html", {
        "teachers": teachers,
        "semesters": semesters,
        "selected_teacher": teacher_id,
        "selected_semester": sem_id,
        "schedules": schedules
    })
def teacher_session_view(request, pattern_id):
    # Load pattern details
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT p.id, c.name, c.code, t.name AS teacher, lt.value AS lesson_type,
                   l.name AS location, p.timeslot, p.day_of_week, p.course_id,
                   p.teacher_id, p.lesson_type_id, p.location_id
            FROM course_schedule_pattern p
            JOIN course c ON c.id = p.course_id
            JOIN teacher_profile t ON t.id = p.teacher_id
            LEFT JOIN lesson_type lt ON lt.id = p.lesson_type_id
            LEFT JOIN location l ON l.id = p.location_id
            WHERE p.id = %s
        """, [pattern_id])
        row = cursor.fetchone()

    if not row:
        return render(request, "404.html")

    pattern = {
        "id": row[0],
        "course": row[1],
        "course_code": row[2],
        "teacher": row[3],
        "lesson_type": row[4],
        "location": row[5],
        "timeslot": row[6],
        "day": row[7],
        "course_id": row[8],
        "teacher_id": row[9],
        "lesson_type_id": row[10],
        "location_id": row[11],
    }

    return render(request, "teacher/session_generate.html", {
        "pattern": pattern
    })
import uuid

def generate_qr_session(request, pattern_id):
    if request.method != "POST":
        return redirect("teacher_session_view", pattern_id=pattern_id)

    token = uuid.uuid4()
    expires = timezone.now() + timezone.timedelta(minutes=10)

    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO class_session
            (teacher_id, course_id, location_id, lesson_type_id, time_setting_id, token, expires_at)
            SELECT teacher_id, course_id, location_id, lesson_type_id, 
                   (SELECT id FROM time_setting LIMIT 1),
                   %s, %s
            FROM course_schedule_pattern WHERE id=%s
            RETURNING id
        """, [str(token), expires, pattern_id])

        session_id = cursor.fetchone()[0]

    return redirect("teacher_qr_display", session_id=session_id)
import qrcode
from io import BytesIO
import base64

def teacher_qr_display(request, session_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT token, expires_at FROM class_session WHERE id=%s", [session_id])
        row = cursor.fetchone()

    token, expires_at = row

    qr_data = f"{request.build_absolute_uri('/')[:-1]}/attendance/check/?token={token}"
    img = qrcode.make(qr_data)
    buffer = BytesIO()
    img.save(buffer, format="PNG")

    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, "teacher/qr_display.html", {
        "qr": qr_base64,
        "expires_at": expires_at,
        "token": token
    })

# app_core/views/teacher_qr.py

import qrcode
import base64
from io import BytesIO
from django.shortcuts import render, redirect
from django.db import connection
from django.utils import timezone
from app_core.utils import set_cookie_safe


def session_qr_display(request, session_id):
    """
    Нэг Session-ийн QR болон дэлгэрэнгүй мэдээллийг харуулах
    Багш болон Админ хоёуланд ажиллана.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                cs.id,
                cs.token,
                cs.date,
                cs.expires_at,

                c.id AS course_id,
                c.name AS course_name,
                c.code AS course_code,

                t.id AS teacher_id,
                t.name AS teacher_name,

                lt.name AS lesson_type_name,

                ts.name AS time_name,
                ts.start_time,
                ts.end_time,

                l.id AS location_id,
                l.name AS location_name

            FROM class_session cs
            JOIN course c ON c.id = cs.course_id
            JOIN teacher_profile t ON t.id = cs.teacher_id
            JOIN lesson_type lt ON lt.id = cs.lesson_type_id
            JOIN time_setting ts ON ts.id = cs.time_setting_id
            LEFT JOIN location l ON l.id = cs.location_id
            WHERE cs.id = %s
        """, [session_id])

        row = cursor.fetchone()

    if not row:
        response = redirect('teacher_sessions_history')
        set_cookie_safe(response, "flash_msg", "Session олдсонгүй", 4)
        set_cookie_safe(response, "flash_status", 404, 4)
        return response

    session = {
        "id": row[0],
        "token": row[1],
        "date": row[2],
        "expires_at": row[3],

        "course_id": row[4],
        "course_name": row[5],
        "course_code": row[6],

        "teacher_id": row[7],
        "teacher_name": row[8],

        "lesson_type": row[9],

        "time_name": row[10],
        "start_time": row[11],
        "end_time": row[12],

        "location_id": row[13],
        "location_name": row[14],
    }

    # -----------------------------
    # ⚠️ Token → QR Image Encode
    # -----------------------------
    base_url = "http://127.0.0.1:8000"     # production дээр env-ээр солино
    qr_url = f"{base_url}/attendance/{session['token']}/scan"

    qr = qrcode.make(qr_url)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_b64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, "teacher/qr_display.html", {
        "session": session,
        "qr_b64": qr_b64,
        "qr_url": qr_url,
        "now": timezone.now()
    })
