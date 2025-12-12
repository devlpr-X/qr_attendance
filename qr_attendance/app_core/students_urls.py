# app_core/urls.py
from django.urls import path
from app_core.views import students
from app_core.views.student import student_attendance

urlpatterns = [
    # Оюутан
    path('admin/students/', students.students_list, name='students_list'),
    path('admin/students/add/', students.student_add, name='student_add'),
    path('admin/students/<int:student_id>/edit/', students.student_edit, name='student_edit'),
    path('admin/students/<int:student_id>/delete/', students.student_delete, name='student_delete'),
    path('admin/students/<int:student_id>/', students.student_view, name='student_view'),

    path('student/<str:student_code>/', student_attendance.student_attendance, name='student_attendance'),
    path('student/<str:student_code>/course/<int:course_id>/', student_attendance.student_course_detail, name='student_course_detail'),
]