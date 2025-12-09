# app_core/views/look_up/room_type.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from app_core.utils import _is_admin, set_cookie_safe
from django.views.decorators.csrf import csrf_protect
import json

@csrf_protect
def room_type_manage(request):
    if not _is_admin(request):
        return redirect("login")

    error = None

    if request.method == "POST":
        action = request.POST.get("action")
        # ADD
        if action == "add":
            code = (request.POST.get("code") or "").strip()
            name = (request.POST.get("name") or "").strip()
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO room_type (code, name)
                            VALUES (%s, %s)
                        """, [code, name])
                resp = redirect("room_type_manage")
                set_cookie_safe(resp, "flash_msg", "Амжилттай нэмэгдлээ", 5)
                set_cookie_safe(resp, "flash_status", 200, 5)
                return resp
            except Exception as e:
                error = f"Нэмэхэд алдаа: {e}"

        # EDIT
        elif action == "edit":
            _id = request.POST.get("id")
            code = (request.POST.get("code") or "").strip()
            name = (request.POST.get("name") or "").strip()
            if not _id or not name:
                error = "Бүх талбар шаардлагатай."
            else:
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("""
                                UPDATE room_type
                                SET code=%s, name=%s
                                WHERE id=%s
                            """, [code, name, _id])
                    resp = redirect("room_type_manage")
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
                        cursor.execute("DELETE FROM room_type WHERE id=%s", [_id])
                resp = redirect("room_type_manage")
                set_cookie_safe(resp, "flash_msg", "Амжилттай устгалаа", 5)
                set_cookie_safe(resp, "flash_status", 200, 5)
                return resp
            except Exception as e:
                error = f"Устгахад алдаа: {e}"

    # READ LIST
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, code, name FROM room_type ORDER BY id DESC")
        rows = cursor.fetchall()

    items = [{"id": r[0], "code": r[1], "name": r[2]} for r in rows]

    return render(request, "admin/look_up/room_type_manage.html", {
        "items": json.dumps(items),
        "error": error
    })
