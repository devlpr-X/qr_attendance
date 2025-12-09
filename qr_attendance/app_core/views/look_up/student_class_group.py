# app_core/views/look_up/student_class_group.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.views.decorators.csrf import csrf_protect
from django.core.paginator import Paginator
from django.utils import timezone

from app_core.utils import _is_admin, set_cookie_safe

import json


def _get_schools():
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM location ORDER BY name")
        rows = cursor.fetchall()
    return [{"id": r[0], "name": r[1]} for r in rows]


def _get_semesters():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, school_id, school_year, term, name, is_active
            FROM semester
            ORDER BY school_id, school_year DESC, term DESC
        """)
        rows = cursor.fetchall()
    return [
        {"id": r[0], "school_id": r[1], "school_year": r[2], "term": r[3], "name": r[4], "is_active": r[5]}
        for r in rows
    ]


def _get_departments():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, school_id, name, code
            FROM department
            ORDER BY school_id, code, name
        """)
        rows = cursor.fetchall()
    return [
        {"id": r[0], "school_id": r[1], "name": r[2], "code": r[3] or ""}
        for r in rows
    ]


def _get_class_groups():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                cg.id, cg.name, cg.school_id, cg.semester_id,
                p.name AS program_name, p.code AS program_code,
                d.id AS department_id, d.name AS department_name,
                s.name AS semester_name
            FROM class_group cg
            JOIN program p ON cg.program_id = p.id
            JOIN department d ON p.department_id = d.id
            LEFT JOIN semester s ON cg.semester_id = s.id
            ORDER BY cg.school_id, p.code, cg.name
        """)
        rows = cursor.fetchall()
    return [
        {
            "id": r[0], 
            "name": r[1] or "", 
            "school_id": r[2], 
            "semester_id": r[3],
            "program_name": r[4] or "", 
            "program_code": r[5] or "",
            "department_id": r[6],
            "department_name": r[7] or "",
            "semester_name": r[8] or ""
        }
        for r in rows
    ]


def _get_students():
    """
    Get all students with their school associations
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT
                s.id, 
                s.student_code, 
                s.full_name,
                cg.school_id
            FROM student s
            LEFT JOIN student_class_group scg ON s.id = scg.student_id
            LEFT JOIN class_group cg ON scg.class_group_id = cg.id
            ORDER BY s.full_name
        """)
        rows = cursor.fetchall()
    
    # Group by student to get unique students with their schools
    students_dict = {}
    for r in rows:
        sid = r[0]
        if sid not in students_dict:
            students_dict[sid] = {
                "id": sid,
                "student_code": r[1] or "",
                "full_name": r[2] or "",
                "school_ids": []
            }
        if r[3]:  # school_id exists
            if r[3] not in students_dict[sid]["school_ids"]:
                students_dict[sid]["school_ids"].append(r[3])
    
    return list(students_dict.values())


def _get_students_in_class_group(class_group_id):
    """
    Get list of student IDs already assigned to a specific class group
    """
    if not class_group_id:
        return []
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT student_id
            FROM student_class_group
            WHERE class_group_id = %s
        """, [class_group_id])
        rows = cursor.fetchall()
    
    return [r[0] for r in rows]


def _get_assignments(filter_school=None, filter_semester=None, filter_department=None, filter_class_group=None, search=None):
    with connection.cursor() as cursor:
        q = """
            SELECT 
                scg.id, 
                s.id as student_id, 
                s.student_code, 
                s.full_name as student_name,
                cg.id as class_group_id, 
                cg.name as class_group_name,
                cg.school_id,
                l.name as school_name,
                sem.id as semester_id,
                sem.name as semester_name,
                d.id as department_id,
                d.name as department_name,
                scg.created_at
            FROM student_class_group scg
            JOIN student s ON scg.student_id = s.id
            JOIN class_group cg ON scg.class_group_id = cg.id
            JOIN location l ON cg.school_id = l.id
            LEFT JOIN semester sem ON cg.semester_id = sem.id
            JOIN program p ON cg.program_id = p.id
            JOIN department d ON p.department_id = d.id
        """
        params = []
        where = []
        
        if filter_school:
            where.append("cg.school_id = %s")
            params.append(filter_school)
        if filter_semester:
            where.append("cg.semester_id = %s")
            params.append(filter_semester)
        if filter_department:
            where.append("d.id = %s")
            params.append(filter_department)
        if filter_class_group:
            where.append("cg.id = %s")
            params.append(filter_class_group)
        if search:
            where.append("(s.student_code ILIKE %s OR s.full_name ILIKE %s OR cg.name ILIKE %s)")
            squery = f"%{search}%"
            params.extend([squery, squery, squery])
            
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY scg.created_at DESC"
        
        cursor.execute(q, params)
        rows = cursor.fetchall()

    items = []
    for r in rows:
        created = r[12]
        created_str = created.strftime("%Y-%m-%d %H:%M:%S") if created else ""
        items.append({
            "id": r[0],
            "student_id": r[1],
            "student_code": r[2] or "",
            "student_name": r[3] or "",
            "class_group_id": r[4],
            "class_group_name": r[5] or "",
            "school_id": r[6],
            "school_name": r[7] or "",
            "semester_id": r[8],
            "semester_name": r[9] or "",
            "department_id": r[10],
            "department_name": r[11] or "",
            "created_at": created_str
        })
    return items


