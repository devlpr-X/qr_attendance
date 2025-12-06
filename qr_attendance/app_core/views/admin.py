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

# app_core/views/admin.py

def admin_teacher_list(request):
    if not _is_admin(request):
        return redirect("login")

    action = request.POST.get("action")

    # -----------------------------------------------------
    # 1) CREATE
    # -----------------------------------------------------
    if action == "create":
        email = request.POST.get("email", "").strip()
        name = request.POST.get("name", "").strip()
        password = request.POST.get("password", "").strip()
        is_verified = request.POST.get("is_verified") == "on"

        if not email:
            res = redirect("admin_teacher_list")
            set_cookie_safe(res, "flash_msg", "И-мэйл шаардлагатай.", 6)
            set_cookie_safe(res, "flash_status", 400, 6)
            return res

        raw_pw = password if password else _generate_password(10)
        hashed = _hash_md5(raw_pw)

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    # teacher role ID
                    cursor.execute("SELECT id FROM ref_role WHERE name='teacher' LIMIT 1")
                    role_id = cursor.fetchone()[0]

                    # create user
                    cursor.execute("""
                        INSERT INTO app_user (email, role_id, is_verified, is_banned, created_at, hashed_password)
                        VALUES (%s, %s, %s, FALSE, NOW(), %s)
                        RETURNING id
                    """, [email, role_id, is_verified, hashed])
                    user_id = cursor.fetchone()[0]

                    # teacher profile
                    cursor.execute("""
                        INSERT INTO teacher_profile (user_id, name)
                        VALUES (%s, %s)
                    """, [user_id, name])

            res = redirect("admin_teacher_list")
            set_cookie_safe(res, "flash_msg", f"Багш бүртгэгдлээ. Нууц үг: {raw_pw}", 12)
            set_cookie_safe(res, "flash_status", 200, 12)
            return res

        except Exception as e:
            res = redirect("admin_teacher_list")
            set_cookie_safe(res, "flash_msg", f"Алдаа: {str(e)}", 10)
            set_cookie_safe(res, "flash_status", 500, 10)
            return res

    # -----------------------------------------------------
    # 2) UPDATE
    # -----------------------------------------------------
    if action == "update":
        print("update")
        teacher_id = request.POST.get("id")
        email = request.POST.get("email", "").strip()
        name = request.POST.get("name", "").strip()
        password = request.POST.get("password", "").strip()
        is_verified = request.POST.get("is_verified") == "on"
        is_banned = False if is_verified == True else True
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:

                    if password:
                        hashed = _hash_md5(password)
                        cursor.execute("""
                            UPDATE app_user 
                            SET email=%s, is_verified=%s, hashed_password=%s
                            WHERE id=%s
                        """, [email, is_verified, hashed, teacher_id])
                    else:
                        cursor.execute("""
                            UPDATE app_user 
                            SET email=%s, is_verified=%s, is_banned=%s
                            WHERE id=%s
                        """, [email, is_verified, is_banned, teacher_id])

                    cursor.execute("""
                        UPDATE teacher_profile 
                        SET name=%s 
                        WHERE user_id=%s
                    """, [name, teacher_id])

            res = redirect("admin_teacher_list")
            set_cookie_safe(res, "flash_msg", "Амжилттай шинэчлэгдлээ.", 8)
            set_cookie_safe(res, "flash_status", 200, 8)
            return res

        except Exception as e:
            res = redirect("admin_teacher_list")
            set_cookie_safe(res, "flash_msg", f"Засварын алдаа: {str(e)}", 10)
            set_cookie_safe(res, "flash_status", 500, 10)
            return res

    # -----------------------------------------------------
    # 3) DELETE
    # -----------------------------------------------------
    if action == "delete":
        teacher_id = request.POST.get("id")
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM teacher_profile WHERE user_id=%s", [teacher_id])
                    cursor.execute("DELETE FROM app_user WHERE id=%s", [teacher_id])

            res = redirect("admin_teacher_list")
            set_cookie_safe(res, "flash_msg", "Устгагдлаа.", 8)
            set_cookie_safe(res, "flash_status", 200, 8)
            return res

        except Exception as e:
            res = redirect("admin_teacher_list")
            set_cookie_safe(res, "flash_msg", f"Устгах үед алдаа: {str(e)}", 10)
            set_cookie_safe(res, "flash_status", 500, 10)
            return res

    # -----------------------------------------------------
    # 4) LIST + FILTER + PAGINATION
    # -----------------------------------------------------
    search = request.GET.get("search", "").strip()
    page = int(request.GET.get("page", 1))
    page_size = 10
    offset = (page - 1) * page_size

    where = ""
    params = []

    if search:
        where = """
            AND (
                LOWER(u.email) LIKE LOWER(%s)
                OR LOWER(t.name) LIKE LOWER(%s)
            )
        """
        params.extend([f"%{search}%", f"%{search}%"])

    # TOTAL
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM app_user u
            LEFT JOIN teacher_profile t ON t.user_id = u.id
            WHERE u.role_id = (SELECT id FROM ref_role WHERE name='teacher')
            {where}
        """, params)
        total = cursor.fetchone()[0]

    # LIST
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT 
                u.id,
                u.email,
                COALESCE(t.name,'-') AS name,
                u.is_verified
            FROM app_user u
            LEFT JOIN teacher_profile t ON t.user_id = u.id
            WHERE u.role_id = (SELECT id FROM ref_role WHERE name='teacher')
            {where}
            ORDER BY t.name ASC NULLS LAST
            LIMIT %s OFFSET %s
        """, params + [page_size, offset])
        rows = cursor.fetchall()

    teachers = [
        {"id": r[0], "email": r[1], "name": r[2], "is_verified": r[3]}
        for r in rows
    ]

    last_page = (total + page_size - 1) // page_size

    return render(request, "teacher/teacher_list.html", {
        "teachers": teachers,
        "total": total,
        "page": page,
        "last_page": last_page,
        "search": search,
        "page_range": range(1, last_page + 1),
    })
