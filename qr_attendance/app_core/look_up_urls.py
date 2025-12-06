# app_core/urls.py
from django.urls import path
from app_core.views.look_up import attendance_type, lesson_type
from app_core.views import locations, schedule

urlpatterns = [
    path('admin/lesson-types/', lesson_type.lesson_type_manage, name='lesson_type_manage'),
    
    path("admin/attendance-type/", attendance_type.attendance_type_manage, name="attendance_type_manage"),

    path('admin/settings/timeslots/', schedule.school_timeslots_config, name='timeslots_config'),

    # semester
    path('admin/semesters/', schedule.semester_list, name='semester_list'),
    path('admin/semester/create/', schedule.semester_create, name='semester_create'),
    path('admin/semester/<int:semester_id>/edit/', schedule.schedule_edit, name='schedule_edit'),
    path("admin/semester/<int:semester_id>/delete/", schedule.semester_delete, name="semester_delete"),

    # Байршил
    path('admin/school/', locations.locations_list, name='locations_list'),
    path('admin/school/add/', locations.location_add, name='location_add'),
    path('admin/school/<int:loc_id>/edit/', locations.location_edit, name='location_edit'),
    path('admin/school/<int:loc_id>/delete/', locations.location_delete, name='location_delete'),
    path('admin/school/<int:loc_id>/', locations.location_view, name='location_view'),

]
