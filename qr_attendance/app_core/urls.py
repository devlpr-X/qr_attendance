# app_core/urls.py
from django.urls import path
from app_core.views import courses, admin, students, attendance, sessions

urlpatterns = [
    # Админ dashboard (болон багшийн CRUD-рүү холбох)
    path('admin/dashboard/', admin.admin_dashboard, name='admin_dashboard'),
    path('admin/teacher-list/', admin.admin_teacher_list, name='admin_teacher_list'),
    path('admin/courses/', courses.courses_crud, name='courses_crud'),

    # Бүргэл
    path('admin/enrollments/', students.enrollments_list, name='enrollments_list'),
    path('admin/enrollment/delete/<int:enrollment_id>/', students.enrollment_delete, name='enrollment_delete'),
    
    # sessions
    path('admin/sessions/', sessions.sessions_list, name='sessions_list'),
    path('admin/sessions/add/', sessions.session_add, name='session_add'),
    path('admin/sessions/<int:session_id>/', sessions.session_view, name='session_view'),
    path('admin/sessions/<int:session_id>/mark/', attendance.teacher_mark_attendance, name='teacher_mark_attendance'),

    # Ирц endpoints (scan + submit)
    path('attendance/<uuid:token>/scan', attendance.scan_page, name='scan_page'),
    path('attendance/<uuid:token>/submit/', attendance.submit_attendance, name='submit_attendance'),
]
