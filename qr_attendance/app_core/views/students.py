# app_core/views/students.py
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import render, redirect
from django.core.paginator import Paginator
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

    # Бүх оюутан, хичээл ачаална
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, full_name, student_code FROM student ORDER BY student_code")
        all_students = cursor.fetchall()

        cursor.execute("SELECT id, name, code FROM course ORDER BY code")
        all_courses = cursor.fetchall()

    # Онгийн жагсаалт
    with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT year FROM enrollment ORDER BY year DESC")
        years = [r[0] for r in cursor.fetchall()]

    # Шүүлтийн параметрүүд
    search = request.GET.get('search', '').strip()
    filter_course = request.GET.get('course_id')
    filter_year = request.GET.get('year')
    filter_term = request.GET.get('term')

    query = """
        SELECT e.id, s.student_code, s.full_name, c.code, c.name, e.year, e.term
        FROM enrollment e
        JOIN student s ON s.id = e.student_id
        JOIN course c ON c.id = e.course_id
        WHERE 1=1
    """
    params = []

    if search:
        query += " AND (s.student_code ILIKE %s OR s.full_name ILIKE %s OR c.code ILIKE %s OR c.name ILIKE %s)"
        like = f"%{search}%"
        params.extend([like, like, like, like])
    if filter_course:
        query += " AND e.course_id = %s"
        params.append(filter_course)
    if filter_year:
        query += " AND e.year = %s"
        params.append(filter_year)
    if filter_term:
        query += " AND e.term = %s"
        params.append(filter_term)

    query += " ORDER BY e.year DESC, e.term DESC, s.student_code"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()

    # Объект болгох
    enrolls_raw = []
    for r in rows:
        enrolls_raw.append({
            'id': r[0],
            'student_code': r[1],
            'student_name': r[2],
            'course_code': r[3],
            'course_name': r[4],
            'year': r[5],
            'term_display': '1-р семестр' if r[6] == 1 else '2-р семестр'
        })

    # Хуудаслалт: 30-н нэг хуудсанд
    paginator = Paginator(enrolls_raw, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    for i, e in enumerate(page_obj):
        e['number'] = (page_obj.number - 1) * 30 + i + 1

    # ========== POST — БӨӨНӨӨР НЭМЭХ ==========
    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        student_ids = request.POST.getlist('student_ids')
        year = request.POST.get('year')
        term = request.POST.get('term')

        if not course_id or not student_ids:
            messages.error(request, 'Хичээл болон оюутан заавал сонгоно уу.')
        else:
            inserted = skipped = 0
            with connection.cursor() as cursor:
                for sid in student_ids:
                    cursor.execute("""
                        SELECT 1 FROM enrollment
                        WHERE student_id=%s AND course_id=%s AND year=%s AND term=%s
                    """, [sid, course_id, year, term])
                    if cursor.fetchone():
                        skipped += 1
                    else:
                        cursor.execute("""
                            INSERT INTO enrollment (student_id, course_id, year, term)
                            VALUES (%s, %s, %s, %s)
                        """, [sid, course_id, year, term])
                        inserted += 1

            msg = f'Амжилттай: {inserted} оюутан элслээ.'
            if skipped:
                msg += f' (Аль хэдийн элссэн: {skipped})'
            messages.success(request, msg)

        # ГОЛ ЗАСВАР: scroll=1 нэмээд redirect хийнэ → template дээр доош гүйлгэнэ
        params = request.GET.copy()
        params['scroll'] = '1'  # Энэ нэг мөр л хангалттай
        return redirect(f"{request.path}?{params.urlencode()}")

    # Default он, семестр
    now = timezone.now()
    default_year = now.year
    default_term = 2 if now.month <= 7 else 1

    return render(request, 'admin/enrollments/list.html', {
        'enrolls': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'all_students': all_students,
        'all_courses': all_courses,
        'years': years or [now.year],
        'default_year': default_year,
        'default_term': default_term,
    })

def enrollment_delete(request, enrollment_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM enrollment WHERE id = %s", [enrollment_id])

    messages.success(request, 'Элсэлт устгагдлаа')
    return redirect('enrollments_list')