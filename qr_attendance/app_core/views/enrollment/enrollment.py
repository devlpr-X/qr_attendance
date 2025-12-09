# app_core/views/students.py (or enrollments.py)
from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect

from django.http import JsonResponse
import json


def _get_schools():
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM location ORDER BY name")
        rows = cursor.fetchall()
    return [{"id": r[0], "name": r[1]} for r in rows]


def _get_semesters():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, school_id, school_year, term, name
            FROM semester
            ORDER BY school_id, school_year DESC, term DESC
        """)
        rows = cursor.fetchall()
    return [
        {"id": r[0], "school_id": r[1], "school_year": r[2], "term": r[3], "name": r[4]}
        for r in rows
    ]


def _get_departments():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, school_id, name, code
            FROM department
            ORDER BY school_id, code
        """)
        rows = cursor.fetchall()
    return [{"id": r[0], "school_id": r[1], "name": r[2], "code": r[3] or ""} for r in rows]


def _get_class_groups():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                cg.id, cg.name, cg.school_id, cg.semester_id,
                p.name AS program_name, p.code AS program_code,
                d.id AS department_id
            FROM class_group cg
            JOIN program p ON cg.program_id = p.id
            JOIN department d ON p.department_id = d.id
            ORDER BY cg.school_id, p.code, cg.name
        """)
        rows = cursor.fetchall()
    return [
        {
            "id": r[0], "name": r[1], "school_id": r[2], "semester_id": r[3],
            "program_name": r[4], "program_code": r[5] or "", "department_id": r[6]
        }
        for r in rows
    ]


def _get_courses():
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, code FROM course ORDER BY code")
        rows = cursor.fetchall()
    return [{"id": r[0], "name": r[1], "code": r[2] or ""} for r in rows]


def _get_students():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT s.id, s.student_code, s.full_name
            FROM student s
            ORDER BY s.full_name
        """)
        rows = cursor.fetchall()
    return [{"id": r[0], "student_code": r[1] or "", "full_name": r[2] or ""} for r in rows]


def _get_students_in_class_group(class_group_id):
    """Get student IDs in a class group"""
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


