import io
import csv
import datetime
from django.http import HttpResponse
from django.shortcuts import redirect
from django.db import connection


def session_export_csv(request, session_id):
    """Export session attendance to CSV with updated schema"""
    print("asdfdsa")
    
    try:
        # Get session info with updated schema
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    cs.id,
                    cs.name,
                    cs.date,
                    ts.value as timeslot,
                    lt.name as lesson_type,
                    c.name as course_name,
                    c.code as course_code,
                    tp.name as teacher_name,
                    cs.expires_at,
                    CASE 
                        WHEN EXTRACT(DOW FROM cs.date) = 0 THEN 'Ням'
                        WHEN EXTRACT(DOW FROM cs.date) = 1 THEN 'Даваа'
                        WHEN EXTRACT(DOW FROM cs.date) = 2 THEN 'Мягмар'
                        WHEN EXTRACT(DOW FROM cs.date) = 3 THEN 'Лхагва'
                        WHEN EXTRACT(DOW FROM cs.date) = 4 THEN 'Пүрэв'
                        WHEN EXTRACT(DOW FROM cs.date) = 5 THEN 'Баасан'
                        WHEN EXTRACT(DOW FROM cs.date) = 6 THEN 'Бямба'
                    END as day_of_week
                FROM class_session cs
                JOIN course c ON c.id = cs.course_id
                LEFT JOIN time_setting ts ON ts.id = cs.time_setting_id
                LEFT JOIN lesson_type lt ON lt.id = cs.lesson_type_id
                LEFT JOIN teacher_profile tp ON tp.id = cs.teacher_id
                WHERE cs.id = %s
            """, [session_id])
            session_row = cursor.fetchone()
        
        if not session_row:
            return HttpResponse(
                "Session олдсонгүй", 
                content_type="text/plain; charset=utf-8", 
                status=404
            )
        
        # Get attendance records with updated schema
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    s.student_code,
                    s.full_name,
                    at.name as attendance_type,
                    a.timestamp,
                    COALESCE(cg.name, '') as class_group,
                    a.lat,
                    a.lon,
                    a.device_info
                FROM attendance a
                JOIN student s ON s.id = a.student_id
                LEFT JOIN attendance_type at ON at.id = a.attendance_type_id
                LEFT JOIN student_class_group scg ON scg.student_id = s.id
                LEFT JOIN class_group cg ON cg.id = scg.class_group_id
                WHERE a.session_id = %s
                ORDER BY at.name DESC, s.full_name ASC
            """, [session_id])
            attendance_rows = cursor.fetchall()
        
        # Create CSV
        output = io.StringIO()
        output.write('\ufeff')  # BOM for Excel UTF-8 recognition
        writer = csv.writer(output)
        
        # Header information
        writer.writerow([f"Хуваарь ID: {session_row[0]}"])
        writer.writerow([f"Хуваарь нэр: {session_row[1] or 'Тодорхойгүй'}"])
        writer.writerow([f"Хичээл: {session_row[5]} ({session_row[6]})"])
        writer.writerow([f"Багшийн нэр: {session_row[7] or 'Тодорхойгүй'}"])
        writer.writerow([
            f"Огноо: {session_row[2]}",
            f"Цаг: {session_row[3] or '-'}",
            f"Төрөл: {session_row[4] or '-'}",
            "",
            f"Өдөр: {session_row[9]}"
        ])
        writer.writerow([])  # Empty row
        
        # Attendance data header
        writer.writerow([
            "Оюутны код",
            "Оюутны нэр",
            "Статус",
            "Бүртгэсэн цаг",
            "Бүлэг",
            "Lat",
            "Lon",
            "Төхөөрөмж"
        ])
        
        # Attendance data
        for row in attendance_rows:
            student_code, full_name, att_type, timestamp, class_group, lat, lon, device_info = row
            
            # Format timestamp
            ts_str = ''
            if timestamp:
                if isinstance(timestamp, datetime.datetime):
                    ts_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    ts_str = str(timestamp)
            
            writer.writerow([
                student_code or '',
                full_name or '',
                att_type or 'Тасалсан',
                ts_str,
                class_group or '-',
                str(lat) if lat else '',
                str(lon) if lon else '',
                device_info or ''
            ])
        
        # Statistics
        writer.writerow([])
        writer.writerow(["Нийт:", len(attendance_rows)])
        
        # Count by status
        status_counts = {}
        for row in attendance_rows:
            status = row[2] or 'Тасалсан'
            status_counts[status] = status_counts.get(status, 0) + 1
        
        for status, count in status_counts.items():
            writer.writerow([f"{status}:", count])
        
        # Generate filename
        date_str = session_row[2].strftime('%Y%m%d') if isinstance(session_row[2], datetime.date) else str(session_row[2])
        filename = f"attendance_session_{session_id}_{date_str}.csv"
        
        # Create response
        response = HttpResponse(
            output.getvalue(),
            content_type='text/csv; charset=utf-8-sig'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        print(f"CSV export error: {e}")
        import traceback
        traceback.print_exc()
        return HttpResponse(
            f"CSV үүсгэхэд алдаа гарлаа: {str(e)}",
            content_type="text/plain; charset=utf-8",
            status=500
        )


def daily_schedule_export_csv(request):
    """Export daily schedule with all sessions to CSV"""
    print("asdfdsa2")
    

    
    # Get date parameter
    qdate = request.GET.get('date') or datetime.date.today().isoformat()
    try:
        date_obj = datetime.date.fromisoformat(qdate)
    except ValueError:
        return HttpResponse(
            "Оруулсан огноо буруу байна",
            content_type='text/plain; charset=utf-8',
            status=400
        )
    
    try:
        # Get all sessions for the day
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    cs.id,
                    cs.name,
                    cs.date,
                    ts.value as timeslot,
                    lt.name as lesson_type,
                    c.name as course_name,
                    c.code as course_code,
                    tp.name as teacher_name
                FROM class_session cs
                JOIN course c ON c.id = cs.course_id
                LEFT JOIN time_setting ts ON ts.id = cs.time_setting_id
                LEFT JOIN lesson_type lt ON lt.id = cs.lesson_type_id
                LEFT JOIN teacher_profile tp ON tp.id = cs.teacher_id
                WHERE cs.date = %s
                ORDER BY ts.value, cs.id
            """, [date_obj])
            sessions = cursor.fetchall()
        
        # Create CSV
        output = io.StringIO()
        output.write('\ufeff')
        writer = csv.writer(output)
        
        # Header
        writer.writerow([f"Өдрийн хуваарь - Огноо: {date_obj}"])
        writer.writerow([])
        
        if not sessions:
            writer.writerow(["Энэ өдөрт хуваарь байхгүй байна."])
        else:
            for session in sessions:
                cs_id, cs_name, cs_date, timeslot, lesson_type, course_name, course_code, teacher_name = session
                
                # Session header
                writer.writerow([f"═══════════════════════════════════════════"])
                writer.writerow([f"Хуваарь ID: {cs_id}"])
                writer.writerow([f"Хуваарь нэр: {cs_name or '-'}"])
                writer.writerow([f"Хичээл: {course_name} ({course_code})"])
                writer.writerow([f"Багш: {teacher_name or '-'}"])
                writer.writerow([f"Цаг: {timeslot or '-'}", f"Төрөл: {lesson_type or '-'}"])
                writer.writerow([])
                
                # Get attendance for this session
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT 
                            s.student_code,
                            s.full_name,
                            at.name as attendance_type,
                            a.timestamp,
                            COALESCE(cg.name, '') as class_group
                        FROM attendance a
                        JOIN student s ON s.id = a.student_id
                        LEFT JOIN attendance_type at ON at.id = a.attendance_type_id
                        LEFT JOIN student_class_group scg ON scg.student_id = s.id
                        LEFT JOIN class_group cg ON cg.id = scg.class_group_id
                        WHERE a.session_id = %s
                        ORDER BY at.name DESC, s.full_name ASC
                    """, [cs_id])
                    att_rows = cursor.fetchall()
                
                if not att_rows:
                    writer.writerow(["Ирц бүртгэл байхгүй"])
                else:
                    writer.writerow(["Оюутны код", "Оюутны нэр", "Статус", "Бүртгэсэн цаг", "Бүлэг"])
                    
                    for row in att_rows:
                        student_code, full_name, att_type, timestamp, class_group = row
                        ts_str = ''
                        if timestamp:
                            if isinstance(timestamp, datetime.datetime):
                                ts_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                            else:
                                ts_str = str(timestamp)
                        
                        writer.writerow([
                            student_code or '',
                            full_name or '',
                            att_type or 'Тасалсан',
                            ts_str,
                            class_group or '-'
                        ])
                    
                    writer.writerow([f"Нийт: {len(att_rows)}"])
                
                writer.writerow([])
        
        # Generate filename
        filename = f"daily_schedule_{date_obj}.csv"
        
        # Create response
        response = HttpResponse(
            output.getvalue(),
            content_type='text/csv; charset=utf-8-sig'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        print(f"Daily CSV export error: {e}")
        import traceback
        traceback.print_exc()
        return HttpResponse(
            f"CSV үүсгэхэд алдаа гарлаа: {str(e)}",
            content_type="text/plain; charset=utf-8",
            status=500
        )