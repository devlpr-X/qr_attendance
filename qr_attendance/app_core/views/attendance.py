# app_core/views/attendance.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from ..utils import _is_admin, set_cookie_safe, get_cookie_safe
from math import radians, sin, cos, sqrt, asin

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

# Scan page (GET) - QR-д зориулсан хуудас
def scan_page(request, token):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT cs.id, cs.course_id, c.name, c.code, cs.date, cs.timeslot, cs.lesson_type, cs.location_id, cs.token
            FROM class_session cs
            JOIN course c ON c.id = cs.course_id
            WHERE cs.token = %s
        """, [token])
        row = cursor.fetchone()

    if not row:
        return render(request, 'attendance/invalid_token.html', {'error': 'Token буруу эсвэл session олдсонгүй.'})

    session = {
        'id': row[0], 'course_id': row[1], 'course_name': row[2], 'course_code': row[3],
        'date': row[4], 'timeslot': row[5], 'lesson_type': row[6], 'location_id': row[7], 'token': row[8]
    }

    # location details (если байршил байгаа бол)
    loc = None
    if session['location_id']:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, name, latitude, longitude, radius_m FROM location WHERE id = %s", [session['location_id']])
            lr = cursor.fetchone()
            if lr:
                loc = {'id': lr[0], 'name': lr[1], 'latitude': lr[2], 'longitude': lr[3], 'radius_m': lr[4]}

    return render(request, 'admin/attendance/scan_qr.html', {'session': session, 'location': loc})


# Submit attendance (POST)
def submit_attendance(request, token):
    if request.method != 'POST':
        return redirect('scan_page', token=token)

    student_code = (request.POST.get('student_code') or '').strip()
    lat = request.POST.get('lat')
    lon = request.POST.get('lon')
    device_id = request.POST.get('device_id') or ''
    device_info = request.POST.get('device_info') or request.META.get('HTTP_USER_AGENT','')

    if not student_code:
        return render(request, 'attendance/submit_result.html', {'ok': False, 'error': 'Оюутны код оруулна уу.'})

    # find session
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, course_id, location_id, date FROM class_session WHERE token = %s", [token])
        row = cursor.fetchone()
    if not row:
        return render(request, 'attendance/submit_result.html', {'ok': False, 'error': 'Session олдсонгүй.'})

    session_id, course_id, location_id, session_date = row

    # lookup student
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM student WHERE student_code = %s LIMIT 1", [student_code])
        s = cursor.fetchone()
    if not s:
        return render(request, 'attendance/submit_result.html', {'ok': False, 'error': 'Оюутан олдсонгүй.'})
    student_id = s[0]

    # is enrolled?
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM enrollment WHERE student_id = %s AND course_id = %s LIMIT 1", [student_id, course_id])
        if not cursor.fetchone():
            # write a failed attendance record (not enrolled)
            with connection.cursor() as c2:
                c2.execute("""
                    INSERT INTO attendance (session_id, student_id, timestamp, lat, lon, success, note, device_id, device_info, status)
                    VALUES (%s, %s, now(), %s, %s, FALSE, %s, %s, %s, %s)
                """, [session_id, student_id, lat or None, lon or None, 'not enrolled', device_id or None, device_info, 'absent'])
            return render(request, 'attendance/submit_result.html', {'ok': False, 'error': 'Та энэ хичээлд бүртгэлтэй биш байна.'})

    # device registry check
    with connection.cursor() as cursor:
        cursor.execute("SELECT device_id FROM device_registry WHERE student_id = %s LIMIT 1", [student_id])
        existing = cursor.fetchone()
    if existing:
        existing_device = existing[0]
        if device_id != existing_device:
            # device mismatch
            with connection.cursor() as c2:
                c2.execute("""
                    INSERT INTO attendance (session_id, student_id, timestamp, lat, lon, success, note, device_id, device_info, status)
                    VALUES (%s, %s, now(), %s, %s, FALSE, %s, %s, %s, %s)
                """, [session_id, student_id, lat or None, lon or None, 'device mismatch', device_id or None, device_info, 'absent'])
            return render(request, 'attendance/submit_result.html', {'ok': False, 'error': 'Таны төхөөрөмж бүртгэлтэй төхөөрөмжтэй таарахгүй байна. Админ/багштай холбогдоно уу.'})
    else:
        # register device for this student
        if device_id:
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO device_registry (student_id, device_id, device_info) VALUES (%s, %s, %s)", [student_id, device_id, device_info])

    # location check
    allowed_ok = True
    distance_m = None
    if location_id:
        with connection.cursor() as cursor:
            cursor.execute("SELECT latitude, longitude, radius_m FROM location WHERE id = %s", [location_id])
            lr = cursor.fetchone()
        if lr:
            try:
                lat_f = float(lat)
                lon_f = float(lon)
                distance_m = int(haversine_m(lr[0], lr[1], lat_f, lon_f))
                allowed_ok = distance_m <= (lr[2] or 100)
            except Exception:
                allowed_ok = False

    # Prevent duplicate attendance (session + student)
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM attendance WHERE session_id = %s AND student_id = %s LIMIT 1", [session_id, student_id])
        if cursor.fetchone():
            return render(request, 'attendance/submit_result.html', {'ok': False, 'error': 'Та аль хэдийн ирц бүртгэгдсэн байна.'})

    # write attendance
    status_val = 'present' if allowed_ok else 'absent'
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO attendance (session_id, student_id, timestamp, lat, lon, success, note, device_id, device_info, status)
            VALUES (%s, %s, now(), %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, [session_id, student_id, lat or None, lon or None, allowed_ok, '' if allowed_ok else 'location not allowed', device_id or None, device_info, status_val])
        att_id = cursor.fetchone()[0]

    if allowed_ok:
        return render(request, 'attendance/submit_result.html', {'ok': True, 'message': 'Ирц амжилттай бүртгэгдлээ.', 'distance_m': distance_m})
    else:
        return render(request, 'attendance/submit_result.html', {'ok': False, 'error': 'Та зөв байршилд биш байна.', 'distance_m': distance_m})


# Teacher manual mark (present / absent / sick)
def teacher_mark_attendance(request, session_id):
    if not _is_admin(request):
        return redirect('login')

    # GET: show all students of that session's course with existing attendance
    if request.method == 'GET':
        with connection.cursor() as cursor:
            cursor.execute("SELECT course_id FROM class_session WHERE id = %s", [session_id])
            r = cursor.fetchone()
            if not r:
                response = redirect('sessions_list')
                set_cookie_safe(response, 'flash_msg', 'Session олдсонгүй', 6)
                set_cookie_safe(response, 'flash_status', 404, 6)
                return response
            course_id = r[0]

            # students in course with their existing attendance status
            cursor.execute("""
                SELECT s.id, s.full_name, s.student_code,
                  (SELECT id FROM attendance a WHERE a.session_id = %s AND a.student_id = s.id LIMIT 1) AS attendance_id,
                  (SELECT status FROM attendance a WHERE a.session_id = %s AND a.student_id = s.id LIMIT 1) AS status
                FROM enrollment e
                JOIN student s ON s.id = e.student_id
                WHERE e.course_id = %s
                ORDER BY s.full_name
            """, [session_id, session_id, course_id])
            rows = cursor.fetchall()

        students = [{'id': r[0], 'full_name': r[1], 'student_code': r[2], 'attendance_id': r[3], 'status': r[4]} for r in rows]
        
        # fetch possible statuses from ref_constant
        with connection.cursor() as cursor:
            cursor.execute("SELECT value, name FROM ref_constant WHERE type = 'attendance_status' ORDER BY id")
            statuses = cursor.fetchall()
        statuses = [{'value': s[0], 'name': s[1]} for s in statuses]
        
        return render(request, 'admin/sessions/mark_attendance.html', {
            'students': students, 
            'session_id': session_id, 
            'statuses': statuses
        })

    # POST: update statuses
    if request.method == 'POST':
        # data: for each student: status_{student_id}
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    for key, val in request.POST.items():
                        if key.startswith('status_'):
                            student_id = int(key.split('_', 1)[1])
                            status_val = val or 'absent'
                            
                            # upsert attendance record
                            cursor.execute("SELECT id FROM attendance WHERE session_id = %s AND student_id = %s LIMIT 1", [session_id, student_id])
                            ex = cursor.fetchone()
                            if ex:
                                # UPDATE existing
                                cursor.execute("""
                                    UPDATE attendance 
                                    SET status = %s, success = %s, note = %s 
                                    WHERE id = %s
                                """, [status_val, True if status_val == 'present' else False, 'teacher_manual', ex[0]])
                            else:
                                # INSERT new
                                cursor.execute("""
                                    INSERT INTO attendance (session_id, student_id, timestamp, success, note, status) 
                                    VALUES (%s, %s, now(), %s, %s, %s)
                                """, [session_id, student_id, True if status_val == 'present' else False, 'teacher_manual', status_val])
            
            response = redirect('session_view', session_id=session_id)
            set_cookie_safe(response, 'flash_msg', 'Ирцийн статусууд амжилттай шинэчлэгдлээ', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response
        except Exception as e:
            return render(request, 'admin/sessions/mark_attendance.html', {
                'error': f'Алдаа гарлаа: {str(e)}',
                'session_id': session_id
            })