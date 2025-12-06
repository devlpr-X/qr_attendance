from django.shortcuts import render, redirect
from django.db import connection
from django.utils import timezone
from datetime import timedelta


# ---------------------------------------------------
# 1) БАГШИЙН ДАШБОРД (ХИЧЭЭЛҮҮД)
# ---------------------------------------------------
def teacher_dashboard(request):
    # ------------------------------
    # 1) Тухайн багшийн user_id → teacher_profile.id
    # ------------------------------
    teacher_user_id = request.COOKIES.get("user_id")

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, name 
            FROM teacher_profile
            WHERE user_id = %s
        """, [teacher_user_id])
        r = cursor.fetchone()

    if not r:
        return render(request, "teacher/teacher_dashboard.html", {
            "error": "Багшийн мэдээлэл олдсонгүй."
        })

    teacher_id = r[0]
    teacher_name = r[1]

    # ------------------------------
    # 2) Он / семестр сонголт (GET)
    # ------------------------------
    year = request.GET.get("year")
    term = request.GET.get("term")

    # Default year & term
    now = timezone.now()
    if not year:
        year = now.year

    if not term:
        # 1–6 → 2-р семестр, 7–12 → 1-р семестр
        term = 2 if now.month <= 7 else 1

    # ------------------------------
    # 3) Тухайн он/семестр → semester.id олж авах
    # ------------------------------
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id 
            FROM semester
            WHERE school_year = %s AND term = %s
            ORDER BY id DESC LIMIT 1
        """, [year, term])
        sem = cursor.fetchone()

    if not sem:
        return render(request, "teacher/teacher_dashboard.html", {
            "error": "Энэ он/семестрт хичээл олдсонгүй.",
            "year": year,
            "term": term,
            "patterns": [],
            "timeslots": []
        })

    semester_id = sem[0]

    # ------------------------------
    # 4) Цагийн слот (time_setting)
    # ------------------------------
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name, value 
            FROM time_setting
            ORDER BY id
        """)
        times = cursor.fetchall()

    timeslots = [{"name": t[0], "slot": t[1]} for t in times]


    # ------------------------------
    # 5) Хуваарь (course_schedule_pattern)
    # ------------------------------
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                csp.id,
                c.name AS course_name,
                c.code AS course_code,
                csp.day_of_week,
                csp.timeslot,
                lt.value AS lesson_type,
                l.name AS location,
                lt.id AS lesson_type_id,
                l.id AS location_id,
                c.id AS course_id,
                csp.teacher_id,
                csp.semester_id,
                csp.time_setting_id,
                s.school_year, 
                s.term
            FROM course_schedule_pattern csp
            JOIN course c ON c.id = csp.course_id
            LEFT JOIN lesson_type lt ON lt.id = csp.lesson_type_id
            LEFT JOIN location l ON l.id = csp.location_id
            LEFT JOIN semester s ON s.id = csp.semester_id
            WHERE csp.teacher_id = %s
              AND csp.semester_id = %s
            ORDER BY csp.day_of_week, csp.timeslot
        """, [teacher_id, semester_id])

        rows = cursor.fetchall()

    patterns = []
    week = ["Даваа", "Мягмар", "Лхагва", "Пүрэв", "Баасан", "Бямба", "Ням"]

    for r in rows:
        patterns.append({
            "id": r[0],
            "course": r[1],
            "course_code": r[2],
            "day_of_week": r[3],
            "day": week[r[3]] if 0 <= r[3] <= 6 else r[3],
            "timeslot": r[4],
            "lesson_type": r[5] or "",
            "location": r[6] or "Хаана гэдэггүй",
            "lesson_type_id": r[7],
            "location_id": r[8],
            "course_id": r[9],
            "teacher_id": r[10],
            "semester_id": r[11],
            "time_setting_id": r[12],
            "school_year": r[13],
            "term": r[14]
        })

    return render(request, "teacher/teacher_dashboard.html", {
        "teacher_name": teacher_name,
        "year": year,
        "term": term,
        "patterns": patterns,
        "timeslots": timeslots,
    })



