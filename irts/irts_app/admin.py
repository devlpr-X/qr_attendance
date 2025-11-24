from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from datetime import datetime, date, timedelta
import qrcode
from io import BytesIO
import base64

from .models import (
    Location, Student, Course, TeacherProfile, 
    WeeklySchedule, ClassSession, Enrollment, 
    Attendance, AttendanceReport
)


# ===============================
# Location Admin
# ===============================
@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'latitude', 'longitude', 'radius_m')
    search_fields = ('name',)
    list_filter = ('radius_m',)


# ===============================
# Student Admin
# ===============================
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_code', 'full_name', 'enrolled_courses_count')
    search_fields = ('student_code', 'full_name')
    list_per_page = 50
    
    def enrolled_courses_count(self, obj):
        return obj.enrollment_set.count()
    enrolled_courses_count.short_description = 'Бүртгэлтэй хичээл'
    
    actions = ['export_students_csv']
    
    def export_students_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="students.csv"'
        response.write('\ufeff')  # UTF-8 BOM
        
        writer = csv.writer(response)
        writer.writerow(['Оюутны код', 'Нэр', 'Бүртгэлтэй хичээл'])
        
        for student in queryset:
            courses = ', '.join([e.course.code for e in student.enrollment_set.all()])
            writer.writerow([student.student_code, student.full_name, courses])
        
        return response
    
    export_students_csv.short_description = 'CSV татах'


# ===============================
# Course Admin
# ===============================
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'enrolled_students_count', 'sessions_count')
    search_fields = ('code', 'name')
    list_filter = ('code',)
    
    def enrolled_students_count(self, obj):
        return obj.enrollment_set.count()
    enrolled_students_count.short_description = 'Бүртгэлтэй оюутан'
    
    def sessions_count(self, obj):
        return obj.classsession_set.count()
    sessions_count.short_description = 'Хичээлийн тоо'


# ===============================
# TeacherProfile Admin
# ===============================
@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'courses_count')
    search_fields = ('name', 'user__username')
    
    def courses_count(self, obj):
        return obj.weeklyschedule_set.values('course').distinct().count()
    courses_count.short_description = 'Заадаг хичээл'


# ===============================
# WeeklySchedule Admin (Долоо хоногийн хуваарь)
# ===============================
@admin.register(WeeklySchedule)
class WeeklyScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'course', 'teacher', 'get_day_display', 
        'start_time', 'form', 'location', 
        'week_range', 'is_active'
    )
    list_filter = ('day_of_week', 'start_time', 'form', 'is_active', 'teacher')
    search_fields = ('course__name', 'teacher__name', 'course__code')
    date_hierarchy = 'week_start'
    list_per_page = 50
    
    fieldsets = (
        ('Хичээлийн мэдээлэл', {
            'fields': ('course', 'teacher', 'form', 'location')
        }),
        ('Цаг хуваарь', {
            'fields': ('day_of_week', 'start_time', 'week_start', 'week_end')
        }),
        ('Тохиргоо', {
            'fields': ('is_active',)
        }),
    )
    
    def get_day_display(self, obj):
        return obj.get_day_of_week_display()
    get_day_display.short_description = 'Гараг'
    
    def week_range(self, obj):
        return f"{obj.week_start.strftime('%m/%d')} - {obj.week_end.strftime('%m/%d')}"
    week_range.short_description = 'Долоо хоног'
    
    actions = ['duplicate_to_next_week', 'mark_inactive']
    
    def duplicate_to_next_week(self, request, queryset):
        """Дараагийн долоо хонд хуулах"""
        count = 0
        for schedule in queryset:
            new_start = schedule.week_end + timedelta(days=1)
            new_end = new_start + timedelta(days=6)
            
            WeeklySchedule.objects.create(
                course=schedule.course,
                teacher=schedule.teacher,
                day_of_week=schedule.day_of_week,
                start_time=schedule.start_time,
                form=schedule.form,
                location=schedule.location,
                week_start=new_start,
                week_end=new_end,
                is_active=True
            )
            count += 1
        
        self.message_user(request, f'{count} хуваарь дараагийн долоо хонд хуулагдлаа.')
    
    duplicate_to_next_week.short_description = 'Дараагийн долоо хонд хуулах'
    
    def mark_inactive(self, request, queryset):
        """Идэвхгүй болгох"""
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} хуваарь идэвхгүй болсон.')
    
    mark_inactive.short_description = 'Идэвхгүй болгох'


