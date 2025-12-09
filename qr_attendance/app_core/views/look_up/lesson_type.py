# app_core/views/look_up/lesson_type.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from app_core.utils import _is_admin, set_cookie_safe
from django.views.decorators.csrf import csrf_protect
import json


@csrf_protect
def lesson_type_manage(request):
    if not _is_admin(request):
        return redirect("login")

    error = None

    if request.method == "POST":
        action = request.POST.get("action")

        # ADD
        if action == "add":
            name = request.POST.get("name", "").strip()
            value = request.POST.get("value", "").strip()

            if not name or not value:
                error = "Нэр болон утга хэрэгтэй."
            else:
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("""
                                INSERT INTO lesson_type (name, value)
                                VALUES (%s, %s)
                            """, [name, value])

                    resp = redirect("lesson_type_manage")
                    set_cookie_safe(resp, "flash_msg", "Амжилттай нэмэгдлээ", 5)
                    set_cookie_safe(resp, "flash_status", 200, 5)
                    return resp

                except Exception:
                    error = "Давхцсан утга байна."

        # EDIT
        elif action == "edit":
            _id = request.POST.get("id")
            name = request.POST.get("name", "").strip()
            value = request.POST.get("value", "").strip()

            if not _id or not name or not value:
                error = "Бүх талбар шаардлагатай."
            else:
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("""
                                UPDATE lesson_type
                                SET name=%s, value=%s
                                WHERE id=%s
                            """, [name, value, _id])

                    resp = redirect("lesson_type_manage")
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
                        cursor.execute("DELETE FROM lesson_type WHERE id=%s", [_id])

                resp = redirect("lesson_type_manage")
                set_cookie_safe(resp, "flash_msg", "Амжилттай устгалаа", 5)
                set_cookie_safe(resp, "flash_status", 200, 5)
                return resp

            except:
                error = "Устгаж чадсангүй."

    # READ LIST
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, name, value
            FROM lesson_type
            ORDER BY id
        """)
        rows = cursor.fetchall()

    items = [{"id": r[0], "name": r[1], "value": r[2]} for r in rows]

    return render(request, "admin/look_up/lesson_type_manage.html", {
        "items": json.dumps(items),
        "error": error
    })

def _get_lesson_types():
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, value FROM lesson_type ORDER BY id ASC")
        rows = cursor.fetchall()

    return [{"id": r[0], "name": r[1], "value": r[2]} for r in rows]