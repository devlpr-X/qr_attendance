from django.urls import path, include

urlpatterns = [
    path('', include('app_core.urls')),
    path('', include('app_core.auth_urls')),
    path('', include('app_core.file_urls')),
    path('', include('app_core.students_urls')),
    path('', include('app_core.teacher_urls')),
    path('', include('app_core.look_up_urls')),
]