# ===============================
# ClassSession Admin
# ===============================
@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = (
        'course', 'teacher', 'session_date', 
        'start_time', 'form', 'location', 
        'attendance_count', 'is_active', 'qr_preview'
    )
    list_filter = ('is_active', 'form', 'teacher', 'session_date')
    search_fields = ('course__name', 'teacher__name', 'course__code')
    date_hierarchy = 'session_date'
    readonly_fields = ('token', 'qr_code_display', 'attendance_stats')
    list_per_page = 50
    
    fieldsets = (
        ('Хичээлийн мэдээлэл', {
            'fields': ('course', 'teacher', 'form', 'location')
        }),
        ('Цаг хуваарь', {
            'fields': ('start_time', 'week_schedule', 'session_date')
        }),
        ('QR код', {
            'fields': ('token', 'is_active', 'qr_code_display')
        }),
        ('Статистик', {
            'fields': ('attendance_stats',)
        }),
    )
    
    def attendance_count(self, obj):
        count = obj.attendance_set.count()
        success = obj.attendance_set.filter(success=True).count()
        return format_html('<span style="color: green;">{}</span> / {}', success, count)
    attendance_count.short_description = 'Ирц (Ирсэн/Нийт)'
    
    def qr_preview(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">●</span> Идэвхтэй'
            )
        return format_html('<span style="color: red;">○</span> Идэвхгүй')
    qr_preview.short_description = 'QR төлөв'
    
    def qr_code_display(self, obj):
        if not obj.token:
            return "QR код үүсээгүй байна."
        
        # QR код үүсгэх
        qr_data = f"http://127.0.0.1:8000/attendance/scan/{obj.token}/"
        qr = qrcode.make(qr_data)
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        qr_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        return format_html(
            '<div style="padding:10px; background:#f8f9fa; text-align:center; border-radius:8px;">'
            '<p><b>QR код</b></p>'
            '<img src="data:image/png;base64,{}" width="250" height="250"/>'
            '<p style="font-size:11px; color:gray; margin-top:10px;">Token: {}</p>'
            '<p style="font-size:12px;"><a href="/attendance/scan/{}/" target="_blank">Оюутны хуудас харах</a></p>'
            '</div>',
            qr_b64, obj.token, obj.token
        )
    qr_code_display.short_description = 'QR код'
    
    def attendance_stats(self, obj):
        """Ирцийн дэлгэрэнгүй статистик"""
        total = obj.attendance_set.count()
        success = obj.attendance_set.filter(success=True).count()
        failed = total - success
        
        enrolled = Enrollment.objects.filter(course=obj.course).count()
        not_attended = enrolled - total
        
        return format_html(
            '<div style="background: #e9ecef; padding: 15px; border-radius: 8px;">'
            '<table style="width: 100%;">'
            '<tr><td><b>Бүртгэлтэй оюутан:</b></td><td>{}</td></tr>'
            '<tr><td><b>Ирц бүртгүүлсэн:</b></td><td>{}</td></tr>'
            '<tr style="color: green;"><td><b>Ирсэн:</b></td><td><b>{}</b></td></tr>'
            '<tr style="color: red;"><td><b>Тасалсан/Буруу:</b></td><td><b>{}</b></td></tr>'
            '<tr style="color: orange;"><td><b>Ирээгүй:</b></td><td><b>{}</b></td></tr>'
            '<tr><td><b>Ирцийн хувь:</b></td><td><b>{:.1f}%</b></td></tr>'
            '</table>'
            '</div>',
            enrolled, total, success, failed, not_attended,
            (success / enrolled * 100) if enrolled > 0 else 0
        )
    attendance_stats.short_description = 'Ирцийн статистик'
    
    actions = ['close_sessions', 'activate_sessions']
    
    def close_sessions(self, request, queryset):
        """Хичээлүүдийг дуусгах"""
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} хичээл дууссан.')
    close_sessions.short_description = 'Хичээл дуусгах (QR идэвхгүй)'
    
    def activate_sessions(self, request, queryset):
        """Хичээлүүдийг дахин идэвхжүүлэх"""
        queryset.update(is_active=True)
        self.message_user(request, f'{queryset.count()} хичээл идэвхжсэн.')
    activate_sessions.short_description = 'QR дахин идэвхжүүлэх'


# ===============================
# Enrollment Admin
# ===============================
@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course')
    list_filter = ('course',)
    search_fields = ('student__student_code', 'student__full_name', 'course__name')
    autocomplete_fields = ['student', 'course']
    list_per_page = 100


# ===============================
# Attendance Admin
# ===============================
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'session', 'timestamp', 
        'success_badge', 'distance_display', 'note'
    )
    list_filter = ('success', 'session__course', 'timestamp')
    search_fields = (
        'student__student_code', 'student__full_name', 
        'session__course__name'
    )
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp', 'distance_display')
    list_per_page = 100
    
    def success_badge(self, obj):
        if obj.success:
            return format_html(
                '<span style="background: #d4edda; color: #155724; '
                'padding: 3px 8px; border-radius: 4px; font-weight: bold;">Ирсэн</span>'
            )
        return format_html(
            '<span style="background: #f8d7da; color: #721c24; '
            'padding: 3px 8px; border-radius: 4px; font-weight: bold;">Тасалсан</span>'
        )
    success_badge.short_description = 'Төлөв'
    
    def distance_display(self, obj):
        dist = obj.distance_from_location()
        if dist is not None:
            if dist <= obj.session.location.radius_m if obj.session.location else False:
                color = 'green'
            else:
                color = 'red'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} м</span>',
                color, dist
            )
        return '-'
    distance_display.short_description = 'Зай'


# ===============================
# AttendanceReport Admin
# ===============================
@admin.register(AttendanceReport)
class AttendanceReportAdmin(admin.ModelAdmin):
    list_display = ('course', 'teacher', 'format', 'generated_at', 'session')
    list_filter = ('format', 'generated_at', 'teacher')
    search_fields = ('course__name', 'teacher__name')
    date_hierarchy = 'generated_at'
    readonly_fields = ('generated_at',)


# Admin site customization
admin.site.site_header = "IRTS - Ирц Бүртгэлийн Систем"
admin.site.site_title = "IRTS Админ"
admin.site.index_title = "Удирдлагын самбар"
