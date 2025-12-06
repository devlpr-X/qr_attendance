# app_core/urls.py
from django.urls import path
from app_core.views import students

urlpatterns = [
    # Оюутан
    path('admin/students/', students.students_list, name='students_list'),
    path('admin/students/add/', students.student_add, name='student_add'),
    path('admin/students/<int:student_id>/edit/', students.student_edit, name='student_edit'),
    path('admin/students/<int:student_id>/delete/', students.student_delete, name='student_delete'),
    path('admin/students/<int:student_id>/', students.student_view, name='student_view'),
]
