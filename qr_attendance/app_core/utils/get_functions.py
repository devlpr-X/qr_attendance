# app_core/views/students.py (or enrollments.py)
from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect

from django.http import JsonResponse
import json


def _get_semesters2(semester_id):    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, school_year, term, start_date, end_date, name, school_id
            FROM semester
            WHERE id = %s
        """, [semester_id]) 
        sem = cursor.fetchone()
    semester = {
        'id': sem[0],
        'school_year': sem[1],
        'term': sem[2],
        'start_date': sem[3],
        'end_date': sem[4],
        'name': sem[5],
        'school_id': sem[6],
    }
    return semester

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

def enrollment_delete(request, enrollment_id):
    """Delete an enrollment"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM enrollment WHERE id = %s", [enrollment_id])
        messages.success(request, "Элсэлт устгагдлаа")
    except Exception as e:
        messages.error(request, f"Алдаа: {e}")
    
    return redirect('enrollments_list')


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
