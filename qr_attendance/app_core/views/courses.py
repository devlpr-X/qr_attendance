# app_core/views/courses.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from ..utils import _is_admin, set_cookie_safe, get_cookie_safe, _get_constants

# List

def courses_list(request):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, name, code
            FROM course
            ORDER BY id DESC
            LIMIT 500
        """)
        rows = cursor.fetchall()

    courses = []
    for r in rows:
        course_id, name, code = r
        courses.append({
            'id': course_id,
            'name': name,
            'code': code,
        })

    return render(request, 'admin/courses/list.html', {'courses': courses})

# Add
def course_add(request):
    if not _is_admin(request):
        return redirect('login')

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        code = (request.POST.get('code') or '').strip()

        if not name:
            response = redirect('course_add')
            set_cookie_safe(response, 'flash_msg', 'Хичээлийн нэр заавал шаардлагатай.', 6)
            set_cookie_safe(response, 'flash_status', 400, 6)
            return response

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("INSERT INTO course (name, code) VALUES (%s, %s) RETURNING id", [name, code or None])
                    new_id = cursor.fetchone()[0]

            response = redirect('courses_list')
            set_cookie_safe(response, 'flash_msg', 'Хичээл амжилттай нэмэгдлээ.', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response
        except Exception as e:
            response = redirect('course_add')
            set_cookie_safe(response, 'flash_msg', f'Хичээл нэмэхэд алдаа: {str(e)}', 500, 6)
            set_cookie_safe(response, 'flash_status', 500, 6)
            return response

    # GET
    return render(request, 'admin/courses/add.html', {})


# View (course details + class sessions list)
def course_view(request, course_id):
    # anyone logged in (admin or teacher) can view — тааруулан өөрчлөх боломжтой
    # currently restrict to admin or teacher:
    role = get_cookie_safe(request, 'role_name', '')
    if not (role == 'admin' or role == 'teacher'):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, code FROM course WHERE id = %s", [course_id])
        row = cursor.fetchone()
        if not row:
            response = redirect('courses_list')
            set_cookie_safe(response, 'flash_msg', 'Хичээл олдсонгүй.', 6)
            set_cookie_safe(response, 'flash_status', 404, 6)
            return response

        course = {'id': row[0], 'name': row[1], 'code': row[2]}

        # sessions: date, timeslot label, lesson_type label, teacher name/email, location name
        cursor.execute("""
            SELECT cs.id, cs.date, cs.timeslot,
                   COALESCE(rt.name, cs.timeslot) as timeslot_label,
                   cs.lesson_type,
                   COALESCE(rl.value, cs.lesson_type) as lesson_type_label,
                   t.name as teacher_name, u.email as teacher_email,
                   COALESCE(l.name, '') as location_name
            FROM class_session cs
            LEFT JOIN ref_constant rt ON rt.type='timeslot' AND rt.value = cs.timeslot
            LEFT JOIN ref_constant rl ON rl.type='lesson_type' AND rl.name = cs.lesson_type
            LEFT JOIN teacher_profile t ON t.id = cs.teacher_id
            LEFT JOIN app_user u ON u.id = t.user_id
            LEFT JOIN location l ON l.id = cs.location_id
            WHERE cs.course_id = %s
            ORDER BY cs.date DESC, rt.start_time NULLS LAST
        """, [course_id])
        rows = cursor.fetchall()

    sessions = []
    for r in rows:
        sessions.append({
            'id': r[0],
            'date': r[1],
            'timeslot': r[2],
            'timeslot_label': r[3],
            'lesson_type': r[4],
            'lesson_type_label': r[5],
            'teacher_name': r[6],
            'teacher_email': r[7],
            'location_name': r[8],
        })

    return render(request, 'admin/courses/view.html', {
        'course': course,
        'sessions': sessions
    })


# Edit
def course_edit(request, course_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, code FROM course WHERE id = %s", [course_id])
        row = cursor.fetchone()
        if not row:
            response = redirect('courses_list')
            set_cookie_safe(response, 'flash_msg', 'Хичээл олдсонгүй.', 6)
            set_cookie_safe(response, 'flash_status', 404, 6)
            return response

        course = {'id': row[0], 'name': row[1], 'code': row[2]}

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        code = (request.POST.get('code') or '').strip()
        if not name:
            response = redirect('course_edit', course_id=course_id)
            set_cookie_safe(response, 'flash_msg', 'Хичээлийн нэр оруулна уу.', 6)
            set_cookie_safe(response, 'flash_status', 400, 6)
            return response

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE course SET name=%s, code=%s WHERE id=%s", [name, code or None, course_id])
            response = redirect('courses_list')
            set_cookie_safe(response, 'flash_msg', 'Хичээл амжилттай шинэчлэгдлээ.', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response
        except Exception as e:
            response = redirect('course_edit', course_id=course_id)
            set_cookie_safe(response, 'flash_msg', f'Засах үед алдаа: {str(e)}', 6)
            set_cookie_safe(response, 'flash_status', 500, 6)
            return response

    return render(request, 'admin/courses/edit.html', {
        'course': course
    })


# Delete
def course_delete(request, course_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM course WHERE id=%s", [course_id])
        row = cursor.fetchone()
        if not row:
            response = redirect('courses_list')
            set_cookie_safe(response, 'flash_msg', 'Хичээл олдсонгүй.', 6)
            set_cookie_safe(response, 'flash_status', 404, 6)
            return response
        course = {'id': row[0], 'name': row[1]}

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # class_session-үүдийг устгах (хэрэв FK cascade байхгүй бол)
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM class_session WHERE course_id = %s", [course_id])
                    cursor.execute("DELETE FROM course WHERE id = %s", [course_id])

            response = redirect('courses_list')
            set_cookie_safe(response, 'flash_msg', 'Хичээл амжилттай устлаа.', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response
        except Exception as e:
            response = redirect('courses_list')
            set_cookie_safe(response, 'flash_msg', f'Устгах үед алдаа: {str(e)}', 6)
            set_cookie_safe(response, 'flash_status', 500, 6)
            return response

    return render(request, 'admin/courses/delete_confirm.html', {'course': course})
