from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.http import JsonResponse, HttpResponseBadRequest, Http404
from django.urls import reverse
from django.utils import timezone
from io import BytesIO
from datetime import timedelta
import uuid
import datetime, math, qrcode, base64
from ...utils import _get_current_semester_pattern  

def get_timeslots(school_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name, value, id 
                FROM time_setting
                WHERE location_id = %s       
            ORDER BY id
        """, [school_id])
        times = cursor.fetchall()
    return [{"name": t[0], "slot": t[1], "id": t[2]} for t in times]

def get_teacher_info(user_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT B.location_id, A.id
                FROM teacher_profile A
                    INNER JOIN course_schedule_pattern B ON B.teacher_id = A.id 
                    WHERE A.user_id = %s LIMIT 1
        """, [user_id])
        cr = cursor.fetchone()
    return cr

# 1) БАГШИЙН ДАШБОРД (ХИЧЭЭЛҮҮД)
def teacher_dashboard(request):
    user_id = int(request.COOKIES.get("user_id"))
    cr = get_teacher_info(user_id)
    school_id = cr[0]

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

    year = request.GET.get("year")
    term = request.GET.get("term")

    now = timezone.now()
    if not year:
        year = now.year

    if not term:
        term = 2 if now.month <= 7 else 1

    # 3) Тухайн он/семестр → semester.id олж авах
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
    timeslots = get_timeslots(school_id)

    # 5) Хуваарь (course_schedule_pattern)
    # ------------------------------
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                csp.id,
                c.name AS course_name,
                c.code AS course_code,
                csp.day_of_week,
                (F.start_time::text || ' - ' || F.end_time::text) AS timeslot,
                lt.value AS lesson_type,
                l.name AS location,
                lt.id AS lesson_type_id,
                l.id AS location_id,
                c.id AS course_id,
                csp.teacher_id,
                csp.semester_id,
                csp.time_setting_id,
                s.school_year, 
                s.term,
				csp.class_room_id, G.room_number,
                lt.name AS lesson_type_name
            FROM course_schedule_pattern csp
            JOIN course c ON c.id = csp.course_id
            LEFT JOIN lesson_type lt ON lt.id = csp.lesson_type_id
            LEFT JOIN location l ON l.id = csp.location_id
            LEFT JOIN semester s ON s.id = csp.semester_id
            LEFT JOIN time_setting  F  ON csp.time_setting_id = F.id
            LEFT JOIN class_room G ON G.id = csp.class_room_id
            WHERE csp.teacher_id = %s AND csp.semester_id = %s
            ORDER BY csp.day_of_week, (F.start_time::text || ' - ' || F.end_time::text)
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
            "term": r[14],
            "class_room_id": r[15],
            "room_number": r[16],
            "lesson_type_name": r[17]
        })

    return render(request, "teacher/teacher_dashboard.html", {
        "teacher_name": teacher_name,
        "year": year,
        "term": term,
        "patterns": patterns,
        "timeslots": timeslots,
    })


def get_attendance_types():
    """Get all attendance types"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, name, value
            FROM attendance_type
            ORDER BY id
        """)
        return cursor.fetchall()

#ҮҮСГЭХ эхлэх
    
from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.http import JsonResponse, HttpResponseBadRequest, Http404
from django.urls import reverse
from django.utils import timezone
from io import BytesIO
from datetime import timedelta
import uuid
import datetime, math, qrcode, base64
from ...utils import _get_current_semester_pattern


def get_teacher_info(user_id):
    """Helper function to get teacher school_id and teacher_id"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT tp.id as teacher_id, s.school_id
            FROM teacher_profile tp
            JOIN app_user u ON u.id = tp.user_id
            LEFT JOIN semester s ON s.is_active = true
            WHERE tp.user_id = %s
            LIMIT 1
        """, [user_id])
        row = cursor.fetchone()
        if row:
            return (row[1], row[0])  # (school_id, teacher_id)
    return (None, None)


def get_timeslots(school_id):
    """Get all timeslots for a school"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name, value, id 
            FROM time_setting
            WHERE location_id = %s       
            ORDER BY id
        """, [school_id])
        times = cursor.fetchall()
    return [{"name": t[0], "slot": t[1], "id": t[2]} for t in times]


def get_attendance_types():
    """Get all attendance types"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, name, value
            FROM attendance_type
            ORDER BY id
        """)
        return cursor.fetchall()


def get_class_groups_for_pattern(pattern_id):
    """Get class groups linked to a pattern"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT cg.id, cg.name, cg.group_number
            FROM class_group_schedule cgs
            INNER JOIN class_group cg ON cg.id = cgs.class_group_id
            WHERE cgs.course_schedule_pattern_id = %s
            ORDER BY cg.name, cg.group_number
        """, [pattern_id])
        return cursor.fetchall()


