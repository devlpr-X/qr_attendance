# app_core/views/schedule.py - ШИНЭЧИЛСЭН
# Raw SQL ашиглан одоо байгаа таблицуудтай ажиллах

from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from ..utils import _is_admin, set_cookie_safe, get_cookie_safe
from datetime import datetime, timedelta, date
import json

def school_timeslots_config(request):
    """Сургуулийн цагийн хуваарь тохиргоо"""
    if not _is_admin(request):
        return redirect('login')
    
    timeslots = []
    with connection.cursor() as cursor:
        cursor.execute("SELECT value FROM school_setting WHERE key = 'school_timeslots'")
        result = cursor.fetchone()
        if result and result[0]:
            try:
                timeslots = json.loads(result[0])
            except:
                pass
    
    if request.method == 'POST':
        timeslots_json = request.POST.get('timeslots_json', '[]')
        try:
            slots = json.loads(timeslots_json)
            
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM school_setting WHERE key = 'school_timeslots'")
                cursor.execute("""
                    INSERT INTO school_setting (key, value, description)
                    VALUES (%s, %s, %s)
                """, ['school_timeslots', json.dumps(slots), 'Сургуулийн цагийн хуваарь'])
            
            response = redirect('timeslots_config')
            set_cookie_safe(response, 'flash_msg', 'Цагийн хуваарь хадгалагдлаа', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response
        except Exception as e:
            return render(request, 'admin/schedule/timeslots_config.html', {
                'timeslots': timeslots,
                'error': f'JSON алдаа: {str(e)}'
            })
    
    return render(request, 'admin/schedule/timeslots_config.html', {
        'timeslots': timeslots
    })

def _fetchall_dict(cursor):
    cols = [c[0] for c in cursor.description]
    rows = cursor.fetchall()
    return [dict(zip(cols, r)) for r in rows]

def get_school_timeslots(school_id=None):
    """
    Return list of timeslot dicts for given school_id.
    We read from time_setting: if rows exist for that school -> use those,
    otherwise allow global ones (location_id IS NULL) or fallback to ref_constant timeslot.
    """
    with connection.cursor() as cursor:
        if school_id:
            cursor.execute("""
                SELECT id, name, value, start_time, end_time
                FROM time_setting
                WHERE location_id = %s
                ORDER BY start_time
            """, [school_id])
            rows = cursor.fetchall()
            if rows:
                return [{'id': r[0], 'name': r[1], 'slot': r[2], 'start_time': r[3], 'end_time': r[4]} for r in rows]

        # fallback: global time_setting where location_id IS NULL
        with connection.cursor() as cursor2:
            cursor2.execute("""
                SELECT id, name, value, start_time, end_time
                FROM time_setting
                WHERE location_id IS NULL
                ORDER BY start_time
            """)
            rows2 = cursor2.fetchall()
            if rows2:
                return [{'id': r[0], 'name': r[1], 'slot': r[2], 'start_time': r[3], 'end_time': r[4]} for r in rows2]


# --------------------------
# Semester list / create
# --------------------------
# app_core/views/schedule.py  (semester_list FIXED)

def semester_list(request):
    """Семестрийн жагсаалт — сургуулиар шүүх боломжтой"""

    if not _is_admin(request):
        return redirect('login')

    selected_school = request.GET.get("school_id")

    # Load all schools (location table)
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM location ORDER BY name")
        schools = cursor.fetchall()

    params = []
    where = ""

    if selected_school:
        where = "WHERE school_id = %s"
        params.append(selected_school)

    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT id, school_year, term, name, start_date, end_date, is_active, school_id
            FROM semester
            {where}
            ORDER BY school_year DESC, term DESC
        """, params)
        rows = cursor.fetchall()

    semesters = [{
        'id': r[0],
        'school_year': r[1],
        'term': r[2],
        'name': r[3],
        'start_date': r[4],
        'end_date': r[5],
        'is_active': r[6],
        'school_id': r[7],
    } for r in rows]

    return render(request, 'admin/schedule/semester_list.html', {
        'semesters': semesters,
        'schools': schools,
        'selected_school': int(selected_school) if selected_school else None
    })


def semester_create(request):
    if not _is_admin(request):
        return redirect('login')

    # load schools (we use location as school)
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM location ORDER BY name")
        schools = cursor.fetchall()  # list of tuples (id, name)
        print("schools: ", schools)
        
    if request.method == 'POST':
        school_id = request.POST.get('school_id') or None
        school_id = int(school_id) if school_id else None

        school_year = request.POST.get('school_year', '').strip()
        term = request.POST.get('term', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()

        if not all([school_year, term, start_date, end_date, school_id]):
            return render(request, 'admin/schedule/semester_create.html', {
                'error': 'Бүх талбарыг бөглөнө үү',
                'schools': schools,
                'school_year': school_year,
                'term': term,
                'start_date': start_date,
                'end_date': end_date,
                'selected_school_id': school_id
            })

        try:
            year_int = int(school_year)
            term_int = int(term)
            if term_int not in [1, 2]:
                raise ValueError('Семестр 1 эсвэл 2 байх ёстой')

            with transaction.atomic():
                with connection.cursor() as cursor:
                    # check duplicate for this school
                    cursor.execute("""
                        SELECT id FROM semester
                        WHERE school_year = %s AND term = %s AND school_id = %s
                        LIMIT 1
                    """, [year_int, term_int, school_id])
                    if cursor.fetchone():
                        return render(request, 'admin/schedule/semester_create.html', {
                            'error': f'{year_int} оны {term_int}-р семестр тухайн сургууль дээр аль хэдийн байна',
                            'schools': schools,
                            'selected_school_id': school_id
                        })

                    # deactivate previous active semesters for this school only
                    cursor.execute("""
                        UPDATE semester SET is_active = FALSE
                        WHERE school_id = %s AND is_active = TRUE
                    """, [school_id])

                    # insert new semester linked to school
                    cursor.execute("""
                        INSERT INTO semester (school_year, term, start_date, end_date, is_active, created_at, name, school_id)
                        VALUES (%s, %s, %s, %s, TRUE, now(), %s, %s)
                        RETURNING id
                    """, [year_int, term_int, start_date, end_date, f"{year_int} оны {term_int}-р семестр", school_id])

                    sem_id = cursor.fetchone()[0]

            response = redirect('schedule_edit', semester_id=sem_id)
            set_cookie_safe(response, 'flash_msg', f'{year_int} оны {term_int}-р семестр амжилттай үүслээ', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response

        except ValueError as e:
            return render(request, 'admin/schedule/semester_create.html', {
                'error': f'Алдаа: {str(e)}',
                'schools': schools,
                'selected_school_id': school_id
            })
        except Exception as e:
            return render(request, 'admin/schedule/semester_create.html', {
                'error': f'Өгөгдлийн сангийн алдаа: {str(e)}',
                'schools': schools,
                'selected_school_id': school_id
            })

    # GET
    return render(request, 'admin/schedule/semester_create.html', {
        'schools': schools,
        'selected_school_id': None
    })


# # --------------------------
# # schedule_edit (patterns & generate sessions)
# # --------------------------
# def get_school_timeslots(location_id=None):
#     """
#     Return list of dicts: [{'name': '1-р цаг', 'slot': '08:30:09:00'}, ...]
#     If location_id is None -> return all timeslots (ordered by start_time).
#     """
#     with connection.cursor() as cursor:
#         if location_id:
#             cursor.execute("""
#                 SELECT name,
#                        (to_char(start_time, 'HH24:MI') || '-' || to_char(end_time, 'HH24:MI')) AS slot,
#                        start_time
#                 FROM time_setting
#                 WHERE location_id = %s
#                 ORDER BY start_time
#             """, [location_id])
#         else:
#             cursor.execute("""
#                 SELECT name,
#                        (to_char(start_time, 'HH24:MI') || '-' || to_char(end_time, 'HH24:MI')) AS slot,
#                        start_time
#                 FROM time_setting
#                 ORDER BY start_time
#             """)
#         rows = cursor.fetchall()
#     return [{'name': r[0], 'slot': r[1]} for r in rows]

@csrf_protect
def schedule_edit(request, semester_id):
    """
    Edit schedule for a semester (semester.school_id determines the school/location context).
    Supports:
     - GET: render timetable view (patterns, timeslots, courses, teachers, locations, lesson_types)
     - POST actions: add_pattern, delete_pattern, generate_sessions
    Uses raw SQL (connection.cursor).
    """
    if not _is_admin(request):
        return redirect('login')

    # 1) Load semester and its school context
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, school_year, term, start_date, end_date, name, school_id
            FROM semester
            WHERE id = %s
        """, [semester_id])
        sem = cursor.fetchone()

    if not sem:
        r = redirect('semester_list')
        set_cookie_safe(r, 'flash_msg', 'Семестр олдсонгүй', 5)
        set_cookie_safe(r, 'flash_status', 404, 5)
        return r

    semester = {
        'id': sem[0],
        'school_year': sem[1],
        'term': sem[2],
        'start_date': sem[3],
        'end_date': sem[4],
        'name': sem[5],
        'school_id': sem[6],
    }

    school_id = semester['school_id']  # may be None

    # 2) Load existing patterns for this semester
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT csp.id,
                   c.name AS course_name, c.code AS course_code,
                   t.name AS teacher_name,
                   csp.day_of_week, csp.timeslot,
                   lt.value AS lesson_type_name, 
                   l.name AS location_name,
                   csp.frequency, csp.start_from_date,
                   lt.id AS lesson_type_id
            FROM course_schedule_pattern csp
            JOIN course c ON c.id = csp.course_id
            JOIN teacher_profile t ON t.id = csp.teacher_id
            LEFT JOIN location l ON l.id = csp.location_id
            LEFT JOIN lesson_type lt ON lt.id = csp.lesson_type_id
            WHERE csp.semester_id = %s
            ORDER BY csp.day_of_week, csp.timeslot
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
            'start_from_date': r[9],
            'lesson_type_id':r[10]
        }
        # compute day name safely
        try:
            p['day'] = day_names[int(p['day_of_week'])]
        except Exception:
            p['day'] = str(p['day_of_week'])
        patterns.append(p)

    # 3) Handle POST actions
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_pattern':
            # required fields
            course_id = request.POST.get('course_id')
            teacher_id = request.POST.get('teacher_id')
            day = request.POST.get('day_of_week')
            timeslot = request.POST.get('timeslot')
            time_setting_id = request.POST.get('time_setting_id')
            lesson_type_id = request.POST.get('lesson_type_id')
            location_id = request.POST.get('location_id') or None
            frequency = request.POST.get('frequency', '1')
            start_from_date = request.POST.get('start_from_date') or None

            # basic validation
            if not all([course_id, teacher_id, day, timeslot, lesson_type_id]):
                return render(request, 'admin/schedule/schedule_edit.html', {
                    'semester': semester,
                    'patterns': patterns,
                    'courses': [],
                    'teachers': [],
                    'locations': [],
                    'timeslots': get_school_timeslots(school_id),
                    'lesson_types': [],
                    'error': 'Бүх шаардлагатай талбарыг бөглөнө үү'
                })

            try:
                freq_int = int(frequency)
            except ValueError:
                freq_int = 1

            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO course_schedule_pattern
                            (semester_id, course_id, teacher_id, day_of_week, timeslot,
                            lesson_type_id, location_id, frequency, start_from_date, time_setting_id)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """, [
                            semester_id, course_id, teacher_id, day, timeslot,
                            lesson_type_id, location_id, freq_int, start_from_date, time_setting_id
                        ])

                r = redirect('schedule_edit', semester_id=semester_id)
                set_cookie_safe(r, 'flash_msg', 'Хичээлийн хуваарь амжилттай нэмэгдлээ', 5)
                set_cookie_safe(r, 'flash_status', 200, 5)
                return r
            except Exception as e:
                # Fall back to render with error
                return render(request, 'admin/schedule/schedule_edit.html', {
                    'semester': semester,
                    'patterns': patterns,
                    'courses': [],
                    'teachers': [],
                    'locations': [],
                    'timeslots': get_school_timeslots(school_id),
                    'lesson_types': [],
                    'error': f'Хадгалах үед алдаа: {str(e)}'
                })

        elif action == 'delete_pattern':
            pattern_id = request.POST.get('pattern_id')
            if pattern_id:
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            # ensure pattern belongs to this semester for safety
                            cursor.execute("""
                                DELETE FROM course_schedule_pattern
                                WHERE id = %s AND semester_id = %s
                            """, [pattern_id, semester_id])
                    r = redirect('schedule_edit', semester_id=semester_id)
                    set_cookie_safe(r, 'flash_msg', 'Хуваарь устгагдлаа', 5)
                    set_cookie_safe(r, 'flash_status', 200, 5)
                    return r
                except Exception as e:
                    r = redirect('schedule_edit', semester_id=semester_id)
                    set_cookie_safe(r, 'flash_msg', f'Устгах үед алдаа: {str(e)}', 6)
                    set_cookie_safe(r, 'flash_status', 500, 6)
                    return r

        elif action == 'generate_sessions':
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT * FROM generate_sessions_for_semester(%s)", [semester_id])
                    res = cursor.fetchone()
                    if res:
                        generated_count = res[0]
                        error_msg = res[1]
                    else:
                        generated_count = 0
                        error_msg = None
                r = redirect('schedule_edit', semester_id=semester_id)
                if error_msg:
                    set_cookie_safe(r, 'flash_msg', f'Алдаа: {error_msg}', 6)
                    set_cookie_safe(r, 'flash_status', 500, 6)
                else:
                    set_cookie_safe(r, 'flash_msg', f'{generated_count} сесс үүслээ', 6)
                    set_cookie_safe(r, 'flash_status', 200, 6)
                return r
            except Exception as e:
                r = redirect('schedule_edit', semester_id=semester_id)
                set_cookie_safe(r, 'flash_msg', f'Сесс үүсгэх алдаа: {str(e)}', 6)
                set_cookie_safe(r, 'flash_status', 500, 6)
                return r

    # 4) GET: load dropdowns filtered by school (if available)
    with connection.cursor() as cursor:
        # courses (all courses)
        cursor.execute("SELECT id, name, code FROM course ORDER BY name")
        courses = cursor.fetchall()

        # teachers (all)
        cursor.execute("SELECT id, name FROM teacher_profile ORDER BY name")
        teachers = cursor.fetchall()

        # locations: prefer locations for this school_id, but if none, list all
        if school_id:
            cursor.execute("SELECT id, name FROM location WHERE id = %s ORDER BY name", [school_id])
            locations = cursor.fetchall()
            # if that returned empty, fallback to all locations
            if not locations:
                cursor.execute("SELECT id, name FROM location ORDER BY name")
                locations = cursor.fetchall()
        else:
            cursor.execute("SELECT id, name FROM location ORDER BY name")
            locations = cursor.fetchall()

        cursor.execute("""
            SELECT id, name, value FROM lesson_type
            ORDER BY id
        """, [school_id])
        lesson_types = cursor.fetchall()

    timeslots = get_school_timeslots(school_id)

    # render
    return render(request, 'admin/schedule/schedule_edit.html', {
        'semester': semester,
        'patterns': patterns,
        'courses': courses,
        'teachers': teachers,
        'locations': locations,
        'lesson_types': lesson_types,
        'timeslots': timeslots,
    })


