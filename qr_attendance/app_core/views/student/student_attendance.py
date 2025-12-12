from django.shortcuts import render, redirect
from django.db import connection
from django.utils import timezone
from django.http import Http404


def student_attendance(request, student_code):
    """View student attendance by student code"""
    
    # Get current academic year and term
    now = timezone.now()
    current_year = now.year
    current_term = 2 if now.month <= 7 else 1
    
    # Adjust year for second semester (Jan-July is previous academic year's 2nd semester)
    if current_term == 2:
        current_year -= 1
    
    # Check if year/term override in GET params
    selected_year = request.GET.get('year')
    selected_term = request.GET.get('term')
    
    if selected_year:
        try:
            current_year = int(selected_year)
        except ValueError:
            pass
    
    if selected_term:
        try:
            current_term = int(selected_term)
        except ValueError:
            pass
    
    # Find student
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, student_code, full_name
            FROM student
            WHERE student_code = %s
            LIMIT 1
        """, [student_code])
        student_row = cursor.fetchone()
    
    if not student_row:
        raise Http404("Оюутан олдсонгүй")
    
    student = {
        'id': student_row[0],
        'code': student_row[1],
        'name': student_row[2]
    }
    
    # Get student's courses for current year/term
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT 
                c.id,
                c.name,
                c.code,
                COUNT(DISTINCT cs.id) as total_sessions,
                COUNT(DISTINCT CASE WHEN a.attendance_type_id = 1 THEN a.id END) as present_count,
                COUNT(DISTINCT CASE WHEN a.attendance_type_id = 2 THEN a.id END) as absent_count,
                COUNT(DISTINCT CASE WHEN a.attendance_type_id = 3 THEN a.id END) as late_count,
                COUNT(DISTINCT CASE WHEN a.attendance_type_id = 4 THEN a.id END) as excused_count,
                cg.name as group_name,
                cg.group_number
            FROM student_class_group scg
            INNER JOIN class_group cg ON cg.id = scg.class_group_id
            INNER JOIN class_group_schedule cgs ON cgs.class_group_id = cg.id
            INNER JOIN course_schedule_pattern csp ON csp.id = cgs.course_schedule_pattern_id
            INNER JOIN course c ON c.id = csp.course_id
            INNER JOIN semester sem ON sem.id = csp.semester_id
            LEFT JOIN class_session cs ON cs.course_id = c.id 
                AND EXTRACT(YEAR FROM cs.date) = sem.school_year
                AND ((sem.term = 1 AND EXTRACT(MONTH FROM cs.date) BETWEEN 8 AND 12)
                     OR (sem.term = 2 AND EXTRACT(MONTH FROM cs.date) BETWEEN 1 AND 7))
            LEFT JOIN attendance a ON a.session_id = cs.id AND a.student_id = %s
            WHERE scg.student_id = %s
                AND sem.school_year = %s
                AND sem.term = %s
            GROUP BY c.id, c.name, c.code, cg.name, cg.group_number
            ORDER BY c.name
        """, [student['id'], student['id'], current_year, current_term])
        
        courses = []
        for row in cursor.fetchall():
            total = row[3] or 0
            present = row[4] or 0
            absent = row[5] or 0
            late = row[6] or 0
            excused = row[7] or 0
            
            # Calculate attendance percentage
            attended = present + late + excused
            percentage = (attended / total * 100) if total > 0 else 0
            
            courses.append({
                'id': row[0],
                'name': row[1],
                'code': row[2],
                'total_sessions': total,
                'present_count': present,
                'absent_count': absent,
                'late_count': late,
                'excused_count': excused,
                'attendance_percentage': round(percentage, 1),
                'group_name': row[8],
                'group_number': row[9]
            })
    
    # Get available years for dropdown
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT school_year
            FROM semester
            ORDER BY school_year DESC
        """)
        available_years = [row[0] for row in cursor.fetchall()]
    
    return render(request, 'student/attendance.html', {
        'student': student,
        'courses': courses,
        'current_year': current_year,
        'current_term': current_term,
        'available_years': available_years,
    })


def student_course_detail(request, student_code, course_id):
    """View detailed attendance for a specific course"""
    
    # Get current academic year and term
    now = timezone.now()
    current_year = now.year
    current_term = 2 if now.month <= 7 else 1
    
    if current_term == 2:
        current_year -= 1
    
    # Check if year/term override in GET params
    selected_year = request.GET.get('year', current_year)
    selected_term = request.GET.get('term', current_term)
    
    try:
        selected_year = int(selected_year)
        selected_term = int(selected_term)
    except ValueError:
        pass
    
    # Find student
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, student_code, full_name
            FROM student
            WHERE student_code = %s
            LIMIT 1
        """, [student_code])
        student_row = cursor.fetchone()
    
    if not student_row:
        raise Http404("Оюутан олдсонгүй")
    
    student = {
        'id': student_row[0],
        'code': student_row[1],
        'name': student_row[2]
    }
    
    # Get course info
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, name, code
            FROM course
            WHERE id = %s
        """, [course_id])
        course_row = cursor.fetchone()
    
    if not course_row:
        raise Http404("Хичээл олдсонгүй")
    
    course = {
        'id': course_row[0],
        'name': course_row[1],
        'code': course_row[2]
    }
    
    # Get all sessions and attendance for this course
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                cs.id,
                cs.date,
                ts.value as timeslot,
                lt.name as lesson_type,
                cs.name as session_name,
                cr.room_number,
                a.id as attendance_id,
                a.timestamp as attendance_time,
                at.name as attendance_type_name,
                at.id as attendance_type_id,
                tp.name as teacher_name
            FROM class_session cs
            LEFT JOIN time_setting ts ON ts.id = cs.time_setting_id
            LEFT JOIN lesson_type lt ON lt.id = cs.lesson_type_id
            LEFT JOIN class_room cr ON cr.id = (
                SELECT class_room_id FROM course_schedule_pattern 
                WHERE course_id = cs.course_id LIMIT 1
            )
            LEFT JOIN attendance a ON a.session_id = cs.id AND a.student_id = %s
            LEFT JOIN attendance_type at ON at.id = a.attendance_type_id
            LEFT JOIN teacher_profile tp ON tp.id = cs.teacher_id
            WHERE cs.course_id = %s
                AND EXTRACT(YEAR FROM cs.date) = %s
                AND ((EXTRACT(MONTH FROM cs.date) BETWEEN 8 AND 12 AND %s = 1)
                     OR (EXTRACT(MONTH FROM cs.date) BETWEEN 1 AND 7 AND %s = 2))
            ORDER BY cs.date DESC, cs.created_at DESC
        """, [student['id'], course_id, selected_year, selected_term, selected_term])
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'id': row[0],
                'date': row[1],
                'timeslot': row[2],
                'lesson_type': row[3],
                'session_name': row[4],
                'room_number': row[5],
                'attendance_id': row[6],
                'attendance_time': row[7],
                'attendance_type_name': row[8],
                'attendance_type_id': row[9],
                'teacher_name': row[10]
            })
    
    # Calculate statistics
    total_sessions = len(sessions)
    present_count = sum(1 for s in sessions if s['attendance_type_id'] == 1)
    absent_count = sum(1 for s in sessions if s['attendance_type_id'] == 2)
    late_count = sum(1 for s in sessions if s['attendance_type_id'] == 3)
    excused_count = sum(1 for s in sessions if s['attendance_type_id'] == 4)
    
    attended = present_count + late_count + excused_count
    percentage = (attended / total_sessions * 100) if total_sessions > 0 else 0
    
    stats = {
        'total_sessions': total_sessions,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'excused_count': excused_count,
        'attendance_percentage': round(percentage, 1)
    }
    
    return render(request, 'student/course_detail.html', {
        'student': student,
        'course': course,
        'sessions': sessions,
        'stats': stats,
        'selected_year': selected_year,
        'selected_term': selected_term,
    })