def create_session(request):
    # Get teacher info from cookies
    user_id = request.COOKIES.get('user_id')
    if not user_id:
        return redirect('login')
    
    cr = get_teacher_info(user_id)
    school_id = cr[0]
    teacher_id = cr[1]

    if not school_id or not teacher_id:
        return HttpResponseBadRequest("Багшийн мэдээлэл олдсонгүй")

    # Get timeslots and attendance types
    timeslots = get_timeslots(school_id)
    attendance_types = get_attendance_types()

    # Get current year and term
    now = timezone.now()
    current_year = now.year
    current_term = 2 if now.month <= 7 else 1

    # Form GET params to prefill/search
    day_of_week = request.GET.get('day_of_week')
    time_setting_id = request.GET.get('time_setting_id')
    selected_pattern_id = request.GET.get('pattern_id')
    filter_group = request.GET.get('filter_group')  # Filter by class group

    # Found scheduled patterns for this teacher at given day/time
    found_patterns = []
    if day_of_week is not None and time_setting_id is not None and day_of_week != "" and time_setting_id != "":
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.id, p.course_id, p.lesson_type_id, p.class_room_id, p.location_id,
                       co.name AS course_name, co.code AS course_code,
                       lt.name AS lesson_type_name,
                       cr.room_number
                FROM course_schedule_pattern p
                LEFT JOIN course co ON co.id = p.course_id
                LEFT JOIN lesson_type lt ON lt.id = p.lesson_type_id
                LEFT JOIN class_room cr ON cr.id = p.class_room_id
                WHERE p.teacher_id = %s
                  AND p.day_of_week = %s
                  AND p.time_setting_id = %s
                ORDER BY co.name
            """, [teacher_id, day_of_week, time_setting_id])
            found_patterns = cursor.fetchall()

    # If a pattern is selected, fetch its info & students
    pattern_info = None
    students_for_pattern = []
    class_groups = []
    if selected_pattern_id:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.id, p.course_id, co.name as course_name, co.code as course_code,
                       p.lesson_type_id, lt.name as lesson_type_name,
                       p.class_room_id, cr.room_number, p.location_id
                FROM course_schedule_pattern p
                LEFT JOIN course co ON co.id = p.course_id
                LEFT JOIN lesson_type lt ON lt.id = p.lesson_type_id
                LEFT JOIN class_room cr ON cr.id = p.class_room_id
                WHERE p.id = %s
            """, [selected_pattern_id])
            row = cursor.fetchone()
            if row:
                pattern_info = {
                    'id': row[0],
                    'course_id': row[1],
                    'course_name': row[2],
                    'course_code': row[3],
                    'lesson_type_id': row[4],
                    'lesson_type_name': row[5],
                    'class_room_id': row[6],
                    'room_number': row[7],
                    'location_id': row[8],
                }

        # Get class groups for filtering
        class_groups = get_class_groups_for_pattern(selected_pattern_id)

        # Get students for this pattern (with optional group filter)
        if filter_group:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT s.id, s.full_name, s.student_code, cg.name as group_name
                    FROM class_group_schedule cgs
                    INNER JOIN class_group cg ON cg.id = cgs.class_group_id
                    INNER JOIN student_class_group scg ON scg.class_group_id = cg.id
                    INNER JOIN student s ON s.id = scg.student_id
                    WHERE cgs.course_schedule_pattern_id = %s
                      AND cg.id = %s
                    ORDER BY s.full_name
                """, [selected_pattern_id, filter_group])
                students_for_pattern = cursor.fetchall()
        else:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT s.id, s.full_name, s.student_code, cg.name as group_name
                    FROM class_group_schedule cgs
                    INNER JOIN class_group cg ON cg.id = cgs.class_group_id
                    INNER JOIN student_class_group scg ON scg.class_group_id = cg.id
                    INNER JOIN student s ON s.id = scg.student_id
                    WHERE cgs.course_schedule_pattern_id = %s
                    ORDER BY s.full_name
                """, [selected_pattern_id])
                students_for_pattern = cursor.fetchall()

    # Session info if created
    created_session = None
    session_attendance = []
    qr_code_base64 = None

    message = None
    error = None

    # POST handling
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_session':
            pattern_id = request.POST.get('pattern_id') or None
            course_id = request.POST.get('course_id') or None
            location_id = request.POST.get('location_id') or None
            lesson_type_id = request.POST.get('lesson_type_id') or None
            time_setting_id_post = request.POST.get('time_setting_id') or None
            session_name = request.POST.get('name') or ''
            class_room_id = None

            # If created from pattern, get pattern details
            if pattern_id:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT course_id, lesson_type_id, class_room_id, location_id
                        FROM course_schedule_pattern
                        WHERE id = %s
                    """, [pattern_id])
                    p = cursor.fetchone()
                    if p:
                        course_id = p[0]
                        lesson_type_id = p[1]
                        class_room_id = p[2]
                        location_id = p[3]
            else:
                class_room_id = request.POST.get('class_room_id') or None

            # Generate session name if not provided
            if not session_name:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT name FROM course WHERE id = %s", [course_id])
                    course_row = cursor.fetchone()
                    if course_row:
                        session_name = f"{course_row[0]} - {now.strftime('%Y-%m-%d %H:%M')}"

            # Create session
            try:
                with transaction.atomic():
                    token = str(uuid.uuid4())
                    expires_at = now + timedelta(minutes=10)

                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO class_session
                            (teacher_id, course_id, token, location_id, date, created_at,
                             lesson_type_id, time_setting_id, expires_at, name)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            RETURNING id, token, expires_at
                        """, [
                            teacher_id,
                            course_id,
                            token,
                            location_id,
                            now.date(),
                            now,
                            lesson_type_id,
                            time_setting_id_post,
                            expires_at,
                            session_name
                        ])
                        cs_row = cursor.fetchone()
                        if cs_row:
                            created_session = {
                                'id': cs_row[0],
                                'token': str(cs_row[1]),
                                'expires_at': cs_row[2],
                                'name': session_name,
                            }
                            
                            # Generate QR code
                            qr_url = request.build_absolute_uri(f'/attendance/{cs_row[1]}/scan/')
                            qr = qrcode.QRCode(version=1, box_size=10, border=5)
                            qr.add_data(qr_url)
                            qr.make(fit=True)
                            img = qr.make_image(fill_color="black", back_color="white")
                            
                            buffered = BytesIO()
                            img.save(buffered, format="PNG")
                            qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()

                    # Pre-register all students as "Тасалсан" (absent)
                    if pattern_id:
                        # Find attendance_type_id for "Тасалсан"
                        with connection.cursor() as cursor:
                            cursor.execute("""
                                SELECT id FROM attendance_type WHERE value = 'absent' OR name ILIKE '%тасалсан%' LIMIT 1
                            """)
                            absent_type = cursor.fetchone()
                            absent_type_id = absent_type[0] if absent_type else 2  # default to 2

                            # Get all students for pattern
                            cursor.execute("""
                                SELECT DISTINCT s.id
                                FROM class_group_schedule cgs
                                INNER JOIN class_group cg ON cg.id = cgs.class_group_id
                                INNER JOIN student_class_group scg ON scg.class_group_id = cg.id
                                INNER JOIN student s ON s.id = scg.student_id
                                WHERE cgs.course_schedule_pattern_id = %s
                            """, [pattern_id])
                            all_students = cursor.fetchall()

                            # Batch insert as "Тасалсан"
                            for student in all_students:
                                cursor.execute("""
                                    INSERT INTO attendance
                                    (session_id, student_id, "timestamp", attendance_type_id, device_id, device_info)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, [cs_row[0], student[0], now, absent_type_id, 'pre-registered', 'Автоматаар тасалсан'])

                    message = "Session амжилттай үүслээ. Бүх оюутнууд 'Тасалсан' байдлаар урьдчилан бүртгэгдлээ."
            except Exception as e:
                error = f"Хуваарь үүсгэхэд алдаа: {str(e)}"

            # Load students for created session
            if created_session and pattern_id:
                filter_group = request.POST.get('filter_group')
                class_groups = get_class_groups_for_pattern(pattern_id)
                
                if filter_group:
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT DISTINCT s.id, s.full_name, s.student_code, cg.name as group_name
                            FROM class_group_schedule cgs
                            INNER JOIN class_group cg ON cg.id = cgs.class_group_id
                            INNER JOIN student_class_group scg ON scg.class_group_id = cg.id
                            INNER JOIN student s ON s.id = scg.student_id
                            WHERE cgs.course_schedule_pattern_id = %s AND cg.id = %s
                            ORDER BY s.full_name
                        """, [pattern_id, filter_group])
                        students_for_pattern = cursor.fetchall()
                else:
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT DISTINCT s.id, s.full_name, s.student_code, cg.name as group_name
                            FROM class_group_schedule cgs
                            INNER JOIN class_group cg ON cg.id = cgs.class_group_id
                            INNER JOIN student_class_group scg ON scg.class_group_id = cg.id
                            INNER JOIN student s ON s.id = scg.student_id
                            WHERE cgs.course_schedule_pattern_id = %s
                            ORDER BY s.full_name
                        """, [pattern_id])
                        students_for_pattern = cursor.fetchall()

        elif action == 'bulk_mark_attendance':
            session_id = request.POST.get('session_id')
            student_ids = request.POST.getlist('student_ids[]')
            attendance_type_id = request.POST.get('attendance_type_id') or 1
            
            if not session_id:
                error = "Session олдсонгүй."
            elif not student_ids:
                error = "Оюутан сонгогдоогүй."
            else:
                try:
                    with transaction.atomic():
                        now = timezone.now()
                        success_count = 0
                        
                        for student_id in student_ids:
                            with connection.cursor() as cursor:
                                # Update existing or insert new
                                cursor.execute("""
                                    UPDATE attendance
                                    SET attendance_type_id = %s, "timestamp" = %s, device_id = 'manual', device_info = 'Багшаар засварласан'
                                    WHERE session_id = %s AND student_id = %s
                                """, [attendance_type_id, now, session_id, student_id])
                                
                                if cursor.rowcount == 0:
                                    cursor.execute("""
                                        INSERT INTO attendance
                                        (session_id, student_id, "timestamp", attendance_type_id, device_id, device_info)
                                        VALUES (%s, %s, %s, %s, %s, %s)
                                    """, [session_id, student_id, now, attendance_type_id, 'manual', 'Багшаар бүртгэсэн'])
                                
                                success_count += 1
                        
                        message = f"{success_count} оюутны ирц амжилттай бүртгэгдлээ."
                except Exception as e:
                    error = f"Бүртгэх үед алдаа: {str(e)}"

            # Reload session info
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id, token, expires_at, name
                    FROM class_session
                    WHERE id = %s
                """, [session_id])
                cs_row = cursor.fetchone()
                if cs_row:
                    created_session = {
                        'id': cs_row[0],
                        'token': str(cs_row[1]),
                        'expires_at': cs_row[2],
                        'name': cs_row[3],
                    }
                    
                    # Regenerate QR code
                    qr_url = request.build_absolute_uri(f'/attendance/{cs_row[1]}/scan/')
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(qr_url)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    
                    buffered = BytesIO()
                    img.save(buffered, format="PNG")
                    qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()

        elif action == 'remove_attendance':
            attendance_id = request.POST.get('attendance_id')
            session_id = request.POST.get('session_id')
            
            if not attendance_id:
                error = "Устгах бүртгэл сонгогдоогүй."
            else:
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("DELETE FROM attendance WHERE id = %s", [attendance_id])
                            message = "Бүртгэл амжилттай устгагдлаа."
                except Exception as e:
                    error = f"Устгах үед алдаа: {str(e)}"

            # Reload session info
            if session_id:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, token, expires_at, name
                        FROM class_session
                        WHERE id = %s
                    """, [session_id])
                    cs_row = cursor.fetchone()
                    if cs_row:
                        created_session = {
                            'id': cs_row[0],
                            'token': str(cs_row[1]),
                            'expires_at': cs_row[2],
                            'name': cs_row[3],
                        }
                        
                        # Regenerate QR code
                        qr_url = request.build_absolute_uri(f'/attendance/{cs_row[1]}/scan/')
                        qr = qrcode.QRCode(version=1, box_size=10, border=5)
                        qr.add_data(qr_url)
                        qr.make(fit=True)
                        img = qr.make_image(fill_color="black", back_color="white")
                        
                        buffered = BytesIO()
                        img.save(buffered, format="PNG")
                        qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()

    # Load attendance for active session
    if created_session:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT a.id, a.student_id, s.full_name, s.student_code, 
                    a.timestamp, at.name as attendance_type_name, a.attendance_type_id,
                    COALESCE(cg.name, '') as group_name
                FROM attendance a
                INNER JOIN student s ON s.id = a.student_id
                LEFT JOIN attendance_type at ON at.id = a.attendance_type_id
                LEFT JOIN student_class_group scg ON scg.student_id = s.id
                LEFT JOIN class_group cg ON cg.id = scg.class_group_id
                WHERE a.session_id = %s
            """, [created_session['id']])
            session_attendance = cursor.fetchall()

    return render(request, 'teacher/create_session.html', {
        'timeslots': timeslots,
        'attendance_types': attendance_types,
        'found_patterns': found_patterns,
        'pattern_info': pattern_info,
        'students_for_pattern': students_for_pattern,
        'class_groups': class_groups,
        'created_session': created_session,
        'session_attendance': session_attendance,
        'qr_code_base64': qr_code_base64,
        'message': message,
        'error': error,
        'day_of_week': day_of_week,
        'time_setting_id': time_setting_id,
        'filter_group': filter_group,
        'current_year': current_year,
        'current_term': current_term,
    })
