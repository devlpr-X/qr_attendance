# app_core/views/sessions.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from ..utils import _is_admin, set_cookie_safe
from io import BytesIO
import base64, datetime, qrcode

def dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]

# Admin: sessions list
def sessions_list(request):
    if not _is_admin(request):
        return redirect('login')

    today = datetime.date.today()

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT cs.id, cs.course_id, c.name AS course_name, c.code AS course_code,
                   cs.date, cs.timeslot, cs.lesson_type, cs.teacher_id, cs.location_id, cs.token
            FROM class_session cs
            JOIN course c ON c.id = cs.course_id
            ORDER BY cs.date DESC, cs.timeslot, cs.id DESC
            LIMIT 500
        """)
        rows = cursor.fetchall()

    # Build sessions list and collect teacher ids
    sessions = []
    teacher_ids = set()
    for r in rows:
        teacher_id = r[7]
        if teacher_id:
            teacher_ids.add(teacher_id)

        sessions.append({
            "id": r[0],
            "course_id": r[1],
            "course_name": r[2],
            "course_code": r[3],
            "date": r[4],
            "timeslot": r[5],
            "lesson_type": r[6],
            "teacher_id": teacher_id,
            "location_id": r[8],
            "token": r[9],
            "teacher_name": None  # will fill below
        })

    # Fetch teacher names map
    if teacher_ids:
        with connection.cursor() as cursor:
            # teacher_profile.user_id is app_user.id
            cursor.execute("""
                SELECT user_id, name FROM teacher_profile
                WHERE user_id = ANY(%s)
            """, [list(teacher_ids)])
            rows = cursor.fetchall()
        teacher_map = {r[0]: r[1] for r in rows}
    else:
        teacher_map = {}

    # attach teacher_name into sessions
    for s in sessions:
        s['teacher_name'] = teacher_map.get(s['teacher_id'], None)

    return render(request, 'admin/sessions/list.html', {
        'sessions': sessions,
        'today': today
    })

# Admin/Teacher: create session
def session_add(request):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, code FROM course ORDER BY name")
        courses = dictfetchall(cursor)

        cursor.execute("SELECT id, name FROM location ORDER BY name")
        locations = dictfetchall(cursor)

        cursor.execute("SELECT value, name FROM ref_constant WHERE type='timeslot' ORDER BY value")
        timeslots = dictfetchall(cursor)

        cursor.execute("SELECT value, name FROM ref_constant WHERE type='lesson_type' ORDER BY name")
        lesson_types = dictfetchall(cursor)

        cursor.execute("SELECT id, name FROM teacher_profile ORDER BY name")
        teachers = dictfetchall(cursor)

    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        date = request.POST.get('date')
        timeslot = request.POST.get('timeslot')
        lesson_type = request.POST.get('lesson_type')
        teacher_id = request.POST.get('teacher_id') or request.COOKIES.get('user_id')
        location_id = request.POST.get('location_id') or None

        if not (course_id and date and timeslot and lesson_type):
            return render(request, 'admin/sessions/add.html', {
                'courses': courses,
                'locations': locations,
                'timeslots': timeslots,
                'lesson_types': lesson_types,
                'teachers': teachers,
                'error': 'Заавал бөглөх шаардлагатай талбар байна.'
            })

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO class_session (course_id, teacher_id, location_id, date, timeslot, lesson_type, token, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, gen_random_uuid(), now()) RETURNING id, token
                    """, [course_id, teacher_id, location_id, date, timeslot, lesson_type])
                    r = cursor.fetchone()
                    new_id = r[0]
                    token = r[1]

            response = redirect('sessions_list')
            set_cookie_safe(response, 'flash_msg', 'Session амжилттай үүслээ', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response
        except Exception as e:
            return render(request, 'admin/sessions/add.html', {
                'courses': courses,
                'locations': locations,
                'timeslots': timeslots,
                'lesson_types': lesson_types,
                'teachers': teachers,
                'error': str(e)
            })

    return render(request, 'admin/sessions/add.html', {
        'courses': courses,
        'locations': locations,
        'timeslots': timeslots,
        'lesson_types': lesson_types,
        'teachers': teachers
    })


# View single session (show QR)
# View single session (show QR) — full names included
def session_view(request, session_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                cs.id,
                cs.course_id,
                c.name AS course_name,
                c.code AS course_code,
                cs.date,
                cs.timeslot,
                cs.lesson_type,
                cs.teacher_id,
                t.name AS teacher_name,
                cs.location_id,
                l.name AS location_name,
                cs.token
            FROM class_session cs
            JOIN course c ON c.id = cs.course_id
            LEFT JOIN teacher_profile t ON t.user_id = cs.teacher_id
            LEFT JOIN location l ON l.id = cs.location_id
            WHERE cs.id = %s
        """, [session_id])
        r = cursor.fetchone()

    if not r:
        response = redirect('sessions_list')
        set_cookie_safe(response, 'flash_msg', 'Session олдсонгүй', 6)
        set_cookie_safe(response, 'flash_status', 404, 6)
        return response

    session = {
        'id': r[0],
        'course_id': r[1],
        'course_name': r[2],
        'course_code': r[3],
        'date': r[4],
        'timeslot': r[5],
        'lesson_type': r[6],
        'teacher_id': r[7],
        'teacher_name': r[8],
        'location_id': r[9],
        'location_name': r[10],
        'token': r[11]
    }

    # generate QR (link to scan page)
    qr_url = f"http://127.0.0.1:8000/attendance/{session['token']}/scan"
    qr = qrcode.make(qr_url)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_b64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, 'admin/sessions/view.html', {'session': session, 'qr_b64': qr_b64})
