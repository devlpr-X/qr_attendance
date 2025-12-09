# app_core/views/look_up/program.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from app_core.utils import _is_admin, set_cookie_safe
from django.views.decorators.csrf import csrf_protect
import json

@csrf_protect
def program_manage(request):
    if not _is_admin(request):
        return redirect("login")

    error = None

    if request.method == "POST":
        action = request.POST.get("action")
        # ADD
        if action == "add":
            name = (request.POST.get("name") or "").strip()
            code = (request.POST.get("code") or "").strip()
            department_id = request.POST.get("department_id") or None
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO program (department_id, name, code, created_at)
                            VALUES (%s, %s, %s, now())
                        """, [department_id, name, code])
                resp = redirect("program_manage")
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
            department_id = request.POST.get("department_id") or None
            if not _id or not name:
                error = "Бүх талбар шаардлагатай."
            else:
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("""
                                UPDATE program
                                SET department_id=%s, name=%s, code=%s
                                WHERE id=%s
                            """, [department_id, name, code, _id])
                    resp = redirect("program_manage")
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
                        cursor.execute("DELETE FROM program WHERE id=%s", [_id])
                resp = redirect("program_manage")
                set_cookie_safe(resp, "flash_msg", "Амжилттай устгалаа", 5)
                set_cookie_safe(resp, "flash_status", 200, 5)
                return resp
            except Exception as e:
                error = f"Устгахад алдаа: {e}"

    # READ LIST
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT p.id, p.department_id, p.name, p.code, COALESCE(d.name,'') as dept_name
            FROM program p
            LEFT JOIN department d ON d.id = p.department_id
            ORDER BY p.id DESC
        """)
        rows = cursor.fetchall()

        cursor.execute("SELECT id, name FROM department ORDER BY name")
        departments = cursor.fetchall()

    items = [{"id": r[0], "department_id": r[1], "name": r[2], "code": r[3], "department_name": r[4]} for r in rows]

    return render(request, "admin/look_up/program_manage.html", {
        "items": json.dumps(items),
        "departments": departments,
        "error": error
    })
