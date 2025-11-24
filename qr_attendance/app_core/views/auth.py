from django.views.decorators.csrf import csrf_protect
from django.shortcuts import render, redirect
from django.db import connection
import hashlib
from ..utils import classify_flash, set_cookie_safe, get_cookie_safe

@csrf_protect
def login_view(request):
    # Flash message-ийг cookie-с авч ирж class тодорхойлно
    flash_msg = get_cookie_safe(request, 'flash_msg')
    flash_status = get_cookie_safe(request, 'flash_status')
    flash = None
    if flash_msg and flash_status:
        flash = {
            "message": flash_msg,
            "status": int(flash_status),
            "class": classify_flash(flash_status)
        }

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        hashed_password = hashlib.md5(password.encode()).hexdigest()

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT A.id, A.email, A.role_id, B.name AS role_name
                FROM app_user A
                INNER JOIN ref_role B ON B.id = A.role_id
                WHERE A.email = %s AND A.hashed_password = %s
                  AND A.is_banned = false AND A.is_verified = true
            """, [email, hashed_password])
            user = cursor.fetchone()

        if user:
            user_id, email_db, role_id, role_name = user
            redirect_page = (
                'admin_dashboard' if role_name.lower() == 'admin'
                else 'teacher_dashboard'
            )
            response = redirect(redirect_page)

            # Cookies
            set_cookie_safe(response, 'user_id', user_id, 3600*24)
            set_cookie_safe(response, 'email', email_db, 3600*24)
            set_cookie_safe(response, 'role_id', role_id, 3600*24)
            set_cookie_safe(response, 'role_name', role_name.lower(), 3600*24)

            # Flash (10 секунд хадгалах)
            set_cookie_safe(response, 'flash_msg', "Амжилттай нэвтэрлээ!", 10)
            set_cookie_safe(response, 'flash_status', 200, 10)

            return response

        # User not found
        response = redirect('login')
        set_cookie_safe(response, 'flash_msg', "Нэвтрэх нэр эсвэл нууц үг буруу", 10)
        set_cookie_safe(response, 'flash_status', 400, 10)
        return response

    return render(request, "login.html", {'flash': flash})

def logout_view(request):
    response = redirect('login')
    response.delete_cookie('user_id')
    response.delete_cookie('email')
    response.delete_cookie('role_id')
    response.delete_cookie('role_name')
    response.delete_cookie('flash_msg')
    response.delete_cookie('flash_status')
    return response