#ҮҮСГЭХ дуусах

# 2) БАГШИЙН ХУВААРЬ (Pattern list)
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

# 3) QR ҮҮСГЭХ БОЛОМЖТОЙ ХИЧЭЭЛҮҮД (Pattern list)
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

# 4) БАГШИЙН ҮҮСГЭСЭН БҮХ SESSION (history)
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

def _get_cookie_user_id(request):
    try:
        return int(request.COOKIES.get('user_id'))
    except Exception:
        return None

def teacher_schedule(request):
    """
    Show teacher's timetable (filter by year & term). Provide buttons to create session.
    """
    teacher_user_id = _get_cookie_user_id(request)
    if not teacher_user_id:
        return redirect('login')

    # Map teacher_user_id -> teacher_profile.id (assuming teacher_profile.user_id = app_user.id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM teacher_profile WHERE user_id = %s LIMIT 1", [teacher_user_id])
        row = cursor.fetchone()
    if not row:
        return Http404("Teacher profile not found")
    teacher_profile_id, teacher_name = row

    # Semester selection: allow GET year & term, otherwise use current date logic
    year_q = request.GET.get('year')
    term_q = request.GET.get('term')
    now = timezone.now()
    default_year = now.year
    default_term = 2 if now.month <= 7 else 1

    try:
        year = int(year_q) if year_q else default_year
    except Exception:
        year = default_year
    try:
        term = int(term_q) if term_q else default_term
    except Exception:
        term = default_term

    # Find semester for given year & term (pick first active)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, school_id, start_date, end_date
            FROM semester
            WHERE school_year = %s AND term = %s
            ORDER BY id DESC
            LIMIT 1
        """, [year, term])
        sem = cursor.fetchone()

    if not sem:
        # No semester found: pass empty context
        semester = None
        semester_id = None
    else:
        semester_id = sem[0]
        semester = {'id': sem[0], 'school_id': sem[1], 'start_date': sem[2], 'end_date': sem[3]}

    # Load timeslots for school's location (fallback to all)
    timeslots = []
    with connection.cursor() as cursor:
        if semester and semester['school_id']:
            cursor.execute("""
                SELECT id, COALESCE(name, 'Цаг ' || id::text) AS name, value AS slot, start_time, end_time
                FROM time_setting WHERE location_id = %s ORDER BY start_time NULLS LAST, id
            """, [semester['school_id']])
            ts_rows = cursor.fetchall()
            if not ts_rows:
                cursor.execute("SELECT id, COALESCE(name,'Цаг ' || id::text) AS name, value AS slot, start_time, end_time FROM time_setting ORDER BY start_time NULLS LAST, id")
                ts_rows = cursor.fetchall()
        else:
            cursor.execute("SELECT id, COALESCE(name,'Цаг ' || id::text) AS name, value AS slot, start_time, end_time FROM time_setting ORDER BY start_time NULLS LAST, id")
            ts_rows = cursor.fetchall()

    for r in ts_rows:
        timeslots.append({'id': r[0], 'name': r[1], 'slot': r[2], 'start_time': r[3], 'end_time': r[4]})

    # Load patterns for this teacher in this semester (if semester selected)
    patterns = []
    if semester_id:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    csp.id,
                    c.name AS course_name,
                    c.code AS course_code,
                    csp.day_of_week,
                    (F.start_time::text || ' - ' || F.end_time::text) AS timeslot,
                    COALESCE(lt.value, '') AS lesson_type,
                    COALESCE(l.name, '') AS location,
                    lt.id AS lesson_type_id,
                    l.id AS location_id,
                    c.id AS course_id,
                    csp.teacher_id,
                    csp.semester_id,
                    csp.time_setting_id,
                    csp.frequency,
                    csp.start_from_date
                FROM course_schedule_pattern csp
                JOIN course c ON c.id = csp.course_id
                LEFT JOIN lesson_type lt ON lt.id = csp.lesson_type_id
                LEFT JOIN location l ON l.id = csp.location_id
                LEFT JOIN time_setting  F ON csp.time_setting_id = F.id
                WHERE csp.teacher_id = %s AND csp.semester_id = %s
                ORDER BY csp.day_of_week, csp.time_setting_id NULLS LAST, (F.start_time::text || ' - ' || F.end_time::text) 
            """, [teacher_profile_id, semester_id])
            rows = cursor.fetchall()

        week = ["Даваа", "Мягмар", "Лхагва", "Пүрэв", "Баасан", "Бямба", "Ням"]
        for r in rows:
            dow = r[3]
            patterns.append({
                "id": r[0],
                "course": r[1],
                "course_code": r[2],
                "day_of_week": dow,
                "day": week[dow] if isinstance(dow, int) and 0 <= dow <= 6 else str(dow),
                "timeslot": r[4],
                "lesson_type": r[5] or "",
                "location": r[6] or "",
                "lesson_type_id": r[7],
                "location_id": r[8],
                "course_id": r[9],
                "teacher_id": r[10],
                "semester_id": r[11],
                "time_setting_id": r[12],
                "frequency": r[13],
                "start_from_date": r[14],
            })

    context = {
        'teacher_name': teacher_name,
        'teacher_profile_id': teacher_profile_id,
        'year': year,
        'term': term,
        'semester': semester,
        'timeslots': timeslots,
        'patterns': patterns,
    }
    return render(request, 'teacher/teacher_dashboard.html', context)

