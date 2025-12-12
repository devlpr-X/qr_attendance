# app_core/views/export_views.py

import os
import io
import datetime
import csv
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.db import connection
from ..utils import _is_admin, set_cookie_safe

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


def _font_file_path():
    candidates = [
        os.path.join(getattr(settings, 'BASE_DIR', ''), 'static', 'fonts', 'DejaVuSans.ttf'),
        os.path.join(getattr(settings, 'BASE_DIR', ''), 'staticfiles', 'fonts', 'DejaVuSans.ttf'),
        os.path.join(getattr(settings, 'BASE_DIR', ''), 'static', 'fonts', 'NotoSans-Regular.ttf'),
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        'C:\\Windows\\Fonts\\DejaVuSans.ttf',
        'DejaVuSans.ttf',
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None


def _register_dejavu_font():
    font_path = _font_file_path()
    if not font_path:
        return (None, "Фонт файл олдсонгүй. static/fonts/DejaVuSans.ttf байрлуулсан эсэхийг шалгана уу.")
    font_name = "AppCyr"
    try:
        pdfmetrics.registerFont(TTFont(font_name, font_path))
    except Exception:
        pass
    return (font_name, None)


def session_export_csv(request, session_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT cs.id, cs.token, cs.date, cs.timeslot, cs.lesson_type, c.name AS course_name, c.code
            FROM class_session cs
            JOIN course c ON c.id = cs.course_id
            WHERE cs.id = %s
        """, [session_id])
        session_row = cursor.fetchone()
        if not session_row:
            return HttpResponse("Session олдсонгүй", content_type="text/plain; charset=utf-8", status=404)

        cursor.execute("""
            SELECT s.student_code, s.full_name, a.status, a.timestamp, a.lat, a.lon
            FROM attendance a
            JOIN student s ON s.id = a.student_id
            WHERE a.session_id = %s
            ORDER BY a.timestamp ASC
        """, [session_id])
        rows = cursor.fetchall()

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow([f"Session ID: {session_id}"])
    writer.writerow([f"Хичээл: {session_row[5]} ({session_row[6]})"])
    writer.writerow([f"Огноо: {session_row[2]}", f"Цаг: {session_row[3]}", f"Төрөл: {session_row[4]}"])
    writer.writerow([])
    writer.writerow(["Оюутны код", "Оюутны нэр", "Статус", "Бүртгэсэн цаг", "Lat", "Lon"])
    for r in rows:
        student_code, full_name, status, ts, lat, lon = r
        ts_str = ts.isoformat() if ts else ''
        writer.writerow([student_code or '', full_name or '', status or '', ts_str, lat or '', lon or ''])

    filename = f"session_{session_id}_attendance_{datetime.date.today().isoformat()}.csv"
    resp = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


def daily_schedule_export_csv(request):
    if not _is_admin(request):
        return redirect('login')

    qdate = request.GET.get('date') or datetime.date.today().isoformat()
    try:
        date_obj = datetime.date.fromisoformat(qdate)
    except Exception:
        return HttpResponse("Оруулсан огноо буруу байна", content_type='text/plain; charset=utf-8', status=400)

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT cs.id, cs.date, cs.timeslot, cs.lesson_type, c.name as course_name, c.code, cs.teacher_id, cs.location_id
            FROM class_session cs
            JOIN course c ON c.id = cs.course_id
            WHERE cs.date = %s
            ORDER BY cs.timeslot, cs.id
        """, [date_obj])
        sessions = cursor.fetchall()

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow([f"Хуваарь - Өдөр: {date_obj.isoformat()}"])
    writer.writerow([])

    for s in sessions:
        cs_id, cs_date, cs_timeslot, cs_ltype, course_name, course_code, teacher_id, location_id = s
        writer.writerow([f"Session ID: {cs_id}", f"{course_name} ({course_code})", f"Цаг: {cs_timeslot}", f"Төрөл: {cs_ltype}", f"Багш ID: {teacher_id}"])
        writer.writerow(["Оюутны код", "Оюутны нэр", "Статус", "Бүртгэсэн цаг", "Lat", "Lon"])

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT s.student_code, s.full_name, a.status, a.timestamp, a.lat, a.lon
                FROM attendance a
                JOIN student s ON s.id = a.student_id
                WHERE a.session_id = %s
                ORDER BY a.timestamp ASC
            """, [cs_id])
            att_rows = cursor.fetchall()

        if not att_rows:
            writer.writerow(["(Ирц бүртгэл байхгүй)"])
        else:
            for ar in att_rows:
                student_code, full_name, status, ts, lat, lon = ar
                ts_str = ts.isoformat() if ts else ''
                writer.writerow([student_code or '', full_name or '', status or '', ts_str, lat or '', lon or ''])
        writer.writerow([])

    filename = f"daily_schedule_{date_obj.isoformat()}.csv"
    resp = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


def session_export_pdf(request, session_id):
    if not _is_admin(request):
        return redirect('login')

    if not REPORTLAB_AVAILABLE:
        return HttpResponse("ReportLab байхгүй", content_type='text/plain; charset=utf-8', status=500)

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT cs.id, cs.token, cs.date, cs.timeslot, cs.lesson_type, c.name AS course_name, c.code
            FROM class_session cs
            JOIN course c ON c.id = cs.course_id
            WHERE cs.id = %s
        """, [session_id])
        session_row = cursor.fetchone()
        if not session_row:
            return HttpResponse("Session олдсонгүй", content_type='text/plain; charset=utf-8', status=404)

        cursor.execute("""
            SELECT s.student_code, s.full_name, a.status, a.timestamp, a.lat, a.lon
            FROM attendance a
            JOIN student s ON s.id = a.student_id
            WHERE a.session_id = %s
            ORDER BY a.timestamp ASC
        """, [session_id])
        rows = cursor.fetchall()

    font_name, font_err = _register_dejavu_font()
    if not font_name:
        return HttpResponse("PDF-д кирилл зөв гаргахгүй байна: " + font_err, content_type='text/plain; charset=utf-8', status=500)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=16, leftMargin=16, topMargin=16, bottomMargin=16)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CyrTitle', parent=styles['Heading2'], fontName=font_name))
    styles.add(ParagraphStyle(name='CyrNormal', parent=styles['Normal'], fontName=font_name, fontSize=9))

    title = Paragraph(f"Session {session_row[0]} — {session_row[5]} ({session_row[6]})", styles['CyrTitle'])
    meta = Paragraph(f"Огноо: {session_row[2]} — Цаг: {session_row[3]} — Төрөл: {session_row[4]}", styles['CyrNormal'])
    elements = [title, Spacer(1,6), meta, Spacer(1,12)]

    header_style = styles['CyrNormal']
    data = [
        [Paragraph("№", header_style),
         Paragraph("Оюутны код", header_style),
         Paragraph("Оюутны нэр", header_style),
         Paragraph("Статус", header_style),
         Paragraph("Бүртгэсэн цаг", header_style),
         Paragraph("Lat", header_style),
         Paragraph("Lon", header_style)]
    ]
    for i, r in enumerate(rows, start=1):
        student_code, full_name, status, ts, lat, lon = r
        ts_str = ts.isoformat() if ts else ""
        data.append([Paragraph(str(i), header_style),
                     Paragraph(student_code or '', header_style),
                     Paragraph(full_name or '', header_style),
                     Paragraph(status or '', header_style),
                     Paragraph(ts_str, header_style),
                     Paragraph(str(lat or ''), header_style),
                     Paragraph(str(lon or ''), header_style)])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), font_name),
                               ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1d5ede')),
                               ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                               ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                               ('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="session_{session_id}_attendance.pdf"'
    return response


def daily_schedule_export_pdf(request):
    if not _is_admin(request):
        return redirect('login')

    if not REPORTLAB_AVAILABLE:
        return HttpResponse("ReportLab байхгүй", content_type='text/plain; charset=utf-8', status=500)

    qdate = request.GET.get('date') or datetime.date.today().isoformat()
    try:
        date_obj = datetime.date.fromisoformat(qdate)
    except Exception:
        return HttpResponse("Оруулсан огноо буруу байна", content_type='text/plain; charset=utf-8', status=400)

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT cs.id, cs.date, cs.timeslot, cs.lesson_type, c.name as course_name, c.code, cs.teacher_id, cs.location_id
            FROM class_session cs
            JOIN course c ON c.id = cs.course_id
            WHERE cs.date = %s
            ORDER BY cs.timeslot, cs.id
        """, [date_obj])
        sessions = cursor.fetchall()

    font_name, font_err = _register_dejavu_font()
    if not font_name:
        return HttpResponse("PDF-д кирилл зөв гаргахгүй байна: " + font_err, content_type='text/plain; charset=utf-8', status=500)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18, leftMargin=18, topMargin=18, bottomMargin=18)
    elements = []
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='MyHeading2', parent=styles['Heading2'], fontName=font_name))
    styles.add(ParagraphStyle(name='MyHeading4', parent=styles['Heading4'], fontName=font_name))
    styles.add(ParagraphStyle(name='MyNormal', parent=styles['Normal'], fontName=font_name, fontSize=9))

    elements.append(Paragraph(f"Өдрийн хуваарь тайлан: {date_obj.isoformat()}", styles['MyHeading2']))
    elements.append(Spacer(1,6))

    for s in sessions:
        cs_id, cs_date, cs_timeslot, cs_ltype, course_name, course_code, teacher_id, location_id = s
        elements.append(Paragraph(f"Session {cs_id} — {course_name} ({course_code}) — Цаг: {cs_timeslot} — Төрөл: {cs_ltype}", styles['MyHeading4']))
        elements.append(Spacer(1,6))

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT s.student_code, s.full_name, a.status, a.timestamp, a.lat, a.lon
                FROM attendance a
                JOIN student s ON s.id = a.student_id
                WHERE a.session_id = %s
                ORDER BY a.timestamp ASC
            """, [cs_id])
            att_rows = cursor.fetchall()

        if not att_rows:
            elements.append(Paragraph("(Ирц бүртгэл байхгүй)", styles['MyNormal']))
            elements.append(Spacer(1,8))
            continue

        data = [[Paragraph("№", styles['MyNormal']),
                 Paragraph("Оюутны код", styles['MyNormal']),
                 Paragraph("Оюутны нэр", styles['MyNormal']),
                 Paragraph("Статус", styles['MyNormal']),
                 Paragraph("Бүртгэсэн цаг", styles['MyNormal']),
                 Paragraph("Lat", styles['MyNormal']),
                 Paragraph("Lon", styles['MyNormal'])]]

        for i, ar in enumerate(att_rows, start=1):
            student_code, full_name, status, ts, lat, lon = ar
            ts_str = ts.isoformat() if ts else ''
            data.append([Paragraph(str(i), styles['MyNormal']),
                         Paragraph(student_code or '', styles['MyNormal']),
                         Paragraph(full_name or '', styles['MyNormal']),
                         Paragraph(status or '', styles['MyNormal']),
                         Paragraph(ts_str, styles['MyNormal']),
                         Paragraph(str(lat or ''), styles['MyNormal']),
                         Paragraph(str(lon or ''), styles['MyNormal'])])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1d5ede')),
                                   ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                                   ('FONTNAME', (0,0), (-1,-1), font_name),
                                   ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                                   ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey])]))
        elements.append(table)
        elements.append(Spacer(1,12))

    if not sessions:
        elements.append(Paragraph("(Тухайн өдөр хуваарь олдсонгүй)", styles['MyNormal']))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="daily_schedule_{date_obj.isoformat()}.pdf"'
    return response
