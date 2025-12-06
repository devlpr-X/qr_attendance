from django.shortcuts import render, redirect
from django.db import connection
from app_core.utils import _is_admin
from django.views.decorators.csrf import csrf_protect
import json

@csrf_protect
def attendance_type_manage(request):
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
                error = "Нэр болон утга шаардлагатай."
            else:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO attendance_type (name, value)
                            VALUES (%s, %s)
                        """, [name, value])
                except Exception as e:
                    error = "Утга давхцаж байна."

        # EDIT
        elif action == "edit":
            _id = request.POST.get("id")
            name = request.POST.get("name")
            value = request.POST.get("value")

            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE attendance_type
                    SET name=%s, value=%s, updated_at=now()
                    WHERE id=%s
                """, [name, value, _id])

        # DELETE
        elif action == "delete":
            _id = request.POST.get("id")
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM attendance_type WHERE id=%s", [_id])

    # READ
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, name, value
            FROM attendance_type
            ORDER BY id
        """)
        rows = cursor.fetchall()

    items = [{"id": r[0], "name": r[1], "value": r[2]} for r in rows]

    return render(request, "admin/attendance_type/manage.html", {
        "items": json.dumps(items),
        "error": error
    })