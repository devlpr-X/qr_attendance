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
    # -------------------------
    # 1) Load base datasets
    # -------------------------
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, full_name, student_code FROM student ORDER BY student_code")
        all_students = cursor.fetchall()

        cursor.execute("SELECT id, name, code FROM course ORDER BY code")
        all_courses = cursor.fetchall()

    # Distinct years
    with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT year FROM enrollment ORDER BY year DESC")
        years = [r[0] for r in cursor.fetchall()]

    # -------------------------
    # 2) Read filters (GET params)
    # -------------------------
    search = request.GET.get('search', '').strip()
    filter_course = request.GET.get('course_id') or None
    filter_year = request.GET.get('year') or None
    filter_term = request.GET.get('term') or None

    # NEW → Items per page
    per_page = request.GET.get('per_page', '30')
    try:
        per_page = int(per_page)
        if per_page <= 0:
            per_page = 30
    except:
        per_page = 30

    # -------------------------
    # 3) Build SQL query
    # -------------------------
    sql = """
        SELECT e.id,
               s.student_code,
               s.full_name,
               c.code,
               c.name,
               e.year,
               e.term
        FROM enrollment e
        JOIN student s ON s.id = e.student_id
        JOIN course c ON c.id = e.course_id
        WHERE 1=1
    """
    params = []

    if search:
        sql += """ AND (
            s.student_code ILIKE %s OR 
            s.full_name ILIKE %s OR
            c.code ILIKE %s OR
            c.name ILIKE %s
        )"""
        like = f"%{search}%"
        params.extend([like, like, like, like])

    if filter_course:
        sql += " AND e.course_id = %s"
        params.append(filter_course)

    if filter_year:
        sql += " AND e.year = %s"
        params.append(filter_year)

    if filter_term:
        sql += " AND e.term = %s"
        params.append(filter_term)

    # *** NEW ORDER: course_code → student_code ***
    sql += " ORDER BY c.code ASC, s.student_code ASC"

    # -------------------------
    # 4) Fetch rows
    # -------------------------
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()

    enrolls_raw = [{
        'id': r[0],
        'student_code': r[1],
        'student_name': r[2],
        'course_code': r[3],
        'course_name': r[4],
        'year': r[5],
        'term_display': '1-р семестр' if r[6] == 1 else '2-р семестр'
    } for r in rows]

    # -------------------------
    # 5) Pagination (per_page)
    # -------------------------
    paginator = Paginator(enrolls_raw, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Absolute row number
    for i, e in enumerate(page_obj):
        e['number'] = (page_obj.number - 1) * per_page + i + 1

    # -------------------------
    # 6) POST: Bulk insert
    # -------------------------
    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        student_ids = request.POST.getlist('student_ids')
        year = request.POST.get('year')
        term = request.POST.get('term')

        if not course_id or not student_ids:
            messages.error(request, "Хичээл болон оюутан сонгоно уу.")
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

            msg = f"Амжилттай: {inserted} элслээ."
            if skipped:
                msg += f" (Давхардсан: {skipped})"
            messages.success(request, msg)

        # Preserve filters + scroll to results
        params = request.GET.copy()
        params['scroll'] = '1'
        return redirect(f"{request.path}?{params.urlencode()}")

    # -------------------------
    # Defaults
    # -------------------------
    now = timezone.now()
    default_year = now.year
    default_term = 2 if now.month <= 7 else 1

    return render(request, 'admin/enrollments/list.html', {
        'enrolls': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,

        'all_students': all_students,
        'all_courses': all_courses,
        'years': years,

        'default_year': default_year,
        'default_term': default_term,

        # template filters
        'search': search,
        'filter_course': filter_course,
        'filter_year': filter_year,
        'filter_term': filter_term,

        # NEW: number of rows per page
        'per_page': per_page,
    })


def enrollment_delete(request, enrollment_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM enrollment WHERE id = %s", [enrollment_id])

    messages.success(request, 'Элсэлт устгагдлаа')
    return redirect('enrollments_list')