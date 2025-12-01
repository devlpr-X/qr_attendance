# FILE: app_core/views/session_attendance.py
# Place this file into your app_core/views/ directory.

import uuid
import base64
from io import BytesIO
from datetime import timedelta
from django.shortcuts import render, redirect, HttpResponse
from django.db import connection, transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.http import JsonResponse
from ..utils import _is_admin, set_cookie_safe
import qrcode  # ensure `qrcode` package installed (pip install qrcode[pil])


# 1) page to show pattern details and Generate button
@csrf_protect
def session_generate(request, pattern_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT p.id, c.name, c.code, t.name AS teacher, p.day_of_week, p.timeslot,
                   lt.value AS lesson_type, l.name AS location, p.course_id, p.teacher_id,
                   p.lesson_type_id, p.location_id
            FROM course_schedule_pattern p
            JOIN course c ON c.id = p.course_id
            JOIN teacher_profile t ON t.id = p.teacher_id
            LEFT JOIN lesson_type lt ON lt.id = p.lesson_type_id
            LEFT JOIN location l ON l.id = p.location_id
            WHERE p.id = %s
        """, [pattern_id])
        row = cursor.fetchone()

    if not row:
        r = redirect('teacher_dashboard')
        set_cookie_safe(r, 'flash_msg', 'Pattern олдсонгүй', 5)
        set_cookie_safe(r, 'flash_status', 404, 5)
        return r

    pattern = {
        'id': row[0],
        'course': row[1],
        'course_code': row[2],
        'teacher': row[3],
        'day_of_week': row[4],
        'timeslot': row[5],
        'lesson_type': row[6],
        'location': row[7],
        'course_id': row[8],
        'teacher_id': row[9],
        'lesson_type_id': row[10],
        'location_id': row[11],
    }

    return render(request, 'teacher/session_generate.html', {'pattern': pattern})


# 2) POST: create class_session with 10 minute expiry and redirect to QR display
@csrf_protect
def generate_qr_session(request, pattern_id):
    if not _is_admin(request):
        return redirect('login')
    if request.method != 'POST':
        return redirect('session_generate', pattern_id=pattern_id)

    # create token and expiry
    token = str(uuid.uuid4())
    expires_at = timezone.now() + timedelta(minutes=10)

    # Build insert based on pattern, resolve time_setting_id by matching timeslot -> to_char(start_time,'HH24:MI')||'-'||to_char(end_time,'HH24:MI')
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                # find pattern row (also validate)
                cursor.execute("""
                    SELECT teacher_id, course_id, location_id, lesson_type_id, timeslot
                    FROM course_schedule_pattern WHERE id=%s
                """, [pattern_id])
                row = cursor.fetchone()
                if not row:
                    r = redirect('teacher_dashboard')
                    set_cookie_safe(r, 'flash_msg', 'Pattern алга болсон', 5)
                    set_cookie_safe(r, 'flash_status', 404, 5)
                    return r

                teacher_id, course_id, location_id, lesson_type_id, timeslot = row

                # try to find matching time_setting id by timeslot string
                cursor.execute("""
                    SELECT id FROM time_setting
                    WHERE (to_char(start_time,'HH24:MI') || '-' || to_char(end_time,'HH24:MI')) = %s
                    LIMIT 1
                """, [timeslot])
                trow = cursor.fetchone()
                if trow:
                    time_setting_id = trow[0]
                else:
                    # fallback: pick any time_setting for the location or any if none
                    if location_id:
                        cursor.execute("SELECT id FROM time_setting WHERE location_id=%s LIMIT 1", [location_id])
                        trow = cursor.fetchone()
                    if not trow:
                        cursor.execute("SELECT id FROM time_setting LIMIT 1")
                        trow = cursor.fetchone()
                    if not trow:
                        # cannot create session without time_setting
                        r = redirect('session_generate', pattern_id=pattern_id)
                        set_cookie_safe(r, 'flash_msg', 'Цагийн слот олдсонгүй. Time setting нэмнэ үү.', 6)
                        set_cookie_safe(r, 'flash_status', 500, 6)
                        return r
                    time_setting_id = trow[0]

                # insert into class_session
                cursor.execute("""
                    INSERT INTO class_session
                        (teacher_id, course_id, location_id, lesson_type_id, time_setting_id, token, expires_at, date, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,CURRENT_DATE,now())
                    RETURNING id
                """, [teacher_id, course_id, location_id, lesson_type_id, time_setting_id, token, expires_at])
                session_id = cursor.fetchone()[0]

        return redirect('teacher_qr_display', session_id=session_id)

    except Exception as e:
        r = redirect('session_generate', pattern_id=pattern_id)
        set_cookie_safe(r, 'flash_msg', f'Сесс үүсгэх үед алдаа: {str(e)}', 6)
        set_cookie_safe(r, 'flash_status', 500, 6)
        return r


# 3) QR display: show QR image + expiry countdown
def teacher_qr_display(request, session_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT token, expires_at, course_id, teacher_id, location_id
            FROM class_session WHERE id=%s
        """, [session_id])
        row = cursor.fetchone()
    if not row:
        r = redirect('teacher_dashboard')
        set_cookie_safe(r, 'flash_msg', 'Session олдсонгүй', 5)
        set_cookie_safe(r, 'flash_status', 404, 5)
        return r

    token, expires_at, course_id, teacher_id, location_id = row
    # Build attendance check URL
    base = request.build_absolute_uri('/')[:-1]
    attendance_url = f"{base}/attendance/check/?token={token}"

    # generate QR image base64
    qr = qrcode.QRCode(border=1)
    qr.add_data(attendance_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode()

    return render(request, 'teacher/qr_display.html', {
        'qr_base64': b64,
        'expires_at': expires_at,
        'attendance_url': attendance_url,
        'session_id': session_id,
        'token': token
    })


# 4) attendance_check: public endpoint to verify token and return session meta
def attendance_check(request):
    token = request.GET.get('token')
    if not token:
        return JsonResponse({'ok': False, 'error': 'token шаардлагатай'}, status=400)

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT cs.id, cs.expires_at, cs.is_cancelled,
                   c.name AS course_name, c.code AS course_code,
                   t.name AS teacher_name,
                   (to_char(ts.start_time,'HH24:MI') || '-' || to_char(ts.end_time,'HH24:MI')) AS slot,
                   l.name AS location_name
            FROM class_session cs
            JOIN course c ON c.id = cs.course_id
            JOIN teacher_profile t ON t.id = cs.teacher_id
            LEFT JOIN time_setting ts ON ts.id = cs.time_setting_id
            LEFT JOIN location l ON l.id = cs.location_id
            WHERE cs.token = %s
            LIMIT 1
        """, [token])
        row = cursor.fetchone()

    if not row:
        return JsonResponse({'ok': False, 'error': 'Token олдсонгүй'}, status=404)

    session_id, expires_at, is_cancelled, course_name, course_code, teacher_name, slot, location_name = row
    now = timezone.now()
    if is_cancelled:
        return JsonResponse({'ok': False, 'error': 'Сесс цуцлагдсан'}, status=400)
    if expires_at and expires_at < now:
        return JsonResponse({'ok': False, 'error': 'Token хугацаа дууссан'}, status=400)

    return JsonResponse({
        'ok': True,
        'session_id': session_id,
        'course_name': course_name,
        'course_code': course_code,
        'teacher_name': teacher_name,
        'slot': slot,
        'location': location_name,
        'expires_at': expires_at.isoformat()
    })


# 5) attendance_mark API — create attendance row (public)
@csrf_exempt
def attendance_mark(request):
    # Accept JSON or form POST
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST шаардлагатай'}, status=405)

    token = request.POST.get('token') or (request_json(request).get('token') if request.content_type.startswith('application/json') else None)
    student_code = request.POST.get('student_code') or request.POST.get('student_id') or (request_json(request).get('student_code') if request.content_type.startswith('application/json') else None)
    status_val = request.POST.get('status') or (request_json(request).get('status') if request.content_type.startswith('application/json') else None)
    device_id = request.POST.get('device_id') or (request_json(request).get('device_id') if request.content_type.startswith('application/json') else None)
    device_info = request.POST.get('device_info') or (request_json(request).get('device_info') if request.content_type.startswith('application/json') else None)
    lat = request.POST.get('lat') or (request_json(request).get('lat') if request.content_type.startswith('application/json') else None)
    lon = request.POST.get('lon') or (request_json(request).get('lon') if request.content_type.startswith('application/json') else None)

    if not token or not student_code:
        return JsonResponse({'ok': False, 'error': 'token болон student_code/ student_id шаардлагатай'}, status=400)

    # resolve session
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, expires_at, is_cancelled FROM class_session WHERE token=%s LIMIT 1", [token])
        srow = cursor.fetchone()
    if not srow:
        return JsonResponse({'ok': False, 'error': 'Token олдсонгүй'}, status=404)
    session_id, expires_at, is_cancelled = srow
    if is_cancelled:
        return JsonResponse({'ok': False, 'error': 'Сесс цуцлагдсан'}, status=400)
    if expires_at and expires_at < timezone.now():
        return JsonResponse({'ok': False, 'error': 'Token хугацаа дууссан'}, status=400)

    # resolve student id by code or accept numeric id
    student_id = None
    try:
        # if numeric id provided
        if str(student_code).isdigit():
            student_id = int(student_code)
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM student WHERE id=%s LIMIT 1", [student_id])
                if not cursor.fetchone():
                    student_id = None
        if not student_id:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM student WHERE student_code=%s OR full_name ILIKE %s LIMIT 1", [student_code, student_code])
                s = cursor.fetchone()
                if s:
                    student_id = s[0]
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Оюутан олж чадсангүй'}, status=404)

    if not student_id:
        return JsonResponse({'ok': False, 'error': 'Student олдсонгүй'}, status=404)

    # prevent duplicate attendance for same session & student (optional)
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM attendance WHERE session_id=%s AND student_id=%s LIMIT 1", [session_id, student_id])
        if cursor.fetchone():
            return JsonResponse({'ok': False, 'error': 'Энэ оюутан аль хэдийн бүртгэгдсэн'}, status=409)

    # insert attendance
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO attendance
                (session_id, student_id, timestamp, lat, lon, success, note, device_id, device_info, status)
                VALUES (%s, %s, now(), %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, [
                session_id, student_id,
                lat or None, lon or None,
                True, None,
                device_id or None, device_info or None,
                status_val or 'present'
            ])
            att_id = cursor.fetchone()[0]
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'DB алдаа: {str(e)}'}, status=500)

    return JsonResponse({'ok': True, 'attendance_id': att_id})


def request_json(request):
    try:
        import json
        return json.loads(request.body.decode('utf-8'))
    except Exception:
        return {}

# 6) attendance list page (teacher) — view existing attendance for a session and manual mark form
@csrf_protect
def attendance_list_view(request, session_id):
    if not _is_admin(request):
        return redirect('login')

    # session meta
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT cs.id, cs.token, cs.expires_at, c.name, c.code, t.name, l.name,
                   (to_char(ts.start_time,'HH24:MI') || '-' || to_char(ts.end_time,'HH24:MI')) AS slot
            FROM class_session cs
            JOIN course c ON c.id = cs.course_id
            JOIN teacher_profile t ON t.id = cs.teacher_id
            LEFT JOIN location l ON l.id = cs.location_id
            LEFT JOIN time_setting ts ON ts.id = cs.time_setting_id
            WHERE cs.id=%s
        """, [session_id])
        srow = cursor.fetchone()
    if not srow:
        r = redirect('teacher_dashboard')
        set_cookie_safe(r, 'flash_msg', 'Session олдсонгүй', 5)
        set_cookie_safe(r, 'flash_status', 404, 5)
        return r

    session = {
        'id': srow[0], 'token': srow[1], 'expires_at': srow[2],
        'course': srow[3], 'course_code': srow[4], 'teacher': srow[5],
        'location': srow[6], 'slot': srow[7]
    }

    # attendance rows for this session
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT a.id, a.student_id, s.full_name, s.student_code, a.timestamp, a.status
            FROM attendance a
            JOIN student s ON s.id = a.student_id
            WHERE a.session_id = %s
            ORDER BY a.timestamp
        """, [session_id])
        attendance_rows = cursor.fetchall()
    attendances = [{'id': r[0], 'student_id': r[1], 'student_name': r[2], 'student_code': r[3], 'timestamp': r[4], 'status': r[5]} for r in attendance_rows]

    # students enrolled in the course (for manual marking list)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT s.id, s.full_name, s.student_code
            FROM enrollment e
            JOIN student s ON s.id = e.student_id
            WHERE e.course_id = (SELECT course_id FROM class_session WHERE id=%s)
              AND e.year = EXTRACT(year FROM (SELECT date FROM class_session WHERE id=%s))
              AND e.term = (SELECT CASE WHEN EXTRACT(month FROM date) >= 1 AND EXTRACT(month FROM date) <= 6 THEN 2 ELSE 1 END FROM class_session WHERE id=%s)
            ORDER BY s.full_name
        """, [session_id, session_id, session_id])
        studs = cursor.fetchall()
    students = [{'id': r[0], 'name': r[1], 'code': r[2]} for r in studs]

    # manual marking POST
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        status = request.POST.get('status', 'present')
        # reuse attendance_mark logic: we can insert directly
        if student_id:
            with connection.cursor() as cursor:
                # prevent duplicates
                cursor.execute("SELECT id FROM attendance WHERE session_id=%s AND student_id=%s LIMIT 1", [session_id, student_id])
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO attendance (session_id, student_id, timestamp, success, status)
                        VALUES (%s,%s,now(),TRUE,%s)
                    """, [session_id, student_id, status])
            r = redirect('attendance_list', session_id=session_id)
            set_cookie_safe(r, 'flash_msg', 'Гар аргаар бүртгэгдлээ', 4)
            set_cookie_safe(r, 'flash_status', 200, 4)
            return r

    return render(request, 'teacher/attendance_list.html', {
        'session': session,
        'attendances': attendances,
        'students': students
    })