# def create_session(request):
#     """
#     AJAX / POST endpoint to create class_session from a pattern.
#     Expects: pattern_id, session_date (YYYY-MM-DD optional), duration_minutes (int, optional), name (optional)
#     Returns JSON: {ok:True, token, expires_at, url}
#     """
#     if request.method != 'POST':
#         return HttpResponseBadRequest("POST only")
#     teacher_user_id = _get_cookie_user_id(request)
#     if not teacher_user_id:
#         return JsonResponse({'error': 'unauthenticated'}, status=403)

#     pattern_id = request.POST.get('pattern_id')
#     if not pattern_id:
#         return JsonResponse({'error': 'pattern_id required'}, status=400)

#     session_date = request.POST.get('session_date') or timezone.now().date().isoformat()
#     try:
#         session_date_obj = datetime.date.fromisoformat(session_date)
#     except Exception:
#         return JsonResponse({'error': 'invalid date'}, status=400)

#     duration_minutes = int(request.POST.get('duration_minutes') or 10)
#     name = request.POST.get('name') or ''  # e.g., "1-р долоо хоног"

#     # load pattern info
#     with connection.cursor() as cursor:
#         cursor.execute("""
#             SELECT semester_id, course_id, teacher_id, lesson_type_id, time_setting_id, location_id
#             FROM course_schedule_pattern
#             WHERE id = %s
#             LIMIT 1
#         """, [pattern_id])
#         p = cursor.fetchone()

