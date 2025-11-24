# app_core/views/admin.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from ..utils import get_cookie_safe, _is_admin, _generate_password, _hash_md5, set_cookie_safe

# -------------------------
# Admin dashboard (unchanged)
# -------------------------
def admin_dashboard(request):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM app_user")
        total_users = cursor.fetchone()[0]

        cursor.execute("""SELECT COUNT(*) 
                       FROM app_user 
                       WHERE role_id = (SELECT id FROM ref_role WHERE name='teacher' LIMIT 1) 
                       """)
        total_teachers = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM course")
        total_courses = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM location")
        total_locations = cursor.fetchone()[0]

        cursor.execute("""
            SELECT u.id, u.email, COALESCE(t.name,'-') AS name, u.is_verified
            FROM app_user u
            LEFT JOIN teacher_profile t ON t.user_id = u.id
            WHERE u.role_id = (SELECT id FROM ref_role WHERE name='teacher' LIMIT 1)
            ORDER BY u.id DESC
            LIMIT 100
        """)
        rows = cursor.fetchall()

    teachers = [{'id': r[0], 'email': r[1], 'name': r[2], 'is_verified': r[3]} for r in rows]

    return render(request, 'admin/dashboard.html', {
        'total_users': total_users,
        'total_teachers': total_teachers,
        'total_courses': total_courses,
        'total_locations': total_locations,
        'teachers': teachers
    })


# -------------------------
# Teacher Add (flash-based)
# -------------------------
def teacher_add(request):
    if not _is_admin(request):
        return redirect('login')

    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip()
        name = (request.POST.get('name') or '').strip()
        is_verified = True if request.POST.get('is_verified') == 'on' else False
        custom_pw = (request.POST.get('password') or '').strip()

        if not email:
            response = redirect('teacher_add')
            set_cookie_safe(response, 'flash_msg', 'И-мэйл оруулна уу.', 8)
            set_cookie_safe(response, 'flash_status', 400, 8)
            return response

        # duplicate шалгах
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM app_user WHERE email = %s LIMIT 1", [email])
            if cursor.fetchone():
                response = redirect('teacher_add')
                set_cookie_safe(response, 'flash_msg', 'Энэ и-мэйл аль хэдийн бүртгэлтэй байна.', 8)
                set_cookie_safe(response, 'flash_status', 400, 8)
                return response

        if custom_pw:
            raw_pw = custom_pw
        else:
            raw_pw = _generate_password(12)

        hashed = _hash_md5(raw_pw)

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT id FROM ref_role WHERE name = 'teacher' LIMIT 1")
                    r = cursor.fetchone()
                    if not r:
                        raise Exception("ref_role-д 'teacher' мөр байхгүй байна.")
                    role_id = r[0]

                    cursor.execute("""
                        INSERT INTO app_user (email, role_id, is_verified, is_banned, created_at, hashed_password)
                        VALUES (%s, %s, %s, FALSE, now(), %s)
                        RETURNING id
                    """, [email, role_id, is_verified, hashed])
                    new_id = cursor.fetchone()[0]

                    cursor.execute("INSERT INTO teacher_profile (user_id, name) VALUES (%s, %s)", [new_id, name])

            # Амжилттай нэмэгдсэн үед flash-ээр мэдээлэх. raw password-г 8 секунд харуулна.
            response = redirect('admin_dashboard')
            set_cookie_safe(response, 'flash_msg', f"Багш амжилттай нэмэгдлээ. И-мэйл: {email} | Нууц үг: {raw_pw}", 12)
            set_cookie_safe(response, 'flash_status', 200, 12)
            return response

        except Exception as e:
            response = redirect('teacher_add')
            set_cookie_safe(response, 'flash_msg', f'Бүртгэх үед алдаа гарлаа: {str(e)}', 10)
            set_cookie_safe(response, 'flash_status', 500, 10)
            return response

    # GET
    return render(request, 'admin/teacher/add.html')


