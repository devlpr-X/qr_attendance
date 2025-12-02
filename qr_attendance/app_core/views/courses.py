# app_core/views/courses.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from ..utils import _is_admin, set_cookie_safe, get_cookie_safe

def courses_crud(request):
    if not _is_admin(request):
        return redirect('login')

    mode = request.GET.get('mode', 'list')
    course_id = request.GET.get('id')

    # =====================================================================
    # LIST + SEARCH + PAGINATION
    # =====================================================================
    if mode == 'list':
        q = request.GET.get('q', '').strip()

        page = int(request.GET.get('page', 1))
        page_size = 5
        offset = (page - 1) * page_size

        where_sql = ""
        params = []

        if q:
            where_sql = "WHERE name ILIKE %s OR code ILIKE %s"
            params = [f"%{q}%", f"%{q}%"]

        with connection.cursor() as cursor:
            # count
            cursor.execute(f"SELECT COUNT(*) FROM course {where_sql}", params)
            total = cursor.fetchone()[0]

            total_pages = (total + page_size - 1) // page_size

            # fetch
            cursor.execute(f"""
                SELECT id, name, code
                FROM course
                {where_sql}
                ORDER BY id DESC
                LIMIT %s OFFSET %s
            """, params + [page_size, offset])
            rows = cursor.fetchall()

        courses = [{'id': r[0], 'name': r[1], 'code': r[2]} for r in rows]

        return render(request, 'admin/courses/crud.html', {
            'mode': 'list',
            'courses': courses,
            'q': q,
            'page': page,
            'total_pages': total_pages
        })

    # =====================================================================
    # ADD
    # =====================================================================
    if mode == 'add':
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip()

            if not name:
                res = redirect('/admin/courses/?mode=add')
                set_cookie_safe(res, 'flash_msg', 'Хичээлийн нэр заавал.', 6)
                set_cookie_safe(res, 'flash_status', 400, 6)
                return res

            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO course (name, code)
                            VALUES (%s, %s)
                        """, [name, code or None])

                res = redirect('/admin/courses/?mode=list')
                set_cookie_safe(res, 'flash_msg', 'Нэмэгдлээ.', 6)
                set_cookie_safe(res, 'flash_status', 200, 6)
                return res

            except Exception as e:
                res = redirect('/admin/courses/?mode=add')
                set_cookie_safe(res, 'flash_msg', f'Алдаа: {e}', 6)
                set_cookie_safe(res, 'flash_status', 500, 6)
                return res

        return render(request, 'admin/courses/crud.html', {'mode': 'add'})

    # =====================================================================
    # EDIT
    # =====================================================================
    if mode == 'edit':
        if not course_id:
            return redirect('/admin/courses/?mode=list')

        with connection.cursor() as cursor:
            cursor.execute("SELECT id, name, code FROM course WHERE id=%s", [course_id])
            row = cursor.fetchone()

        if not row:
            res = redirect('/admin/courses/?mode=list')
            set_cookie_safe(res, 'flash_msg', 'Хичээл олдсонгүй.', 6)
            set_cookie_safe(res, 'flash_status', 404, 6)
            return res

        course = {'id': row[0], 'name': row[1], 'code': row[2]}

        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip()

            if not name:
                res = redirect(f'/admin/courses/?mode=edit&id={course_id}')
                set_cookie_safe(res, 'flash_msg', 'Нэр шаардлагатай.', 6)
                set_cookie_safe(res, 'flash_status', 400, 6)
                return res

            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            UPDATE course
                            SET name=%s, code=%s
                            WHERE id=%s
                        """, [name, code or None, course_id])

                res = redirect('/admin/courses/?mode=list')
                set_cookie_safe(res, 'flash_msg', 'Шинэчлэгдлээ.', 6)
                set_cookie_safe(res, 'flash_status', 200, 6)
                return res

            except Exception as e:
                res = redirect(f'/admin/courses/?mode=edit&id={course_id}')
                set_cookie_safe(res, 'flash_msg', f'Алдаа: {e}', 6)
                set_cookie_safe(res, 'flash_status', 500, 6)
                return res

        return render(request, 'admin/courses/crud.html', {
            'mode': 'edit',
            'course': course
        })

    # =====================================================================
    # DELETE
    # =====================================================================
    if mode == 'delete':
        if not course_id:
            return redirect('/admin/courses/?mode=list')

        with connection.cursor() as cursor:
            cursor.execute("SELECT id, name FROM course WHERE id=%s", [course_id])
            row = cursor.fetchone()

        if not row:
            res = redirect('/admin/courses/?mode=list')
            set_cookie_safe(res, 'flash_msg', 'Хичээл олдсонгүй.', 6)
            set_cookie_safe(res, 'flash_status', 404, 6)
            return res

        course = {'id': row[0], 'name': row[1]}

        if request.method == 'POST':
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM class_session WHERE course_id=%s", [course_id])
                        cursor.execute("DELETE FROM course WHERE id=%s", [course_id])

                res = redirect('/admin/courses/?mode=list')
                set_cookie_safe(res, 'flash_msg', 'Устгагдлаа.', 6)
                set_cookie_safe(res, 'flash_status', 200, 6)
                return res

            except Exception as e:
                res = redirect('/admin/courses/?mode=list')
                set_cookie_safe(res, 'flash_msg', f'Алдаа: {e}', 6)
                set_cookie_safe(res, 'flash_status', 500, 6)
                return res

        return render(request, 'admin/courses/crud.html', {
            'mode': 'delete',
            'course': course
        })

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