@csrf_protect
def student_class_group_manage(request):
    if not _is_admin(request):
        return redirect("login")

    error = None

    # POST actions
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "assign":
            class_group_id = request.POST.get("class_group_id")
            student_ids = request.POST.getlist("student_ids")
            if not class_group_id or not student_ids:
                error = "Анги болон оюутнууд заавал заагдсан байх ёстой."
            else:
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            for sid in student_ids:
                                cursor.execute("""
                                    SELECT 1 FROM student_class_group
                                    WHERE student_id = %s AND class_group_id = %s
                                """, [sid, class_group_id])
                                if cursor.fetchone():
                                    continue
                                cursor.execute("""
                                    INSERT INTO student_class_group (student_id, class_group_id, created_at)
                                    VALUES (%s, %s, %s)
                                """, [sid, class_group_id, timezone.now()])
                    resp = redirect("student_class_group_manage")
                    set_cookie_safe(resp, "flash_msg", f"{len(student_ids)} оюутан амжилттай холбогдлоо", 5)
                    set_cookie_safe(resp, "flash_status", 200, 5)
                    return resp
                except Exception as e:
                    error = f"Оруулахад алдаа: {e}"

        elif action == "delete":
            _id = request.POST.get("id")
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM student_class_group WHERE id = %s", [_id])
                resp = redirect("student_class_group_manage")
                set_cookie_safe(resp, "flash_msg", "Холболт устгагдлаа", 5)
                set_cookie_safe(resp, "flash_status", 200, 5)
                return resp
            except Exception as e:
                error = f"Устгахад алдаа: {e}"
                
        elif action == "delete_filtered":
            # Шүүгдсэн бүх холболтыг устгах
            filter_school = request.POST.get("filter_school") or None
            filter_semester = request.POST.get("filter_semester") or None
            filter_department = request.POST.get("filter_department") or None
            filter_class_group = request.POST.get("filter_class_group") or None
            
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        q = """
                            DELETE FROM student_class_group scg
                            USING class_group cg, program p, department d
                            WHERE scg.class_group_id = cg.id
                            AND cg.program_id = p.id
                            AND p.department_id = d.id
                        """
                        params = []
                        where = []
                        
                        if filter_school:
                            where.append("cg.school_id = %s")
                            params.append(filter_school)
                        if filter_semester:
                            where.append("cg.semester_id = %s")
                            params.append(filter_semester)
                        if filter_department:
                            where.append("d.id = %s")
                            params.append(filter_department)
                        if filter_class_group:
                            where.append("cg.id = %s")
                            params.append(filter_class_group)
                            
                        if where:
                            q += " AND " + " AND ".join(where)
                            
                        cursor.execute(q, params)
                        count = cursor.rowcount
                        
                resp = redirect("student_class_group_manage")
                set_cookie_safe(resp, "flash_msg", f"{count} холболт устгагдлаа", 5)
                set_cookie_safe(resp, "flash_status", 200, 5)
                return resp
            except Exception as e:
                error = f"Устгахад алдаа: {e}"

    # GET - list data
    schools = _get_schools()
    semesters = _get_semesters()
    departments = _get_departments()
    class_groups = _get_class_groups()
    students = _get_students()
    
    # Get currently assigned students for the selected class group (if any)
    selected_class_group_for_assign = request.GET.get("assign_class_group_id") or None
    assigned_student_ids = _get_students_in_class_group(selected_class_group_for_assign) if selected_class_group_for_assign else []

    # Filters & pagination
    filter_school = request.GET.get("school_id") or None
    filter_semester = request.GET.get("semester_id") or None
    filter_department = request.GET.get("department_id") or None
    filter_class_group = request.GET.get("class_group_id") or None
    search = request.GET.get("search") or None
    per_page = int(request.GET.get("per_page") or 20)
    page_num = int(request.GET.get("page") or 1)

    assignments_all = _get_assignments(
        filter_school=filter_school,
        filter_semester=filter_semester,
        filter_department=filter_department,
        filter_class_group=filter_class_group,
        search=search
    )
    
    paginator = Paginator(assignments_all, per_page)
    page_obj = paginator.get_page(page_num)
    page_items = list(page_obj.object_list)

    return render(request, "admin/look_up/student_class_group_manage.html", {
        "error": error,
        "schools": schools,
        "semesters": semesters,
        "departments": departments,
        "class_groups": class_groups,
        "students": students,
        "assignments": page_items,
        "paginator": paginator,
        "page_obj": page_obj,
        "filter_school": filter_school,
        "filter_semester": filter_semester,
        "filter_department": filter_department,
        "filter_class_group": filter_class_group,
        "search": search or "",
        "per_page": per_page,
        "assigned_student_ids": assigned_student_ids,
        "schools_json": json.dumps(schools, ensure_ascii=False),
        "semesters_json": json.dumps(semesters, ensure_ascii=False),
        "departments_json": json.dumps(departments, ensure_ascii=False),
        "class_groups_json": json.dumps(class_groups, ensure_ascii=False),
        "students_json": json.dumps(students, ensure_ascii=False),
        "assignments_json": json.dumps(assignments_all, ensure_ascii=False),
        "assigned_student_ids_json": json.dumps(assigned_student_ids, ensure_ascii=False),
    })