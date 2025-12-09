# app_core/views/look_up/class_room.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from app_core.utils import _is_admin, set_cookie_safe
from django.views.decorators.csrf import csrf_protect
import json

@csrf_protect
def class_room_manage(request):
    if not _is_admin(request):
        return redirect("login")

    error = None

    if request.method == "POST":
        action = request.POST.get("action")
        # ADD
        if action == "add":
            room_number = (request.POST.get("room_number") or "").strip()
            room_type_id = request.POST.get("room_type_id") or None
            capacity = request.POST.get("capacity") or None
            school_id = request.POST.get("school_id") or None
            try:
                capacity_i = int(capacity) if capacity else None
            except:
                capacity_i = None
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO class_room (school_id, room_number, room_type_id, capacity, created_at)
                            VALUES (%s, %s, %s, %s, now())
                        """, [school_id, room_number, room_type_id, capacity_i])
                resp = redirect("class_room_manage")
                set_cookie_safe(resp, "flash_msg", "Амжилттай нэмэгдлээ", 5)
                set_cookie_safe(resp, "flash_status", 200, 5)
                return resp
            except Exception as e:
                error = f"Нэмэхэд алдаа: {e}"

        # EDIT
        elif action == "edit":
            _id = request.POST.get("id")
            room_number = (request.POST.get("room_number") or "").strip()
            room_type_id = request.POST.get("room_type_id") or None
            capacity = request.POST.get("capacity") or None
            school_id = request.POST.get("school_id") or None
            try:
                capacity_i = int(capacity) if capacity else None
            except:
                capacity_i = None
            if not _id or not room_number:
                error = "Бүх талбар шаардлагатай."
            else:
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("""
                                UPDATE class_room
                                SET school_id=%s, room_number=%s, room_type_id=%s, capacity=%s
                                WHERE id=%s
                            """, [school_id, room_number, room_type_id, capacity_i, _id])
                    resp = redirect("class_room_manage")
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
                        cursor.execute("DELETE FROM class_room WHERE id=%s", [_id])
                resp = redirect("class_room_manage")
                set_cookie_safe(resp, "flash_msg", "Амжилттай устгалаа", 5)
                set_cookie_safe(resp, "flash_status", 200, 5)
                return resp
            except Exception as e:
                error = f"Устгахад алдаа: {e}"

    # READ LIST
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT cr.id, cr.school_id, cr.room_number, cr.room_type_id, cr.capacity,
                   COALESCE(rt.name,'') as room_type_name, COALESCE(l.name,'') as school_name
            FROM class_room cr
            LEFT JOIN room_type rt ON rt.id = cr.room_type_id
            LEFT JOIN location l ON l.id = cr.school_id
            ORDER BY cr.school_id, cr.room_number, rt.id, cr.capacity
        """)
        rows = cursor.fetchall()

        cursor.execute("SELECT id, name FROM location ORDER BY name")
        schools = cursor.fetchall()

        cursor.execute("SELECT id, name FROM room_type ORDER BY name")
        room_types = cursor.fetchall()

    items = [{
        "id": r[0],
        "school_id": r[1],
        "room_number": r[2],
        "room_type_id": r[3],
        "capacity": r[4],
        "room_type_name": r[5],
        "school_name": r[6]
    } for r in rows]

    return render(request, "admin/look_up/class_room_manage.html", {
        "items": json.dumps(items),
        "schools": schools,
        "room_types": room_types,
        "error": error
    })
