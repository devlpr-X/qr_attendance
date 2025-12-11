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

def _get_years():
    """Бүх оныг буцаана"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT year 
            FROM class_group 
            WHERE year IS NOT NULL 
            ORDER BY year DESC
        """)
        rows = cursor.fetchall()
    return [r[0] for r in rows]

def _get_departments(school_id=None):
    with connection.cursor() as cursor:
        q = "SELECT id, school_id, name, code FROM department"
        params = []
        if school_id:
            q += " WHERE school_id = %s"
            params.append(school_id)
        q += " ORDER BY school_id, code, name"
        cursor.execute(q, params)
        rows = cursor.fetchall()
    return [
        {"id": r[0], "school_id": r[1], "name": r[2], "code": r[3] or ""}
        for r in rows
    ]

def _get_programs(school_id=None, department_id=None):
    """Хөтөлбөрүүдийг авах"""
    with connection.cursor() as cursor:
        q = """
            SELECT p.id, p.department_id, p.name, p.code, d.school_id
            FROM program p
            JOIN department d ON p.department_id = d.id
        """
        params = []
        where = []
        
        if school_id:
            where.append("d.school_id = %s")
            params.append(school_id)
        if department_id:
            where.append("p.department_id = %s")
            params.append(department_id)
            
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY p.code, p.name"
        
        cursor.execute(q, params)
        rows = cursor.fetchall()
    return [
        {
            "id": r[0],
            "department_id": r[1],
            "name": r[2],
            "code": r[3] or "",
            "school_id": r[4]
        }
        for r in rows
    ]

def _get_class_groups(school_id=None, year=None, department_id=None, program_id=None):
    with connection.cursor() as cursor:
        q = """
            SELECT
                cg.id, cg.name, cg.year, cg.school_id,
                p.id AS program_id, p.name AS program_name, p.code AS program_code,
                d.id AS department_id, d.name AS department_name
            FROM class_group cg
            JOIN program p ON cg.program_id = p.id
            JOIN department d ON p.department_id = d.id
        """
        params = []
        where = []
        
        if school_id:
            where.append("cg.school_id = %s")
            params.append(school_id)
        if year:
            where.append("cg.year = %s")
            params.append(year)
        if department_id:
            where.append("d.id = %s")
            params.append(department_id)
        if program_id:
            where.append("p.id = %s")
            params.append(program_id)
            
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY cg.year DESC, p.code, cg.name"
        
        cursor.execute(q, params)
        rows = cursor.fetchall()
    return [
        {
            "id": r[0],
            "name": r[1] or "",
            "year": r[2],
            "school_id": r[3],
            "program_id": r[4],
            "program_name": r[5] or "",
            "program_code": r[6] or "",
            "department_id": r[7],
            "department_name": r[8] or ""
        }
        for r in rows
    ]

def _get_students(school_id=None):
    """Оюутнуудыг авах"""
    with connection.cursor() as cursor:
        q = """
            SELECT DISTINCT
                s.id,
                s.student_code,
                s.full_name
            FROM student s
        """
        params = []
        if school_id:
            q += """
                LEFT JOIN student_class_group scg ON s.id = scg.student_id
                LEFT JOIN class_group cg ON scg.class_group_id = cg.id
                WHERE cg.school_id = %s OR cg.school_id IS NULL
            """
            params.append(school_id)
        q += " ORDER BY s.full_name"
        
        cursor.execute(q, params)
        rows = cursor.fetchall()
    
    return [
        {
            "id": r[0],
            "student_code": r[1] or "",
            "full_name": r[2] or ""
        }
        for r in rows
    ]

def _get_students_in_class_group(class_group_id):
    """Тодорхой бүлэгт элссэн оюутнуудын ID"""
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

