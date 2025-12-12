# app_core/urls.py
from django.urls import path
from app_core.views.teacher import teacher
from app_core.views import export_views
from .views.session_attendance import (
    session_generate, generate_qr_session, teacher_qr_display,
    attendance_check, attendance_mark, attendance_list_view
)
from .views import attendance

urlpatterns = [
    path('teacher/dashboard/', teacher.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/create_session/', teacher.create_session, name='create_session'),
    path('session/<int:session_id>/export/csv/', export_views.session_export_csv, name='session_export_csv'),
    path('daily-schedule/export/csv/', export_views.daily_schedule_export_csv, name='daily_schedule_export_csv'),
    
    
    path('teacher/pattern/<int:pattern_id>/generate/', session_generate, name='session_generate'),
    path('teacher/pattern/<int:pattern_id>/generate/post/', generate_qr_session, name='generate_qr_session'),
    path('teacher/session/<int:session_id>/qr/', teacher_qr_display, name='teacher_qr_display'),
    path('teacher/session/<int:session_id>/attendance/', attendance_list_view, name='attendance_list'),
        
    path('teacher/schedule_list/', teacher.teacher_schedule_list, name='teacher_schedule_list'),
    path('teacher/generate/', teacher.teacher_session_generate_list, name='teacher_session_generate_list'),
    path('teacher/sessions/history/', teacher.teacher_sessions_history, name='teacher_sessions_history'),

    path('teacher/schedule/', teacher.teacher_schedule, name='teacher_schedule'),
    # path('teacher/schedule/create_session/', teacher.create_session, name='create_session'),
    path('teacher/session/<uuid:token>/', teacher.session_detail, name='session_detail'),
    path("attendance/scan/<uuid:token>/", teacher.attendance_scan, name="attendance_scan"),

    path('teacher/pattern/<int:pattern_id>/detail/', teacher.pattern_detail, name='pattern_detail'),
    path('teacher/pattern/<int:pattern_id>/create_session/', teacher.pattern_create_session, name='pattern_create_session'),
    path('attendance/check/', attendance_check, name='attendance_check'),          # GET?token=...
    path('attendance/mark/', attendance_mark, name='attendance_mark'),             # POST api
    
    path('teacher/create_session/', teacher.create_session, name='create_session'),
    
    # Student attendance routes
    path('attendance/<uuid:token>/scan/', attendance.scan_page, name='scan_page'),
    path('attendance/<uuid:token>/submit/', attendance.submit_attendance, name='submit_attendance'),
]
