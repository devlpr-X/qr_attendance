from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.teacher_dashboard, name='teacher_dashboard'),  # /dashboard/
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard_alt'),  # /teacher/dashboard/
    
    # Хичээл сонгох
    path('select-class/', views.select_current_class, name='select_current_class'),
    
    # Session QR
    path('session/<uuid:token>/', views.session_qr, name='session_qr'),
    path('session/<uuid:token>/close/', views.close_session, name='close_session'),
    
    # Оюутны ирц
    path('attendance/scan/<uuid:token>/', views.scan_page, name='scan_page'),
    path('attendance/submit/<uuid:token>/', views.submit_attendance, name='submit_attendance'),
    
    # Ирцийн жагсаалт
    path('attendance/', views.attendance_list, name='attendance_list_all'),
    path('attendance/<int:session_id>/', views.attendance_list, name='attendance_list'),
    path('statistics/<int:course_id>/', views.attendance_statistics, name='attendance_statistics'),
    
    # Export
    path('export/csv/<int:session_id>/', views.export_attendance_csv, name='export_csv'),
    path('export/excel/<int:session_id>/', views.export_attendance_excel, name='export_excel'),
    path('export/pdf/<int:session_id>/', views.export_attendance_pdf, name='export_pdf'),
    path('export/course-excel/<int:course_id>/', views.export_course_attendance_excel, name='export_course_excel'),
]