def _get_student_year_enrollments(year):
    """
    Тухайн оны бүх оюутнуудын элсэлтийг авах
    Returns: {student_id: {"class_group_id": X, "class_group_name": "Y"}}
    """
    if not year:
        return {}
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                scg.student_id,
                cg.id as class_group_id,
                cg.name as class_group_name
            FROM student_class_group scg
            JOIN class_group cg ON scg.class_group_id = cg.id
            WHERE cg.year = %s
        """, [year])
        rows = cursor.fetchall()
    
    result = {}
    for r in rows:
        result[r[0]] = {
            "class_group_id": r[1],
            "class_group_name": r[2]
        }
    return result

def _get_assignments(filter_school=None, filter_year=None, filter_department=None, 
                     filter_program=None, filter_class_group=None, search=None):
    """Бүлэгт элссэн оюутнуудын жагсаалт"""
    with connection.cursor() as cursor:
        q = """
            SELECT
                scg.id,
                s.id as student_id,
                s.student_code,
                s.full_name as student_name,
                cg.id as class_group_id,
                cg.name as class_group_name,
                cg.year,
                cg.school_id,
                l.name as school_name,
                d.id as department_id,
                d.name as department_name,
                p.id as program_id,
                p.name as program_name,
                scg.created_at
            FROM student_class_group scg
            JOIN student s ON scg.student_id = s.id
            JOIN class_group cg ON scg.class_group_id = cg.id
            JOIN program p ON cg.program_id = p.id
            JOIN department d ON p.department_id = d.id
            LEFT JOIN location l ON cg.school_id = l.id
        """
        params = []
        where = []
        
        if filter_school:
            where.append("cg.school_id = %s")
            params.append(filter_school)
        if filter_year:
            where.append("cg.year = %s")
            params.append(filter_year)
        if filter_department:
            where.append("d.id = %s")
            params.append(filter_department)
        if filter_program:
            where.append("p.id = %s")
            params.append(filter_program)
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
        created = r[13]
        created_str = created.strftime("%Y-%m-%d %H:%M:%S") if created else ""
        items.append({
            "id": r[0],
            "student_id": r[1],
            "student_code": r[2] or "",
            "student_name": r[3] or "",
            "class_group_id": r[4],
            "class_group_name": r[5] or "",
            "year": r[6],
            "school_id": r[7],
            "school_name": r[8] or "",
            "department_id": r[9],
            "department_name": r[10] or "",
            "program_id": r[11],
            "program_name": r[12] or "",
            "created_at": created_str
        })
    return items

@csrf_protect
def student_class_group_manage(request):
    if not _is_admin(request):
        return redirect("login")
    
    error = None
    
    # POST ҮЙЛДЛҮҮД
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "assign":
            # Оюутнуудыг бүлэгт элсүүлэх
            class_group_id = request.POST.get("class_group_id")
            student_ids = request.POST.getlist("student_ids")
            
            if not class_group_id or not student_ids:
                error = "Анги болон оюутнууд заавал заагдсан байх ёстой."
            else:
                try:
                    # Сонгосон бүлгийн он-г олох
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT year FROM class_group WHERE id = %s", [class_group_id])
                        row = cursor.fetchone()
                        if not row:
                            error = "Анги олдсонгүй"
                        else:
                            selected_year = row[0]
                            
                            # Тухайн оны бүх элсэлтийг шалгах
                            year_enrollments = _get_student_year_enrollments(selected_year)
                            
                            with transaction.atomic():
                                added_count = 0
                                skipped_students = []
                                
                                for sid in student_ids:
                                    sid_int = int(sid)
                                    
                                    # Тухайн онд аль хэдийн элссэн эсэхийг шалгах
                                    if sid_int in year_enrollments:
                                        existing_group = year_enrollments[sid_int]["class_group_name"]
                                        skipped_students.append(f"{sid} ({existing_group})")
                                        continue
                                    
                                    # Тухайн бүлэгт аль хэдийн элссэн эсэхийг шалгах
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
                                    added_count += 1
                                
                            resp = redirect("student_class_group_manage")
                            
                            if skipped_students:
                                msg = f"{added_count} оюутан элсүүллээ. {len(skipped_students)} оюутан {selected_year} онд өөр бүлэгт элссэн байна: {', '.join(skipped_students[:5])}"
                                if len(skipped_students) > 5:
                                    msg += f" болон бусад {len(skipped_students) - 5}..."
                            else:
                                msg = f"{added_count} оютан амжилттай элсүүллээ"
                                
                            set_cookie_safe(resp, "flash_msg", msg, 5)
                            set_cookie_safe(resp, "flash_status", 200, 5)
                            return resp
                except Exception as e:
                    error = f"Элсүүлэхэд алдаа: {e}"
                    
        elif action == "remove":
            # Нэг оюутныг бүлгээс гаргах
            assignment_id = request.POST.get("id")
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM student_class_group WHERE id = %s", [assignment_id])
                        
                resp = redirect("student_class_group_manage")
                set_cookie_safe(resp, "flash_msg", "Оюутныг бүлгээс гаргалаа", 5)
                set_cookie_safe(resp, "flash_status", 200, 5)
                return resp
            except Exception as e:
                error = f"Гаргахад алдаа: {e}"
                
        elif action == "remove_filtered":
            # Шүүгдсэн бүх оюутнуудыг бүлгээс гаргах
            filter_school = request.POST.get("filter_school") or None
            filter_year = request.POST.get("filter_year") or None
            filter_department = request.POST.get("filter_department") or None
            filter_program = request.POST.get("filter_program") or None
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
                        if filter_year:
                            where.append("cg.year = %s")
                            params.append(filter_year)
                        if filter_department:
                            where.append("d.id = %s")
                            params.append(filter_department)
                        if filter_program:
                            where.append("p.id = %s")
                            params.append(filter_program)
                        if filter_class_group:
                            where.append("cg.id = %s")
                            params.append(filter_class_group)
                            
                        if where:
                            q += " AND " + " AND ".join(where)
                            
                        cursor.execute(q, params)
                        count = cursor.rowcount
                        
                resp = redirect("student_class_group_manage")
                set_cookie_safe(resp, "flash_msg", f"{count} оюутныг бүлгээс гаргалаа", 5)
                set_cookie_safe(resp, "flash_status", 200, 5)
                return resp
            except Exception as e:
                error = f"Гаргахад алдаа: {e}"
    
    # GET - датаг унших
    schools = _get_schools()
    years = _get_years()
    departments = _get_departments()
    programs = _get_programs()
    class_groups = _get_class_groups()
    students = _get_students()
    
    # Шүүлтүүр
    filter_school = request.GET.get("school_id") or None
    filter_year = request.GET.get("year") or None
    filter_department = request.GET.get("department_id") or None
    filter_program = request.GET.get("program_id") or None
    filter_class_group = request.GET.get("class_group_id") or None
    search = request.GET.get("search") or None
    per_page = int(request.GET.get("per_page") or 20)
    page_num = int(request.GET.get("page") or 1)
    
    # Бүлэгт элссэн оюутнууд
    assignments_all = _get_assignments(
        filter_school=filter_school,
        filter_year=filter_year,
        filter_department=filter_department,
        filter_program=filter_program,
        filter_class_group=filter_class_group,
        search=search
    )
    
    # Pagination
    paginator = Paginator(assignments_all, per_page)
    page_obj = paginator.get_page(page_num)
    page_items = list(page_obj.object_list)
    
    # Элсүүлэх хэсэгт сонгогдсон бүлэгт аль хэдийн элссэн оюутнууд
    selected_class_group_for_assign = request.GET.get("assign_class_group_id") or None
    assigned_student_ids = _get_students_in_class_group(selected_class_group_for_assign) if selected_class_group_for_assign else []
    
    # Элсүүлэх хэсэгт сонгогдсон оны бүх элсэлтүүд
    selected_year_for_assign = request.GET.get("assign_year") or None
    year_enrollments = _get_student_year_enrollments(selected_year_for_assign) if selected_year_for_assign else {}
    
    return render(request, "admin/look_up/student_class_group_manage.html", {
        "error": error,
        "schools": schools,
        "years": years,
        "departments": departments,
        "programs": programs,
        "class_groups": class_groups,
        "students": students,
        "assignments": page_items,
        "paginator": paginator,
        "page_obj": page_obj,
        "filter_school": filter_school,
        "filter_year": filter_year,
        "filter_department": filter_department,
        "filter_program": filter_program,
        "filter_class_group": filter_class_group,
        "search": search or "",
        "per_page": per_page,
        "assigned_student_ids": assigned_student_ids,
        "year_enrollments": year_enrollments,
        # JSON форматаар
        "schools_json": json.dumps(schools, ensure_ascii=False),
        "years_json": json.dumps(years, ensure_ascii=False),
        "departments_json": json.dumps(departments, ensure_ascii=False),
        "programs_json": json.dumps(programs, ensure_ascii=False),
        "class_groups_json": json.dumps(class_groups, ensure_ascii=False),
        "students_json": json.dumps(students, ensure_ascii=False),
        "assigned_student_ids_json": json.dumps(assigned_student_ids, ensure_ascii=False),
        "year_enrollments_json": json.dumps(year_enrollments, ensure_ascii=False),
    })