# ---------------------------------------------------
# 2) БАГШИЙН ХУВААРЬ (Pattern list)
# ---------------------------------------------------
def teacher_schedule_list(request):

    teacher_user_id = request.COOKIES.get("user_id")

    # teacher_profile ID
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM teacher_profile WHERE user_id = %s", [teacher_user_id])
        t = cursor.fetchone()
    if not t:
        return render(request, "teacher/schedule_list.html", {"patterns": []})
    teacher_id = t[0]

    # Patterns
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                p.id,
                c.name AS course_name,
                c.code AS course_code,
                p.day_of_week,
                p.timeslot,
                lt.value AS lesson_type,
                p.frequency
            FROM course_schedule_pattern p
            JOIN course c ON c.id = p.course_id
            JOIN lesson_type lt ON lt.id = p.lesson_type_id
            WHERE p.teacher_id = %s
            ORDER BY p.day_of_week, p.timeslot
        """, [teacher_id])
        rows = cursor.fetchall()

    patterns = [{
        "id": r[0],
        "course": r[1],
        "code": r[2],
        "day": r[3],
        "timeslot": r[4],
        "type": r[5],
        "freq": r[6]
    } for r in rows]

    return render(request, "teacher/schedule_list.html", {
        "patterns": patterns
    })


# ---------------------------------------------------
# 3) QR ҮҮСГЭХ БОЛОМЖТОЙ ХИЧЭЭЛҮҮД (Pattern list)
# ---------------------------------------------------
def teacher_session_generate_list(request):

    teacher_user_id = request.COOKIES.get("user_id")

    # teacher_profile.id
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM teacher_profile WHERE user_id=%s", [teacher_user_id])
        t = cursor.fetchone()

    if not t:
        return render(request, "teacher/session_generate_list.html", {"patterns": []})

    teacher_id = t[0]

    # Patterns
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                p.id,
                c.name,
                c.code,
                p.day_of_week,
                p.timeslot,
                lt.value AS lesson_type
            FROM course_schedule_pattern p
            JOIN course c ON c.id = p.course_id
            JOIN lesson_type lt ON lt.id = p.lesson_type_id
            WHERE p.teacher_id = %s
            ORDER BY c.name
        """, [teacher_id])
        rows = cursor.fetchall()

    patterns = [{
        "id": r[0],
        "course": r[1],
        "code": r[2],
        "day": r[3],
        "timeslot": r[4],
        "lesson_type": r[5],
    } for r in rows]

    return render(request, "teacher/session_generate_list.html", {
        "patterns": patterns
    })


# ---------------------------------------------------
# 4) БАГШИЙН ҮҮСГЭСЭН БҮХ SESSION (history)
# ---------------------------------------------------
def teacher_sessions_history(request):

    teacher_user_id = request.COOKIES.get("user_id")

    # teacher_profile.id
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM teacher_profile WHERE user_id=%s", [teacher_user_id])
        t = cursor.fetchone()
    if not t:
        return render(request, "teacher/sessions_history.html", {"sessions": []})

    teacher_id = t[0]

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                s.id,
                c.name,
                s.date,
                ts.name AS timeslot_name,
                lt.value AS lesson_type,
                s.token,
                s.expires_at
            FROM class_session s
            JOIN course c ON c.id = s.course_id
            JOIN time_setting ts ON ts.id = s.time_setting_id
            JOIN lesson_type lt ON lt.id = s.lesson_type_id
            WHERE s.teacher_id = %s
            ORDER BY s.created_at DESC
        """, [teacher_id])

        rows = cursor.fetchall()

    sessions = [{
        "id": r[0],
        "course": r[1],
        "date": r[2],
        "timeslot": r[3],
        "lesson_type": r[4],
        "token": r[5],
        "expires": r[6]
    } for r in rows]

    return render(request, "teacher/sessions_history.html", {
        "sessions": sessions
    })
