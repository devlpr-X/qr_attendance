# app_core/urls.py
from django.urls import path
from app_core.views import courses, users, auth, admin, locations, students, attendance, sessions, export_views, documents, schedule
from app_core.views.look_up import attendance_type
from app_core.views.teacher import teacher_schedule as t_schedule, teacher
from .views.session_attendance import (
    session_generate, generate_qr_session, teacher_qr_display,
    attendance_check, attendance_mark, attendance_list_view
)
from app_core.views.teacher import teacherv2 as teacher_views

urlpatterns = [
    # Шинэ schedule path-үүд (нэмэгдэж байгаа зүйлс)
    path('admin/settings/timeslots/', schedule.school_timeslots_config, name='timeslots_config'),
    path('admin/semesters/', schedule.semester_list, name='semester_list'),
    path('admin/semester/create/', schedule.semester_create, name='semester_create'),
    path('admin/semester/<int:semester_id>/edit/', schedule.schedule_edit, name='schedule_edit'),
    # path('teacher/dashboard/', schedule.teacher_dashboard_schedule, name='teacher_dashboard'),
    path("admin/semester/<int:semester_id>/delete/", schedule.semester_delete, name="semester_delete"),


    path("admin/attendance-type/", attendance_type.attendance_type_manage, name="attendance_type_manage"),

    # auth
    path('', users.home, name='index'),
    path('login/', auth.login_view, name='login'),
    path('logout/', auth.logout_view, name='logout'),
    path('register/teacher/', auth.teacher_register, name='teacher_register'),
    path('reset/', auth.reset_password_request, name='reset_password_request'),
    path('reset/confirm/', auth.reset_password_confirm, name='reset_password_confirm'),


    # Админ dashboard (болон багшийн CRUD-рүү холбох)
    path('admin/dashboard/', admin.admin_dashboard, name='admin_dashboard'),
    path('admin/lesson-types/', admin.lesson_type_manage, name='lesson_type_manage'),
    path('admin/teacher-list/', admin.admin_teacher_list, name='admin_teacher_list'),

    # Багш
    # path("teacher/schedule/", t_schedule.teacher_schedules_list, name="teacher_schedule_select"),
    # path("teacher/schedule/<int:pattern_id>/generate/", t_schedule.generate_qr, name="generate_qr"),
    # path("teacher/schedule/<int:pattern_id>/view/", t_schedule.teacher_schedule_detail, name="teacher_schedule_detail"),
    # path('admin/teacher/add/', admin.teacher_add, name='teacher_add'),
    # path('admin/teacher/<int:user_id>/edit/', admin.teacher_edit, name='teacher_edit'),
    # path('admin/teacher/<int:user_id>/delete/', admin.teacher_delete, name='teacher_delete'),

    path('teacher/pattern/<int:pattern_id>/generate/', session_generate, name='session_generate'),
    path('teacher/pattern/<int:pattern_id>/generate/post/', generate_qr_session, name='generate_qr_session'),
    path('teacher/session/<int:session_id>/qr/', teacher_qr_display, name='teacher_qr_display'),
    path('attendance/check/', attendance_check, name='attendance_check'),          # GET?token=...
    path('attendance/mark/', attendance_mark, name='attendance_mark'),             # POST api
    path('teacher/session/<int:session_id>/attendance/', attendance_list_view, name='attendance_list'),
        
    path('teacher/dashboard/', teacher.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/schedule_list/', teacher.teacher_schedule_list, name='teacher_schedule_list'),
    path('teacher/generate/', teacher.teacher_session_generate_list, name='teacher_session_generate_list'),
    path('teacher/sessions/history/', teacher.teacher_sessions_history, name='teacher_sessions_history'),

    path('teacher/schedule/', teacher_views.teacher_schedule, name='teacher_schedule'),
    path('teacher/schedule/create_session/', teacher_views.create_session, name='create_session'),
    path('teacher/session/<uuid:token>/', teacher_views.session_detail, name='session_detail'),
    path("attendance/scan/<uuid:token>/", teacher_views.attendance_scan, name="attendance_scan"),

    path('teacher/pattern/<int:pattern_id>/detail/', teacher_views.pattern_detail, name='pattern_detail'),
    path('teacher/pattern/<int:pattern_id>/create_session/', teacher_views.pattern_create_session, name='pattern_create_session'),
    
    # Хичээл
    path('admin/courses/', courses.courses_crud, name='courses_crud'),

    # Байршил
    path('admin/school/', locations.locations_list, name='locations_list'),
    path('admin/school/add/', locations.location_add, name='location_add'),
    path('admin/school/<int:loc_id>/edit/', locations.location_edit, name='location_edit'),
    path('admin/school/<int:loc_id>/delete/', locations.location_delete, name='location_delete'),
    path('admin/school/<int:loc_id>/', locations.location_view, name='location_view'),

    # Оюутан
    path('admin/students/', students.students_list, name='students_list'),
    path('admin/students/add/', students.student_add, name='student_add'),
    path('admin/students/<int:student_id>/edit/', students.student_edit, name='student_edit'),
    path('admin/students/<int:student_id>/delete/', students.student_delete, name='student_delete'),
    path('admin/students/<int:student_id>/', students.student_view, name='student_view'),


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

    # Export
    path('admin/session/<int:session_id>/export/csv/', export_views.session_export_csv, name='session_export_csv'),
    path('admin/session/<int:session_id>/export/pdf/', export_views.session_export_pdf, name='session_export_pdf'),
    path('admin/schedule/export/daily/csv/', export_views.daily_schedule_export_csv, name='daily_schedule_export_csv'),
    path('admin/schedule/export/daily/pdf/', export_views.daily_schedule_export_pdf, name='daily_schedule_export_pdf'),

    # documents
    path('api/docs/', documents.api_docs_list, name='api_docs_list'),
    path('api/chat/', documents.api_chat, name='api_chat'),
    path('admin/documents/upload/', documents.document_upload, name='document_upload'),
    path('admin/documents/<int:doc_id>/delete/', documents.document_delete, name='document_delete'),
]
