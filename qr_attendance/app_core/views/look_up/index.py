# app_core/views/look_up/index.py
from django.shortcuts import render, redirect
from app_core.utils import _is_admin

def lookup_index(request):
    if not _is_admin(request):
        return redirect("login")

    return render(request, "admin/look_up/index.html")
