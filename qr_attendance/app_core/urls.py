# app_core/urls.py
from django.urls import path
from app_core.views import courses, admin, attendance, sessions
from app_core.views.enrollment import enrollment 

urlpatterns = [
    # Админ dashboard (болон багшийн CRUD-рүү холбох)
    path('admin/dashboard/', admin.admin_dashboard, name='admin_dashboard'),
    path('admin/teacher-list/', admin.admin_teacher_list, name='admin_teacher_list'),
    path('admin/courses/', courses.courses_crud, name='courses_crud'),

    # sessions
    path('admin/sessions/', sessions.sessions_list, name='sessions_list'),
    path('admin/sessions/add/', sessions.session_add, name='session_add'),
    path('admin/sessions/<int:session_id>/', sessions.session_view, name='session_view'),
    path('admin/sessions/<int:session_id>/mark/', attendance.teacher_mark_attendance, name='teacher_mark_attendance'),

    # Ирц endpoints (scan + submit)
    path('attendance/<uuid:token>/scan', attendance.scan_page, name='scan_page'),
    path('attendance/<uuid:token>/submit/', attendance.submit_attendance, name='submit_attendance'),

    # Enrollments
    path('admin/enrollments/', enrollment.enrollments_list, name='enrollments_list'),
    path('admin/enrollments/delete/<int:enrollment_id>/', enrollment.enrollment_delete, name='enrollment_delete'),
    
    # APIs
    path("api/assigned-students/", enrollment.get_assigned_students_api, name="api_assigned_students"),
    path("api/enrolled-students/", enrollment.get_enrolled_students_api, name="api_enrolled_students"),
]