def _get_students_in_enrollment(course_id, class_group_id):
    """Get student IDs already enrolled in a course for a class group"""
    if not course_id or not class_group_id:
        return []
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT student_id
            FROM enrollment
            WHERE course_id = %s AND class_group_id = %s
        """, [course_id, class_group_id])
        rows = cursor.fetchall()
    return [r[0] for r in rows]


@csrf_protect
def enrollments_list(request):
    # POST: Handle enrollment actions
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'enroll_group':
            # Бүлгээр элсүүлэх
            course_id = request.POST.get('course_id')
            class_group_id = request.POST.get('class_group_id')
            
            if not course_id or not class_group_id:
                messages.error(request, "Хичээл болон анги бүлэг сонгоно уу.")
            else:
                try:
                    # Get all students in the class group
                    student_ids = _get_students_in_class_group(class_group_id)
                    
                    if not student_ids:
                        messages.warning(request, "Тухайн ангид оюутан байхгүй байна.")
                    else:
                        inserted = 0
                        skipped = 0
                        
                        with transaction.atomic():
                            with connection.cursor() as cursor:
                                for sid in student_ids:
                                    # Check if already enrolled
                                    cursor.execute("""
                                        SELECT 1 FROM enrollment
                                        WHERE student_id=%s AND course_id=%s AND class_group_id=%s
                                    """, [sid, course_id, class_group_id])
                                    
                                    if cursor.fetchone():
                                        skipped += 1
                                    else:
                                        cursor.execute("""
                                            INSERT INTO enrollment (student_id, course_id, class_group_id)
                                            VALUES (%s, %s, %s)
                                        """, [sid, course_id, class_group_id])
                                        inserted += 1
                        
                        msg = f"Амжилттай: {inserted} оюутан элслээ."
                        if skipped:
                            msg += f" (Давхардсан: {skipped})"
                        messages.success(request, msg)
                        
                except Exception as e:
                    messages.error(request, f"Алдаа гарлаа: {e}")
        
        elif action == 'enroll_additional':
            # Нэмэлт оюутан нэмэх
            course_id = request.POST.get('course_id')
            class_group_id = request.POST.get('class_group_id')
            student_ids = request.POST.getlist('student_ids')
            
            if not course_id or not class_group_id or not student_ids:
                messages.error(request, "Хичээл, анги бүлэг болон оюутан сонгоно уу.")
            else:
                try:
                    inserted = 0
                    skipped = 0
                    
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            for sid in student_ids:
                                cursor.execute("""
                                    SELECT 1 FROM enrollment
                                    WHERE student_id=%s AND course_id=%s AND class_group_id=%s
                                """, [sid, course_id, class_group_id])
                                
                                if cursor.fetchone():
                                    skipped += 1
                                else:
                                    cursor.execute("""
                                        INSERT INTO enrollment (student_id, course_id, class_group_id)
                                        VALUES (%s, %s, %s)
                                    """, [sid, course_id, class_group_id])
                                    inserted += 1
                    
                    msg = f"Нэмэлт {inserted} оюутан элслээ."
                    if skipped:
                        msg += f" (Давхардсан: {skipped})"
                    messages.success(request, msg)
                    
                except Exception as e:
                    messages.error(request, f"Алдаа гарлаа: {e}")
        
        params = request.GET.copy()
        params['scroll'] = '1'
        return redirect(f"{request.path}?{params.urlencode()}")
    
    # GET: Load data and filters
    schools = _get_schools()
    semesters = _get_semesters()
    departments = _get_departments()
    class_groups = _get_class_groups()
    courses = _get_courses()
    students = _get_students()
    
    # Filters
    search = request.GET.get('search', '').strip()
    filter_course = request.GET.get('course_id') or None
    filter_school = request.GET.get('school_id') or None
    filter_semester = request.GET.get('semester_id') or None
    filter_department = request.GET.get('department_id') or None
    filter_class_group = request.GET.get('class_group_id') or None
    
    per_page = int(request.GET.get('per_page', '30'))
    if per_page <= 0:
        per_page = 30
    
    # Build query
    sql = """
        SELECT 
            e.id,
            s.student_code,
            s.full_name,
            c.code AS course_code,
            c.name AS course_name,
            cg.name AS class_group_name,
            l.name AS school_name,
            sem.name AS semester_name,
            d.name AS department_name
        FROM enrollment e
        JOIN student s ON s.id = e.student_id
        JOIN course c ON c.id = e.course_id
        LEFT JOIN class_group cg ON cg.id = e.class_group_id
        LEFT JOIN location l ON cg.school_id = l.id
        LEFT JOIN semester sem ON cg.semester_id = sem.id
        LEFT JOIN program p ON cg.program_id = p.id
        LEFT JOIN department d ON p.department_id = d.id
        WHERE 1=1
    """
    params = []
    
    if search:
        sql += """ AND (
            s.student_code ILIKE %s OR 
            s.full_name ILIKE %s OR
            c.code ILIKE %s OR
            c.name ILIKE %s OR
            cg.name ILIKE %s
        )"""
        like = f"%{search}%"
        params.extend([like, like, like, like, like])
    
    if filter_course:
        sql += " AND e.course_id = %s"
        params.append(filter_course)
    
    if filter_school:
        sql += " AND cg.school_id = %s"
        params.append(filter_school)
    
    if filter_semester:
        sql += " AND cg.semester_id = %s"
        params.append(filter_semester)
    
    if filter_department:
        sql += " AND d.id = %s"
        params.append(filter_department)
    
    if filter_class_group:
        sql += " AND e.class_group_id = %s"
        params.append(filter_class_group)
    
    sql += " ORDER BY c.code ASC, cg.name ASC, s.student_code ASC"
    
    # Execute query
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
    
    enrolls_raw = [{
        'id': r[0],
        'student_code': r[1],
        'student_name': r[2],
        'course_code': r[3],
        'course_name': r[4],
        'class_group_name': r[5] or '-',
        'school_name': r[6] or '-',
        'semester_name': r[7] or '-',
        'department_name': r[8] or '-'
    } for r in rows]
    
    # Pagination
    paginator = Paginator(enrolls_raw, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    for i, e in enumerate(page_obj):
        e['number'] = (page_obj.number - 1) * per_page + i + 1
    
    return render(request, 'admin/enrollments/list.html', {
        'enrolls': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        
        'schools': schools,
        'semesters': semesters,
        'departments': departments,
        'class_groups': class_groups,
        'courses': courses,
        'students': students,
        
        'search': search,
        'filter_course': filter_course,
        'filter_school': filter_school,
        'filter_semester': filter_semester,
        'filter_department': filter_department,
        'filter_class_group': filter_class_group,
        'per_page': per_page,
        
        'schools_json': json.dumps(schools, ensure_ascii=False),
        'semesters_json': json.dumps(semesters, ensure_ascii=False),
        'departments_json': json.dumps(departments, ensure_ascii=False),
        'class_groups_json': json.dumps(class_groups, ensure_ascii=False),
        'courses_json': json.dumps(courses, ensure_ascii=False),
        'students_json': json.dumps(students, ensure_ascii=False),
    })


def enrollment_delete(request, enrollment_id):
    """Delete an enrollment"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM enrollment WHERE id = %s", [enrollment_id])
        messages.success(request, "Элсэлт устгагдлаа")
    except Exception as e:
        messages.error(request, f"Алдаа: {e}")
    
    return redirect('enrollments_list')


def get_enrolled_students_api(request):
    """
    API endpoint to get students already enrolled in a course for a class group
    """
    
    course_id = request.GET.get('course_id')
    class_group_id = request.GET.get('class_group_id')
    
    if not course_id or not class_group_id:
        return JsonResponse({"student_ids": []})
    
    student_ids = _get_students_in_enrollment(course_id, class_group_id)
    return JsonResponse({"student_ids": student_ids})

def get_assigned_students_api(request):
    """
    API endpoint to get students assigned to a class_group.
    Returns JSON: { "student_ids": [1,2,3] }
    """
    class_group_id = request.GET.get('class_group_id')
    if not class_group_id:
        return JsonResponse({"student_ids": []})
    ids = _get_students_in_class_group(class_group_id)
    return JsonResponse({"student_ids": ids})
