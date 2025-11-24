# app_core/views/students.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from ..utils import _is_admin, set_cookie_safe, get_cookie_safe

# -------------------------
# Students CRUD
# -------------------------
def students_list(request):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, full_name, student_code FROM student ORDER BY id DESC")
        rows = cursor.fetchall()

    students = [{'id': r[0], 'full_name': r[1], 'student_code': r[2]} for r in rows]
    return render(request, 'admin/students/list.html', {'students': students})


def student_add(request):
    if not _is_admin(request):
        return redirect('login')

    if request.method == 'POST':
        full_name = (request.POST.get('full_name') or '').strip()
        student_code = (request.POST.get('student_code') or '').strip()

        if not full_name or not student_code:
            return render(request, 'admin/students/add.html', {'error': 'Нэр болон оюутны код заавал байна.'})

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    # check unique code
                    cursor.execute("SELECT id FROM student WHERE student_code = %s LIMIT 1", [student_code])
                    if cursor.fetchone():
                        return render(request, 'admin/students/add.html', {'error': 'Энэ оюутны код аль хэдийн ашиглагдсан.'})

                    cursor.execute(
                        "INSERT INTO student (full_name, student_code) VALUES (%s, %s) RETURNING id",
                        [full_name, student_code]
                    )
                    new_id = cursor.fetchone()[0]

            response = redirect('students_list')
            set_cookie_safe(response, 'flash_msg', f'Оюутан амжилттай бүртгэгдлээ (ID: {new_id}).', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response

        except Exception as e:
            return render(request, 'admin/students/add.html', {'error': f'Бүртгэх үед алдаа: {str(e)}'})

    return render(request, 'admin/students/add.html')


def student_view(request, student_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, full_name, student_code FROM student WHERE id = %s", [student_id])
        row = cursor.fetchone()
        if not row:
            response = redirect('students_list')
            set_cookie_safe(response, 'flash_msg', 'Оюутан олдсонгүй.', 6)
            set_cookie_safe(response, 'flash_status', 404, 6)
            return response

        student = {'id': row[0], 'full_name': row[1], 'student_code': row[2]}

        # enrollments
        cursor.execute("""
            SELECT e.id, e.course_id, c.name, c.code
            FROM enrollment e
            JOIN course c ON c.id = e.course_id
            WHERE e.student_id = %s
            ORDER BY c.name
        """, [student_id])
        rows = cursor.fetchall()

    enrolls = [{'id': r[0], 'course_id': r[1], 'course_name': r[2], 'course_code': r[3]} for r in rows]

    return render(request, 'admin/students/view.html', {'student': student, 'enrolls': enrolls})


def student_edit(request, student_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, full_name, student_code FROM student WHERE id = %s", [student_id])
        row = cursor.fetchone()
    if not row:
        return redirect('students_list')

    student = {'id': row[0], 'full_name': row[1], 'student_code': row[2]}

    if request.method == 'POST':
        full_name = (request.POST.get('full_name') or '').strip()
        student_code = (request.POST.get('student_code') or '').strip()
        if not full_name or not student_code:
            return render(request, 'admin/students/edit.html', {'student': student, 'error': 'Нэр болон код хоосон байж болохгүй.'})

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    # check if code used by other
                    cursor.execute("SELECT id FROM student WHERE student_code = %s AND id != %s LIMIT 1", [student_code, student_id])
                    if cursor.fetchone():
                        return render(request, 'admin/students/edit.html', {'student': student, 'error': 'Энэ код бусад оюутанд холбогдсон байна.'})

                    cursor.execute("UPDATE student SET full_name = %s, student_code = %s WHERE id = %s", [full_name, student_code, student_id])

            response = redirect('student_view', student_id=student_id)
            set_cookie_safe(response, 'flash_msg', 'Оюутны мэдээлэл шинэчлэгдлээ.', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response

        except Exception as e:
            return render(request, 'admin/students/edit.html', {'student': student, 'error': f'Шинэчлэх үед алдаа: {str(e)}'})

    return render(request, 'admin/students/edit.html', {'student': student})


def student_delete(request, student_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, full_name FROM student WHERE id = %s", [student_id])
        row = cursor.fetchone()
    if not row:
        return redirect('students_list')

    student = {'id': row[0], 'full_name': row[1]}

    if request.method == 'POST':
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM enrollment WHERE student_id = %s", [student_id])
                    cursor.execute("DELETE FROM student WHERE id = %s", [student_id])
            response = redirect('students_list')
            set_cookie_safe(response, 'flash_msg', 'Оюутан устгагдлаа.', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response
        except Exception as e:
            return render(request, 'admin/students/delete_confirm.html', {'student': student, 'error': str(e)})

    return render(request, 'admin/students/delete_confirm.html', {'student': student})


# -------------------------
# Enrollment (Оюутан-курс холболт)
# -------------------------
def enrollments_list(request):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT e.id, s.id AS student_id, s.full_name, s.student_code, c.id AS course_id, c.name, c.code
            FROM enrollment e
            JOIN student s ON s.id = e.student_id
            JOIN course c ON c.id = e.course_id
            ORDER BY e.id DESC
        """)
        rows = cursor.fetchall()

    enrolls = [{'id': r[0], 'student_id': r[1], 'student_name': r[2], 'student_code': r[3],
                'course_id': r[4], 'course_name': r[5], 'course_code': r[6]} for r in rows]
    return render(request, 'admin/enrollments/list.html', {'enrolls': enrolls})


def enrollment_add(request):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, full_name, student_code FROM student ORDER BY full_name")
        students = cursor.fetchall()
        cursor.execute("SELECT id, name, code FROM course ORDER BY name")
        courses = cursor.fetchall()

    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        course_id = request.POST.get('course_id')
        if not student_id or not course_id:
            return render(request, 'admin/enrollments/add.html', {'students': students, 'courses': courses, 'error': 'Оюутан болон хичээл сонгоно уу.'})

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT id FROM enrollment WHERE student_id = %s AND course_id = %s LIMIT 1", [student_id, course_id])
                    if cursor.fetchone():
                        return render(request, 'admin/enrollments/add.html', {'students': students, 'courses': courses, 'error': 'Энэ оюутан аль хэдийн энэ хичээлд элссэн.'})

                    cursor.execute("INSERT INTO enrollment (student_id, course_id) VALUES (%s, %s) RETURNING id", [student_id, course_id])
                    new_id = cursor.fetchone()[0]

            response = redirect('enrollments_list')
            set_cookie_safe(response, 'flash_msg', 'Элсэлт амжилттай нэмэгдлээ.', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response

        except Exception as e:
            return render(request, 'admin/enrollments/add.html', {'students': students, 'courses': courses, 'error': f'Алдаа: {str(e)}'})

    return render(request, 'admin/enrollments/add.html', {'students': students, 'courses': courses})


def enrollment_delete(request, enroll_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT e.id, s.full_name, s.student_code, c.name, c.code
            FROM enrollment e
            JOIN student s ON s.id = e.student_id
            JOIN course c ON c.id = e.course_id
            WHERE e.id = %s
        """, [enroll_id])
        row = cursor.fetchone()

    if not row:
        response = redirect('enrollments_list')
        set_cookie_safe(response, 'flash_msg', 'Элсэлт олдсонгүй.', 6)
        set_cookie_safe(response, 'flash_status', 404, 6)
        return response

    enroll = {'id': row[0], 'student_name': row[1], 'student_code': row[2], 'course_name': row[3], 'course_code': row[4]}

    if request.method == 'POST':
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM enrollment WHERE id = %s", [enroll_id])
            response = redirect('enrollments_list')
            set_cookie_safe(response, 'flash_msg', 'Элсэлт устлаа.', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response
        except Exception as e:
            return render(request, 'admin/enrollments/delete_confirm.html', {'enroll': enroll, 'error': str(e)})

    return render(request, 'admin/enrollments/delete_confirm.html', {'enroll': enroll})


# enroll for specific student (from student view)
def enroll_student_to_course(request, student_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, code FROM course ORDER BY name")
        courses = cursor.fetchall()

        cursor.execute("SELECT id, full_name, student_code FROM student WHERE id = %s", [student_id])
        s = cursor.fetchone()
        if not s:
            response = redirect('students_list')
            set_cookie_safe(response, 'flash_msg', 'Оюутан олдсонгүй.', 6)
            set_cookie_safe(response, 'flash_status', 404, 6)
            return response
        student = {'id': s[0], 'full_name': s[1], 'student_code': s[2]}

    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        if not course_id:
            return render(request, 'admin/enrollments/add_for_student.html', {'courses': courses, 'student': student, 'error': 'Хичээл сонгоно уу.'})

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT id FROM enrollment WHERE student_id = %s AND course_id = %s LIMIT 1", [student_id, course_id])
                    if cursor.fetchone():
                        return render(request, 'admin/enrollments/add_for_student.html', {'courses': courses, 'student': student, 'error': 'Энэ оюутан аль хэдийн элссэн.'})
                    cursor.execute("INSERT INTO enrollment (student_id, course_id) VALUES (%s, %s)", [student_id, course_id])

            response = redirect('student_view', student_id=student_id)
            set_cookie_safe(response, 'flash_msg', 'Элсгэлт амжилттай нэмэгдлээ.', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response
        except Exception as e:
            return render(request, 'admin/enrollments/add_for_student.html', {'courses': courses, 'student': student, 'error': str(e)})

    return render(request, 'admin/enrollments/add_for_student.html', {'courses': courses, 'student': student})


def course_enrollments(request, course_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, code FROM course WHERE id = %s", [course_id])
        c = cursor.fetchone()
        if not c:
            response = redirect('courses_list')
            set_cookie_safe(response, 'flash_msg', 'Курс олдсонгүй.', 6)
            set_cookie_safe(response, 'flash_status', 404, 6)
            return response
        course = {'id': c[0], 'name': c[1], 'code': c[2]}

        cursor.execute("""
            SELECT s.id, s.full_name, s.student_code, e.id AS enroll_id
            FROM enrollment e
            JOIN student s ON s.id = e.student_id
            WHERE e.course_id = %s
            ORDER BY s.full_name
        """, [course_id])
        rows = cursor.fetchall()

    students = [{'id': r[0], 'full_name': r[1], 'student_code': r[2], 'enroll_id': r[3]} for r in rows]
    return render(request, 'admin/enrollments/course_enrollments.html', {'course': course, 'students': students})
