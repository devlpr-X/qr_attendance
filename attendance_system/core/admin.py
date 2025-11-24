from django.contrib import admin
from .models import *

@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_time', 'end_time')

@admin.register(LessonType)
class LessonTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('code', 'last_name', 'first_name')

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'credit')
    filter_horizontal = ('teachers',)

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('code', 'last_name', 'first_name', 'group', 'year')

@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ('course', 'teacher', 'date', 'timeslot')
    actions = ['generate_qr']

    def generate_qr(self, request, queryset):
        for session in queryset:
            session.generate_qr_code()
        self.message_user(request, "QR codes generated successfully.")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.groups.filter(name='Teacher').exists():
            try:
                teacher = Teacher.objects.get(user=request.user)
                return qs.filter(teacher=teacher)
            except Teacher.DoesNotExist:
                return qs.none()
        return qs

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('session', 'student', 'timestamp')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.groups.filter(name='Teacher').exists():
            try:
                teacher = Teacher.objects.get(user=request.user)
                return qs.filter(session__teacher=teacher)
            except Teacher.DoesNotExist:
                return qs.none()
        return qs