# -------------------------
# Teacher Edit (flash-based)
# -------------------------
def teacher_edit(request, user_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT u.id, u.email, u.is_verified, COALESCE(t.name,'')
            FROM app_user u
            LEFT JOIN teacher_profile t ON t.user_id = u.id
            WHERE u.id = %s
        """, [user_id])
        row = cursor.fetchone()

    if not row:
        response = redirect('admin_dashboard')
        set_cookie_safe(response, 'flash_msg', 'Тухайн хэрэглэгч олдсонгүй.', 8)
        set_cookie_safe(response, 'flash_status', 404, 8)
        return response

    user = {'id': row[0], 'email': row[1], 'is_verified': row[2], 'name': row[3]}

    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip()
        name = (request.POST.get('name') or '').strip()
        is_verified = True if request.POST.get('is_verified') == 'on' else False
        provided_pw = (request.POST.get('password') or '').strip()
        reset_generate = True if request.POST.get('reset_generate') == '1' else False

        new_password = None
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE app_user SET email=%s, is_verified=%s WHERE id=%s", [email, is_verified, user_id])
                    cursor.execute("SELECT id FROM teacher_profile WHERE user_id = %s", [user_id])
                    if cursor.fetchone():
                        cursor.execute("UPDATE teacher_profile SET name=%s WHERE user_id=%s", [name, user_id])
                    else:
                        cursor.execute("INSERT INTO teacher_profile (user_id, name) VALUES (%s, %s)", [user_id, name])

                    if provided_pw or reset_generate:
                        if provided_pw:
                            raw_pw = provided_pw
                        else:
                            raw_pw = _generate_password(12)
                        hashed = _hash_md5(raw_pw)
                        cursor.execute("UPDATE app_user SET hashed_password = %s WHERE id = %s", [hashed, user_id])
                        new_password = raw_pw

            # success flash
            if new_password:
                response = redirect('admin_dashboard')
                set_cookie_safe(response, 'flash_msg', f'Хэрэглэгч амжилттай шинэчлэгдлээ. Шинэ нууц үг: {new_password}', 12)
                set_cookie_safe(response, 'flash_status', 200, 12)
                return response
            else:
                response = redirect('admin_dashboard')
                set_cookie_safe(response, 'flash_msg', 'Хэрэглэгчийн мэдээлэл амжилттай шинэчлэгдлээ.', 8)
                set_cookie_safe(response, 'flash_status', 200, 8)
                return response

        except Exception as e:
            response = redirect('admin/teacher/{}/edit/'.format(user_id))
            set_cookie_safe(response, 'flash_msg', f'Засах үед алдаа гарлаа: {str(e)}', 10)
            set_cookie_safe(response, 'flash_status', 500, 10)
            return response

    # GET render edit page
    return render(request, 'admin/teacher/edit.html', {'user': user})


# -------------------------
# Teacher Delete (flash-based)
# -------------------------
def teacher_delete(request, user_id):
    if not _is_admin(request):
        return redirect('login')

    if request.method == 'POST':
        try:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM teacher_profile WHERE user_id = %s", [user_id])
                cursor.execute("DELETE FROM app_user WHERE id = %s", [user_id])
            response = redirect('admin_dashboard')
            set_cookie_safe(response, 'flash_msg', 'Хэрэглэгч амжилттай устгагдлаа.', 200)
            set_cookie_safe(response, 'flash_status', 200, 8)
            return response
        except Exception as e:
            response = redirect('admin_dashboard')
            set_cookie_safe(response, 'flash_msg', f'Устгах үед алдаа гарлаа: {str(e)}', 500)
            set_cookie_safe(response, 'flash_status', 500, 8)
            return response

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, email FROM app_user WHERE id = %s", [user_id])
        row = cursor.fetchone()
    if not row:
        response = redirect('admin_dashboard')
        set_cookie_safe(response, 'flash_msg', 'Хэрэглэгч олдсонгүй.', 404)
        set_cookie_safe(response, 'flash_status', 404, 8)
        return response

    return render(request, 'admin/teacher/delete_confirm.html', {'user': {'id': row[0], 'email': row[1]}})
