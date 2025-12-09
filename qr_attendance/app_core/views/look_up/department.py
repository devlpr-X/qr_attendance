# app_core/views/look_up/department.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from app_core.utils import _is_admin, set_cookie_safe
from django.views.decorators.csrf import csrf_protect
import json

@csrf_protect
def department_manage(request):
    if not _is_admin(request):
        return redirect("login")

    error = None

    if request.method == "POST":
        action = request.POST.get("action")
        # ADD
        if action == "add":
            name = (request.POST.get("name") or "").strip()
            code = (request.POST.get("code") or "").strip()
            school_id = request.POST.get("school_id") or None
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO department (school_id, name, code, created_at)
                            VALUES (%s, %s, %s, now())
                        """, [school_id, name, code])
                resp = redirect("department_manage")
                set_cookie_safe(resp, "flash_msg", "Амжилттай нэмэгдлээ", 5)
                set_cookie_safe(resp, "flash_status", 200, 5)
                return resp
            except Exception as e:
                error = f"Нэмэхэд алдаа: {e}"

        # EDIT
        elif action == "edit":
            _id = request.POST.get("id")
            name = (request.POST.get("name") or "").strip()
            code = (request.POST.get("code") or "").strip()
            school_id = request.POST.get("school_id") or None
            if not _id or not name:
                error = "Бүх талбар шаардлагатай."
            else:
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("""
                                UPDATE department
                                SET school_id=%s, name=%s, code=%s
                                WHERE id=%s
                            """, [school_id, name, code, _id])
                    resp = redirect("department_manage")
                    set_cookie_safe(resp, "flash_msg", "Амжилттай шинэчлэгдлээ", 5)
                    set_cookie_safe(resp, "flash_status", 200, 5)
                    return resp
                except Exception as e:
                    error = f"Шинэчлэхэд алдаа: {e}"

        # DELETE
        elif action == "delete":
            _id = request.POST.get("id")
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM department WHERE id=%s", [_id])
                resp = redirect("department_manage")
                set_cookie_safe(resp, "flash_msg", "Амжилттай устгалаа", 5)
                set_cookie_safe(resp, "flash_status", 200, 5)
                return resp
            except Exception as e:
                error = f"Устгахад алдаа: {e}"

    # READ LIST
    with connection.cursor() as cursor:
        # school_name-ийг JOIN хийгээд авна
        cursor.execute("""
            SELECT 
                d.id,
                d.school_id,
                d.name,
                d.code,
                COALESCE(l.name, '') AS school_name
            FROM department d
            LEFT JOIN location l ON d.school_id = l.id
            ORDER BY d.id DESC
        """)
        rows = cursor.fetchall()

        # schools dropdown-д ашиглах байршлууд
        cursor.execute("SELECT id, name FROM location ORDER BY name")
        schools = cursor.fetchall()

    # items дотор school_name нэмсэн нь ЧУХАЛ
    items = [
        {
            "id": r[0],
            "school_id": r[1],
            "name": r[2],
            "code": r[3],
            "school_name": r[4],
        }
        for r in rows
    ]

    return render(request, "admin/look_up/department_manage.html", {
        "items": json.dumps(items),
        "schools": schools,
        "error": error
    })