#     if not p:
#         return JsonResponse({'error': 'pattern not found'}, status=404)

#     semester_id, course_id, pattern_teacher_id, lesson_type_id, time_setting_id, location_id = p

#     # ensure teacher matches cookie teacher (safety)
#     with connection.cursor() as cursor:
#         cursor.execute("SELECT user_id FROM teacher_profile WHERE id = %s", [pattern_teacher_id])
#         tp_row = cursor.fetchone()
#     if not tp_row:
#         return JsonResponse({'error': 'teacher profile not found'}, status=404)
#     pattern_user_id = tp_row[0]
#     if pattern_user_id != teacher_user_id:
#         return JsonResponse({'error': 'permission denied'}, status=403)

#     # derive school_id from semester if possible
#     school_id = None
#     if semester_id:
#         with connection.cursor() as cursor:
#             cursor.execute("SELECT school_id FROM semester WHERE id = %s LIMIT 1", [semester_id])
#             srow = cursor.fetchone()
#             if srow:
#                 school_id = srow[0]

#     # insert into class_session
#     try:
#         with transaction.atomic():
#             with connection.cursor() as cursor:
#                 cursor.execute("""
#                     INSERT INTO class_session
#                     (teacher_id, course_id, school_id, location_id, lesson_type_id, time_setting_id,
#                      name, date, expires_at)
#                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s, now() + (%s || ' minutes')::interval)
#                     RETURNING id, token, expires_at
#                 """, [
#                     pattern_teacher_id, course_id, school_id, location_id,
#                     lesson_type_id, time_setting_id, name or f"Session {session_date}", session_date_obj,
#                     str(duration_minutes)
#                 ])
#                 row = cursor.fetchone()
#                 session_id, token, expires_at = row
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=500)

#     session_url = request.build_absolute_uri(reverse('session_detail', args=[str(token)]))
#     return JsonResponse({'ok': True, 'session_id': session_id, 'token': str(token), 'expires_at': expires_at.isoformat(), 'url': session_url})

