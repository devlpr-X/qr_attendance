# app_core/urls.py
from django.urls import path
from app_core.views import courses, users, auth, admin, locations, students, attendance, sessions, export_views, documents, schedule

urlpatterns = [
    # Шинэ schedule path-үүд (нэмэгдэж байгаа зүйлс)
    path('admin/settings/timeslots/', schedule.school_timeslots_config, name='timeslots_config'),
    path('admin/semesters/', schedule.semester_list, name='semester_list'),
    path('admin/semester/create/', schedule.semester_create, name='semester_create'),
    path('admin/semester/<int:semester_id>/edit/', schedule.schedule_edit, name='schedule_edit'),
    path('teacher/dashboard/', schedule.teacher_dashboard_schedule, name='teacher_dashboard'),
    path("admin/semester/<int:semester_id>/delete/", schedule.semester_delete, name="semester_delete"),


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

    # Багшийн CRUD — /admin/teacher/...
    path('admin/teacher/add/', admin.teacher_add, name='teacher_add'),
    path('admin/teacher/<int:user_id>/edit/', admin.teacher_edit, name='teacher_edit'),
    path('admin/teacher/<int:user_id>/delete/', admin.teacher_delete, name='teacher_delete'),

    # Хичээл
    path('admin/courses/', courses.courses_list, name='courses_list'),
    path('admin/courses/add/', courses.course_add, name='course_add'),
    path('admin/courses/<int:course_id>/', courses.course_view, name='course_view'),
    path('admin/courses/<int:course_id>/edit/', courses.course_edit, name='course_edit'),
    path('admin/courses/<int:course_id>/delete/', courses.course_delete, name='course_delete'),

    # Байршил
    path('admin/locations/', locations.locations_list, name='locations_list'),
    path('admin/locations/add/', locations.location_add, name='location_add'),
    path('admin/locations/<int:loc_id>/edit/', locations.location_edit, name='location_edit'),
    path('admin/locations/<int:loc_id>/delete/', locations.location_delete, name='location_delete'),
    path('admin/locations/<int:loc_id>/', locations.location_view, name='location_view'),

    # Оюутан
    path('admin/students/', students.students_list, name='students_list'),
    path('admin/students/add/', students.student_add, name='student_add'),
    path('admin/students/<int:student_id>/edit/', students.student_edit, name='student_edit'),
    path('admin/students/<int:student_id>/delete/', students.student_delete, name='student_delete'),
    path('admin/students/<int:student_id>/', students.student_view, name='student_view'),

    # Бүргэл
    path('admin/enrollments/', students.enrollments_list, name='enrollments_list'),
    path('admin/enrollments/add/', students.enrollment_add, name='enrollment_add'),
    path('admin/enrollments/<int:enroll_id>/delete/', students.enrollment_delete, name='enrollment_delete'),
    path('admin/students/<int:student_id>/enroll/', students.enroll_student_to_course, name='enroll_student_to_course'),
    path('admin/courses/<int:course_id>/enrollments/', students.course_enrollments, name='course_enrollments'),
    
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