# --------------------------
# Teacher dashboard: weekly schedule
# --------------------------
def teacher_dashboard_schedule(request):
    user_id = get_cookie_safe(request, 'user_id')
    if not user_id:
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, school_year, term, start_date, end_date
            FROM semester WHERE is_active = TRUE
            ORDER BY id DESC LIMIT 1
        """)
        sem = cursor.fetchone()

    if not sem:
        return render(request, 'teacher/dashboard.html', {'error': 'Идэвхтэй семестр олдсонгүй'})

    semester = {'id': sem[0], 'school_year': sem[1], 'term': sem[2], 'start_date': sem[3], 'end_date': sem[4]}

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT cs.id, c.name, c.code,
                   cs.day_of_week, cs.timeslot,
                   cs.lesson_type, l.name,
                   COUNT(e.id) as student_count
            FROM course_schedule_pattern cs
            JOIN course c ON c.id = cs.course_id
            LEFT JOIN location l ON l.id = cs.location_id
            LEFT JOIN enrollment e ON e.course_id = cs.course_id
            WHERE cs.semester_id = %s AND cs.teacher_id = %s
            GROUP BY cs.id, c.name, c.code, cs.day_of_week, cs.timeslot, cs.lesson_type, l.name
            ORDER BY cs.day_of_week, cs.timeslot
        """, [semester['id'], user_id])
        rows = cursor.fetchall()

    days = ['Даваа', 'Мягмар', 'Лхагва', 'Пүрэв', 'Баасан', 'Бямба', 'Ням']
    schedule_list = []
    for r in rows:
        schedule_list.append({
            'id': r[0],
            'course_name': r[1],
            'course_code': r[2],
            'day': days[r[3]],
            'timeslot': r[4],
            'lesson_type': r[5],
            'location': r[6] or 'Заагаагүй',
            'student_count': r[7]
        })

    return render(request, 'teacher/dashboard.html', {
        'semester': semester,
        'schedules': schedule_list
    })