def session_detail(request, token):
    """
    Show session (QR) + enrolled students
    URL: /teacher/session/<token>/
    """

    # --------------------------
    # 1) Load class session
    # --------------------------
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                id, teacher_id, course_id, school_id, location_id,
                lesson_type_id, time_setting_id, name, date, token, expires_at
            FROM class_session
            WHERE token = %s
            LIMIT 1
        """, [str(token)])
        r = cursor.fetchone()

    if not r:
        raise Http404("Session not found")

    session = {
        'id': r[0],
        'teacher_id': r[1],
        'course_id': r[2],
        'school_id': r[3],
        'location_id': r[4],
        'lesson_type_id': r[5],
        'time_setting_id': r[6],
        'name': r[7],
        'date': r[8],
        'token': r[9],
        'expires_at': r[10]
    }

    # --------------------------
    # 2) Load course
    # --------------------------
    with connection.cursor() as cursor:
        cursor.execute("SELECT name, code FROM course WHERE id = %s", [session['course_id']])
        cc = cursor.fetchone()
    course = {'name': cc[0], 'code': cc[1]} if cc else {'name': '', 'code': ''}

    # --------------------------
    # 3) Load teacher
    # --------------------------
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM teacher_profile WHERE id = %s", [session['teacher_id']])
        tr = cursor.fetchone()
    teacher = tr[0] if tr else "Тодорхойгүй"

    # --------------------------
    # 4) Load location
    # --------------------------
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM location WHERE id = %s", [session['location_id']])
        lr = cursor.fetchone()
    location = lr[0] if lr else "Заагаагүй"

    # --------------------------
    # 5) Load time slot via time_setting
    # --------------------------
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name, start_time, end_time 
            FROM time_setting 
            WHERE id = %s
        """, [session['time_setting_id']])
        ts = cursor.fetchone()

    if ts:
        slot_name = ts[0]
        slot_range = f"{ts[1].strftime('%H:%M')} - {ts[2].strftime('%H:%M')}"
    else:
        slot_name = "Цаггүй"
        slot_range = ""

    # --------------------------
    # 6) Load enrolled students
    # --------------------------
    students = []

    with connection.cursor() as cursor:
        # Try find semester for session.date
        cursor.execute("""
            SELECT id, school_year, term
            FROM semester
            WHERE school_id = %s AND start_date <= %s AND end_date >= %s
            LIMIT 1
        """, [session['school_id'], session['date'], session['date']])

        sem = cursor.fetchone()

        if sem:
            sem_year = sem[1]
            sem_term = sem[2]

            cursor.execute("""
                SELECT s.id, s.student_code, s.full_name
                FROM enrollment e
                JOIN student s ON s.id = e.student_id
                WHERE e.course_id = %s AND e.year = %s AND e.term = %s
                ORDER BY s.student_code
            """, [session['course_id'], sem_year, sem_term])

            students = cursor.fetchall()
        else:
            cursor.execute("""
                SELECT s.id, s.student_code, s.full_name
                FROM enrollment e
                JOIN student s ON s.id = e.student_id
                WHERE e.course_id = %s
                ORDER BY s.student_code
                LIMIT 200
            """, [session['course_id']])
            students = cursor.fetchall()

    students_list = [{'id': s[0], 'code': s[1], 'name': s[2]} for s in students]

    # --------------------------
    # 7) Generate QR
    # --------------------------
    qr_url = f"http://127.0.0.1:8000/attendance/scan/{session['token']}/"

    qr = qrcode.QRCode(box_size=10, border=3)
    qr.add_data(qr_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    qr_base64 = base64.b64encode(buf.getvalue()).decode()

    # --------------------------
    # 8) Render
    # --------------------------
    return render(request, "teacher/session_detail.html", {
        "session": session,
        "course": course,
        "students": students_list,
        "teacher": teacher,
        "location": location,
        "slot_name": slot_name,
        "slot_range": slot_range,
        "qr_base64": qr_base64,
        "qr_url": qr_url,
        "now": timezone.now(),
    })

def attendance_scan(request, token):
    """
    Student QR attendance verification endpoint
    Steps:
      1) Validate QR → class_session record
      2) GET → form
      3) POST → student_code, lat, lon, device_id
      4) Validate expiry, GPS, student, device
      5) Save attendance
    """

    # -----------------------------------------
    # 1) Load session by token
    # -----------------------------------------
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, teacher_id, course_id, school_id, location_id,
                   lesson_type_id, time_setting_id, name, date,
                   token, expires_at
            FROM class_session
            WHERE token = %s
            LIMIT 1
        """, [token])
        row = cursor.fetchone()

    if not row:
        raise Http404("Session not found")

    session = {
        "id": row[0],
        "teacher_id": row[1],
        "course_id": row[2],
        "school_id": row[3],
        "location_id": row[4],
        "lesson_type_id": row[5],
        "time_setting_id": row[6],
        "name": row[7],
        "date": row[8],
        "token": row[9],
        "expires_at": row[10],
    }

    # -----------------------------------------
    # FIX: Normalize timezone (avoid TypeError)
    # -----------------------------------------
    expires = session["expires_at"]
    if timezone.is_naive(expires):
        expires = timezone.make_aware(expires, timezone.get_current_timezone())

    # -----------------------------------------
    # 2) GET → show QR scan form
    # -----------------------------------------
    if request.method == "GET":
        return render(request, "attendance/scan_form.html", {
            "session": session,
            "expires_at": expires
        })

    # -----------------------------------------
    # 3) POST → verify
    # -----------------------------------------
    student_code = request.POST.get("student_code", "").strip()
    lat = request.POST.get("lat")
    lon = request.POST.get("lon")
    device_id = request.POST.get("device_id")

    if not student_code:
        return JsonResponse({"ok": False, "error": "Оюутны кодоо оруулна уу."})

    if not device_id:
        return JsonResponse({"ok": False, "error": "Төхөөрөмжийн ID олдсонгүй."})

    # -----------------------------------------
    # QR expiry
    # -----------------------------------------
    if expires < timezone.now():
        return JsonResponse({"ok": False, "error": "QR кодын хугацаа дууссан."})

    # -----------------------------------------
    # 4) Load Student
    # -----------------------------------------
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, student_code, full_name
            FROM student
            WHERE student_code = %s
            LIMIT 1
        """, [student_code])
        s = cursor.fetchone()

    if not s:
        return JsonResponse({"ok": False, "error": "Ийм оюутны код бүртгэлгүй байна."})

    student_id = s[0]

    # -----------------------------------------
    # 5) GPS location check
    # -----------------------------------------
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT latitude, longitude, radius_m
            FROM location
            WHERE id = %s
        """, [session["location_id"]])
        loc = cursor.fetchone()

    if loc:
        loc_lat, loc_lon, radius = loc

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371000
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlam = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
            return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

        try:
            dist = haversine(float(lat), float(lon), float(loc_lat), float(loc_lon))
            if dist > radius:
                return JsonResponse({"ok": False, "error": "Байршил хичээлийн байрлалаас гадуур байна."})
        except:
            return JsonResponse({"ok": False, "error": "GPS мэдээлэл буруу байна."})

    # -----------------------------------------
    # 6) Device Registration Check
    # -----------------------------------------
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, device_id
            FROM device_registry
            WHERE student_id = %s
            LIMIT 1
        """, [student_id])
        dev = cursor.fetchone()

    if dev:
        # device mismatch = reject
        if dev[1] != device_id:
            return JsonResponse({
                "ok": False,
                "error": "Бүртгэлтэй төхөөрөмж биш байна."
            })
    else:
        # Register first device
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO device_registry (student_id, device_id, device_info, created_at)
                VALUES (%s, %s, %s, NOW())
            """, [student_id, device_id, "AUTO-REGISTERED"])

    # -----------------------------------------
    # 7) Insert attendance
    # -----------------------------------------
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO attendance
            (session_id, student_id, timestamp, lat, lon, success, note, device_id, device_info)
            VALUES (%s, %s, NOW(), %s, %s, TRUE, 'OK', %s, %s)
        """, [
            session["id"],
            student_id,
            lat,
            lon,
            device_id,
            "ATTEND"
        ])

    return JsonResponse({"ok": True, "message": "Амжилттай ирц бүртгэгдлээ!"})

