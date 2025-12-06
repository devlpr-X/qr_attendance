# app_core/urls.py
from django.urls import path
from app_core.views import users, auth

urlpatterns = [
    # auth
    path('', users.home, name='index'),
    path('login/', auth.login_view, name='login'),
    path('logout/', auth.logout_view, name='logout'),
    path('register/teacher/', auth.teacher_register, name='teacher_register'),
    path('reset/', auth.reset_password_request, name='reset_password_request'),
    path('reset/confirm/', auth.reset_password_confirm, name='reset_password_confirm'),
]
