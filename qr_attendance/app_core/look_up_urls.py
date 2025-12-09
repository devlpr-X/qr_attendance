# app_core/urls.py
from django.urls import path
from app_core.views.look_up import attendance_type, lesson_type, department, class_room, program, room_type, class_group, student_class_group
from app_core.views import locations, schedule
from app_core.views.look_up.index import lookup_index 
from app_core.views.look_up import student_class_group

urlpatterns = [
    path('admin/look-up/', lookup_index, name='lookup_index'),
    
    path('admin/look-up/departments/', department.department_manage, name='department_manage'),
    path('admin/look-up/programs/', program.program_manage, name='program_manage'),
    path('admin/look-up/class-rooms/', class_room.class_room_manage, name='class_room_manage'),
    path('admin/look-up/room-types/', room_type.room_type_manage, name='room_type_manage'),
    path('admin/look-up/lesson-types/', lesson_type.lesson_type_manage, name='lesson_type_manage'),
    path("admin/look-up/attendance-type/", attendance_type.attendance_type_manage, name="attendance_type_manage"),    
    path('admin/look-up/class-groups/', class_group.class_group_manage, name='class_group_manage'),
    path('admin/look-up/student-class-groups/', student_class_group.student_class_group_manage, name='student_class_group_manage'),


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

    #  path("api/assigned-students/", student_class_group.get_assigned_students_api, name="api_assigned_students"),
]
