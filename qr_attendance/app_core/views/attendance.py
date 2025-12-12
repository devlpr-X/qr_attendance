# views.py
import logging
from math import radians, sin, cos, sqrt, asin

from django.db import connection, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

logger = logging.getLogger(__name__)


def haversine_m(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in meters"""
    try:
        R = 6371000.0
        dlat = radians(float(lat2) - float(lat1))
        dlon = radians(float(lon2) - float(lon1))
        a = sin(dlat / 2) ** 2 + cos(radians(float(lat1))) * cos(radians(float(lat2))) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        return R * c
    except (ValueError, TypeError) as e:
        logger.exception("Haversine calculation error")
        return None


def scan_page(request, token):
    """QR scan page - displays session info and location requirements"""
    error = None
    session = None
    loc = None

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT cs.id, cs.course_id, c.name, c.code, cs.date,
                       ts.value as timeslot, lt.name as lesson_type,
                       cs.location_id, cs.token, cs.expires_at, cs.name
                FROM class_session cs
                JOIN course c ON c.id = cs.course_id
                LEFT JOIN time_setting ts ON ts.id = cs.time_setting_id
                LEFT JOIN lesson_type lt ON lt.id = cs.lesson_type_id
                WHERE cs.token = %s
            """, [token])
            row = cursor.fetchone()

        if not row:
            error = 'Token буруу эсвэл session олдсонгүй.'
        else:
            now = timezone.now()
            expires_at = row[9]

            # Make expires_at timezone-aware if naive
            if expires_at and timezone.is_naive(expires_at):
                expires_at = timezone.make_aware(expires_at)

            if expires_at and expires_at < now:
                error = 'Session-ий хугацаа дууссан байна.'
            else:
                session = {
                    'id': row[0],
                    'course_id': row[1],
                    'course_name': row[2],
                    'course_code': row[3],
                    'date': row[4],
                    'timeslot': row[5],
                    'lesson_type': row[6],
                    'location_id': row[7],
                    'token': str(row[8]),
                    'expires_at': expires_at,
                    'name': row[10]
                }

                if session['location_id']:
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT id, name, latitude, longitude, radius_m
                            FROM location
                            WHERE id = %s
                        """, [session['location_id']])
                        lr = cursor.fetchone()
                        if lr:
                            loc = {
                                'id': lr[0],
                                'name': lr[1],
                                'latitude': lr[2],
                                'longitude': lr[3],
                                'radius_m': lr[4]
                            }
    except Exception as e:
        logger.exception("scan_page error")
        error = 'Системийн алдаа. Админтай холбогдоно уу.'

    return render(request, 'admin/attendance/scan_qr.html', {
        'session': session,
        'location': loc,
        'error': error
    })


def submit_attendance(request, token):
    """Submit attendance via QR scan - returns JSON"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Зөвхөн POST request зөвшөөрөгдсөн.'}, status=405)

    try:
        # Get form data
        student_code = (request.POST.get('student_code') or '').strip()
        lat = request.POST.get('lat')
        lon = request.POST.get('lon')
        device_id = request.POST.get('device_id') or ''
        device_info = request.POST.get('device_info') or request.META.get('HTTP_USER_AGENT', '')

        if not student_code:
            return JsonResponse({'ok': False, 'error': 'Оюутны код оруулна уу.'})

        # Find session
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, course_id, location_id, date, expires_at
                FROM class_session
                WHERE token = %s
            """, [token])
            row = cursor.fetchone()

        if not row:
            return JsonResponse({'ok': False, 'error': 'Session олдсонгүй.'})

        session_id, course_id, location_id, session_date, expires_at = row

        # Check expiry
        now = timezone.now()
        if expires_at:
            if timezone.is_naive(expires_at):
                expires_at = timezone.make_aware(expires_at)
            if expires_at < now:
                return JsonResponse({'ok': False, 'error': 'Session-ий хугацаа дууссан байна.'})

        # Lookup student
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, full_name
                FROM student
                WHERE student_code = %s
                LIMIT 1
            """, [student_code])
            s = cursor.fetchone()

        if not s:
            return JsonResponse({'ok': False, 'error': 'Оюутан олдсонгүй. Код шалгана уу.'})

        student_id = s[0]
        student_name = s[1]

        # Check enrollment (best-effort; keep raw SQL similar to your schema)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM class_group_schedule cgs
                INNER JOIN student_class_group scg ON scg.class_group_id = cgs.class_group_id
                INNER JOIN course_schedule_pattern csp ON csp.id = cgs.course_schedule_pattern_id
                WHERE scg.student_id = %s AND csp.course_id = %s
            """, [student_id, course_id])
            enrolled_count = cursor.fetchone()[0]

        if enrolled_count == 0:
            return JsonResponse({'ok': False, 'error': 'Та энэ хичээлд бүртгэлтэй биш байна.', 'student_name': student_name})

        # Device registry check / register
        with connection.cursor() as cursor:
            cursor.execute("SELECT device_id FROM device_registry WHERE student_id = %s LIMIT 1", [student_id])
            existing = cursor.fetchone()

        if existing:
            existing_device = existing[0]
            if device_id and device_id != existing_device:
                return JsonResponse({
                    'ok': False,
                    'error': 'Таны төхөөрөмж бүртгэлтэй төхөөрөмжтэй таарахгүй байна. Админ/багштай холбогдоно уу.',
                    'student_name': student_name
                })
        else:
            if device_id:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO device_registry (student_id, device_id, device_info, created_at)
                        VALUES (%s, %s, %s, %s)
                    """, [student_id, device_id, device_info, now])

        # Location verification
        allowed_ok = True
        distance_m = None
        location_error = None

        if location_id:
            with connection.cursor() as cursor:
                cursor.execute("SELECT latitude, longitude, radius_m, name FROM location WHERE id = %s", [location_id])
                lr = cursor.fetchone()

            if lr:
                # require lat/lon from client
                if not lat or not lon:
                    allowed_ok = False
                    location_error = 'Байршил авч чадсангүй. GPS-аа идэвхжүүлнэ үү.'
                else:
                    try:
                        lat_f = float(lat)
                        lon_f = float(lon)
                        # lr[0]=latitude, lr[1]=longitude
                        distance_m = haversine_m(lr[0], lr[1], lat_f, lon_f)
                        if distance_m is None:
                            allowed_ok = False
                            location_error = 'Байршлын тооцоолол алдаатай байна.'
                        else:
                            distance_m = int(distance_m)
                            allowed_radius = lr[2] or 100
                            if distance_m > allowed_radius:
                                allowed_ok = False
                                location_error = f'Та {lr[3]}-с {distance_m}м зайд байна. Зөвшөөрөгдсөн радиус: {allowed_radius}м'
                    except (ValueError, TypeError) as e:
                        allowed_ok = False
                        location_error = f'Байршлын мэдээлэл буруу байна: {str(e)}'

        # Determine present attendance type id (best-effort)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id FROM attendance_type
                WHERE value = 'present' OR name ILIKE '%ирсэн%'
                LIMIT 1
            """)
            present_type = cursor.fetchone()
            present_type_id = present_type[0] if present_type else 1

        # Check existing attendance
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, attendance_type_id
                FROM attendance
                WHERE session_id = %s AND student_id = %s
                LIMIT 1
            """, [session_id, student_id])
            existing_att = cursor.fetchone()

        if not allowed_ok:
            return JsonResponse({
                'ok': False,
                'error': location_error or 'Байршил шаардлага хангахгүй байна.',
                'distance_m': distance_m,
                'student_name': student_name
            })

        if existing_att:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE attendance
                        SET attendance_type_id = %s,
                            "timestamp" = %s,
                            lat = %s,
                            lon = %s,
                            device_id = %s,
                            device_info = %s
                        WHERE id = %s
                    """, [present_type_id, now, lat, lon, device_id, device_info, existing_att[0]])

            return JsonResponse({
                'ok': True,
                'message': 'Ирц амжилттай бүртгэгдлээ!',
                'distance_m': distance_m,
                'student_name': student_name
            })
        else:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO attendance
                        (session_id, student_id, "timestamp", lat, lon, device_id, device_info, attendance_type_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, [session_id, student_id, now, lat, lon, device_id, device_info, present_type_id])
                    new_id = cursor.fetchone()[0] if cursor.fetchone() else None

            return JsonResponse({
                'ok': True,
                'message': 'Ирц амжилттай бүртгэгдлээ!',
                'distance_m': distance_m,
                'student_name': student_name
            })

    except Exception as e:
        logger.exception("submit_attendance error")
        return JsonResponse({'ok': False, 'error': 'Системийн алдаа. Админтай холбогдоно уу.'}, status=500)