def _get_cookie_user_id(request):
    try:
        return int(request.COOKIES.get('user_id'))
    except:
        return None

def pattern_detail(request, pattern_id):
    """
    Show detail page for a course_schedule_pattern:
      - show pattern info
      - show dropdowns to create a session (prefilled from pattern)
      - list existing sessions for that course/teacher/time/lesson-type in the same semester/year/term
    """
    teacher_user_id = _get_cookie_user_id(request)
    if not teacher_user_id:
        return redirect('login')

    # Load pattern
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                csp.id,
                c.name AS course_name,
                c.code AS course_code,
                csp.day_of_week,
                csp.timeslot,
                COALESCE(lt.value, '') AS lesson_type,
                l.name AS location,
                lt.id AS lesson_type_id,
                l.id AS location_id,
                c.id AS course_id,
                csp.teacher_id,
                csp.semester_id,
                csp.time_setting_id,
                s.school_year, 
                s.term,
                s.school_id
            FROM course_schedule_pattern csp
            JOIN course c ON c.id = csp.course_id
            LEFT JOIN lesson_type lt ON lt.id = csp.lesson_type_id
            LEFT JOIN location l ON l.id = csp.location_id
            LEFT JOIN semester s ON s.id = csp.semester_id
            WHERE csp.id = %s
            LIMIT 1
        """, [pattern_id])
        r = cursor.fetchone()

    if not r:
        raise Http404("Pattern олдсонгүй")

    pattern = {
        "id": r[0],
        "course": r[1],
        "course_code": r[2],
        "day_of_week": r[3],
        "day": ["Даваа","Мягмар","Лхагва","Пүрэв","Баасан","Бямба","Ням"][r[3]] if isinstance(r[3], int) and 0 <= r[3] <= 6 else r[3],
        "timeslot": r[4],
        "lesson_type": r[5] or "",
        "location": r[6] or "",
        "lesson_type_id": r[7],
        "location_id": r[8],
        "course_id": r[9],
        "teacher_id": r[10],
        "semester_id": r[11],
        "time_setting_id": r[12],
        "school_year": r[13],
        "term": r[14],
        "school_id": r[15] if r[15] else None
    }

    # Load selectable lists
    # lesson types
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, value FROM lesson_type ORDER BY id")
        lesson_types = [{"id": rr[0], "name": rr[1], "value": rr[2]} for rr in cursor.fetchall()]

    # locations (limit to school's locations if possible)
    with connection.cursor() as cursor:
        if pattern.get("school_id"):
            cursor.execute("SELECT id, name FROM location WHERE id = %s ORDER BY id", [pattern["location_id"]])
        else:
            cursor.execute("SELECT id, name FROM location ORDER BY id")
        locations = [{"id": rr[0], "name": rr[1]} for rr in cursor.fetchall()]

    # time_settings for the location (if provided)
    timeslots = []
    with connection.cursor() as cursor:
        if pattern.get("location_id"):
            cursor.execute("""
                SELECT id, name, value, start_time, end_time FROM time_setting
                WHERE location_id = %s
                ORDER BY start_time NULLS LAST, id
            """, [pattern["location_id"]])
            for t in cursor.fetchall():
                timeslots.append({"id": t[0], "name": t[1], "slot": t[2], "start_time": t[3], "end_time": t[4]})

    # semesters (distinct recent)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, school_year, term, start_date, end_date
            FROM semester
            WHERE school_id = %s OR %s IS NULL
            ORDER BY school_year DESC, term DESC
            LIMIT 20
        """, [pattern.get("school_id"), pattern.get("school_id")])
        semesters = [{"id": s[0], "year": s[1], "term": s[2], "start_date": s[3], "end_date": s[4]} for s in cursor.fetchall()]

    # Determine semester to filter existing sessions:
    semester_start = None
    semester_end = None
    if pattern.get("school_year") and pattern.get("term"):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT start_date, end_date FROM semester
                WHERE school_year = %s AND term = %s
                ORDER BY id DESC LIMIT 1
            """, [pattern["school_year"], pattern["term"]])
            srow = cursor.fetchone()
            if srow:
                semester_start, semester_end = srow[0], srow[1]

    # Load existing sessions for this pattern's course/teacher/time/lesson within semester date range (if available)
    sessions = []
    with connection.cursor() as cursor:
        q = """
            SELECT s.id, s.name, s.date, s.token, s.expires_at, ts.name AS timeslot_name, lt.value AS lesson_type
            FROM class_session s
            LEFT JOIN time_setting ts ON ts.id = s.time_setting_id
            LEFT JOIN lesson_type lt ON lt.id = s.lesson_type_id
            WHERE s.course_id = %s AND s.teacher_id = %s
        """
        params = [pattern["course_id"], pattern["teacher_id"]]

        # Filter by time_setting_id and lesson_type_id if available (narrow)
        if pattern.get("time_setting_id"):
            q += " AND s.time_setting_id = %s"
            params.append(pattern["time_setting_id"])
        if pattern.get("lesson_type_id"):
            q += " AND s.lesson_type_id = %s"
            params.append(pattern["lesson_type_id"])

        if semester_start and semester_end:
            q += " AND s.date >= %s AND s.date <= %s"
            params.extend([semester_start, semester_end])

        q += " ORDER BY s.date DESC LIMIT 200"

        cursor.execute(q, params)
        for rr in cursor.fetchall():
            sessions.append({
                "id": rr[0],
                "name": rr[1],
                "date": rr[2],
                "token": rr[3],
                "expires_at": rr[4],
                "timeslot_name": rr[5],
                "lesson_type": rr[6],
                "url": request.build_absolute_uri(reverse('session_detail', args=[str(rr[3])])) if rr[3] else None
            })

    return render(request, "teacher/pattern_detail.html", {
        "pattern": pattern,
        "lesson_types": lesson_types,
        "locations": locations,
        "timeslots": timeslots,
        "semesters": semesters,
        "sessions": sessions,
    })

def pattern_create_session(request, pattern_id):
    """
    Create a session from the pattern-detail form.
    Accepts POST fields:
      - name
      - session_date (YYYY-MM-DD)
      - duration_minutes
      - lesson_type_id
      - time_setting_id
      - location_id
      - course_id
      - optionally school_year & term (to find semester -> school_id)
    Returns JSON similar to create_session.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    teacher_user_id = _get_cookie_user_id(request)
    if not teacher_user_id:
        return JsonResponse({'error': 'unauthenticated'}, status=403)

    # basic required
    session_date = request.POST.get('session_date') or timezone.now().date().isoformat()
    try:
        session_date_obj = datetime.date.fromisoformat(session_date)
    except:
        return JsonResponse({'error': 'invalid date'}, status=400)

    duration_minutes = int(request.POST.get('duration_minutes') or 10)
    name = request.POST.get('name') or ''
    lesson_type_id = request.POST.get('lesson_type_id') or None
    time_setting_id = request.POST.get('time_setting_id') or None
    location_id = request.POST.get('location_id') or None
    course_id = request.POST.get('course_id') or None

    # Load pattern to verify teacher/course if needed
    with connection.cursor() as cursor:
        cursor.execute("SELECT teacher_id, course_id, semester_id, location_id, lesson_type_id, time_setting_id FROM course_schedule_pattern WHERE id=%s LIMIT 1", [pattern_id])
        p = cursor.fetchone()
    if not p:
        return JsonResponse({'error': 'pattern not found'}, status=404)

    pattern_teacher_id, pattern_course_id, pattern_semester_id, pattern_location_id, pattern_ltid, pattern_time_setting_id = p

    # permission: ensure cookie user matches pattern owner
    with connection.cursor() as cursor:
        cursor.execute("SELECT user_id FROM teacher_profile WHERE id = %s", [pattern_teacher_id])
        tp_row = cursor.fetchone()
    if not tp_row:
        return JsonResponse({'error': 'teacher profile not found'}, status=404)
    pattern_user_id = tp_row[0]
    if pattern_user_id != teacher_user_id:
        return JsonResponse({'error': 'permission denied'}, status=403)

    # fallback to pattern values if fields not provided
    if not course_id:
        course_id = pattern_course_id
    if not lesson_type_id:
        lesson_type_id = pattern_ltid
    if not time_setting_id:
        time_setting_id = pattern_time_setting_id
    if not location_id:
        location_id = pattern_location_id

    # derive school_id from semester if posted school_year & term given, else from pattern_semester_id
    school_id = None
    school_year = request.POST.get('school_year')
    term = request.POST.get('term')
    if school_year and term:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, school_id FROM semester WHERE school_year = %s AND term = %s LIMIT 1", [school_year, term])
            srow = cursor.fetchone()
            if srow:
                school_id = srow[1]
    if not school_id and pattern_semester_id:
        with connection.cursor() as cursor:
            cursor.execute("SELECT school_id FROM semester WHERE id = %s LIMIT 1", [pattern_semester_id])
            srow = cursor.fetchone()
            if srow:
                school_id = srow[0]

    # Insert class_session
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO class_session
                    (teacher_id, course_id, school_id, location_id, lesson_type_id, time_setting_id,
                     name, date, expires_at, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s, now() + (%s || ' minutes')::interval, NOW())
                    RETURNING id, token, expires_at
                """, [
                    pattern_teacher_id, course_id, school_id, location_id,
                    lesson_type_id, time_setting_id, name or f"Session {session_date}", session_date_obj,
                    str(duration_minutes)
                ])
                row = cursor.fetchone()
                session_id, token, expires_at = row
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    session_url = request.build_absolute_uri(reverse('session_detail', args=[str(token)]))
    return JsonResponse({'ok': True, 'session_id': session_id, 'token': str(token), 'expires_at': expires_at.isoformat(), 'url': session_url})