# views/schedule.py
def semester_delete(request, semester_id):
    if not _is_admin(request):
        return redirect("login")

    if request.method == "POST":
        with connection.cursor() as cursor:
            print("DELETE FROM semester WHERE id = %s", [semester_id])
            cursor.execute("DELETE FROM semester WHERE id = %s", [semester_id])

        r = redirect("semester_list")
        set_cookie_safe(r, "flash_msg", "Семестр устгалаа", 5)
        set_cookie_safe(r, "flash_status", 200, 5)
        return r

    return redirect("semester_list")


def teacher_dashboard_schedule(request):
    """Багшийн хичээлийн хуваарь"""
    user_id = get_cookie_safe(request, 'user_id')
    if not user_id:
        return redirect('login')
    
    with connection.cursor() as cursor:
        # Идэвхтэй семестр авах
        cursor.execute("""
            SELECT id, school_year, term, start_date, end_date 
            FROM semester WHERE is_active = TRUE
            ORDER BY id DESC LIMIT 1
        """)
        sem = cursor.fetchone()
        
        if not sem:
            return render(request, 'teacher/dashboard.html', {
                'error': 'Идэвхтэй семестр олдсонгүй',
                'weeks': {}
            })
        
        semester = {
            'id': sem[0],
            'school_year': sem[1],
            'term': sem[2],
            'start_date': sem[3],
            'end_date': sem[4]
        }
        
        # Энэ багшийн сессүүдийг авах
        cursor.execute("""
            SELECT gs.id, c.name, c.code, gs.session_date,
                   gs.timeslot, gs.lesson_type, 
                   COALESCE(l.name, 'Заагаагүй') as location,
                   COALESCE(COUNT(e.id), 0) as student_count,
                   gs.token
            FROM generated_session gs
            JOIN course c ON c.id = gs.course_id
            LEFT JOIN location l ON l.id = gs.location_id
            LEFT JOIN enrollment e ON e.course_id = gs.course_id
            WHERE gs.semester_id = %s AND gs.teacher_id = %s
            GROUP BY gs.id, c.name, c.code, gs.session_date, 
                     gs.timeslot, gs.lesson_type, l.name, gs.token
            ORDER BY gs.session_date, gs.timeslot
        """, [semester['id'], user_id])
        
        sessions = cursor.fetchall()
    
    # Долоо хоногоор бүлэглэх
    days = ['Даваа', 'Мягмар', 'Лхагва', 'Пүрэв', 'Баасан', 'Бямба', 'Ням']
    grouped_by_week = {}
    
    for s in sessions:
        session_date = s[3]
        week_start = session_date - timedelta(days=session_date.weekday())
        week_key = week_start.strftime('%Y-%m-%d')
        
        if week_key not in grouped_by_week:
            grouped_by_week[week_key] = []
        
        grouped_by_week[week_key].append({
            'id': s[0],
            'course_name': s[1],
            'course_code': s[2],
            'session_date': s[3],
            'day_name': days[s[3].weekday()],
            'timeslot': s[4],
            'lesson_type': s[5],
            'location': s[6],
            'student_count': s[7],
            'token': s[8]
        })
    
    return render(request, 'teacher/dashboard.html', {
        'semester': semester,
        'weeks': grouped_by_week,
        'days': days
    })