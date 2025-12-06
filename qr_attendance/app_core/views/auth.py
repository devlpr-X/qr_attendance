# app_core/views/auth.py

from django.views.decorators.csrf import csrf_protect
from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.utils import timezone
import hashlib, secrets

from ..utils import (
    classify_flash,
    set_cookie_safe,
    get_cookie_safe,
    _hash_md5,
    send_school_email
)


# ------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------
def _generate_token(n=40):
    return ''.join(secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(n))


def _now_naive():
    """
    Return current time as naive datetime so it is comparable to DB timestamp without tz.
    """
    now = timezone.now()
    if timezone.is_aware(now):
        return now.replace(tzinfo=None)
    return now


# ========================================================================
# LOGIN
# ========================================================================
@csrf_protect
def login_view(request):
    flash_msg = get_cookie_safe(request, 'flash_msg')
    flash_status = get_cookie_safe(request, 'flash_status')

    flash = None
    if flash_msg and flash_status:
        try:
            status_int = int(flash_status)
        except Exception:
            status_int = 0
        flash = {
            "message": flash_msg,
            "status": status_int,
            "class": classify_flash(flash_status)
        }

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Try using helper, fallback to hashlib.md5
        try:
            hashed = _hash_md5(password)
        except Exception:
            hashed = hashlib.md5(str(password or "").encode()).hexdigest()

        # Query user including is_verified and is_banned
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT A.id, A.email, A.role_id, B.name AS role_name,
                       A.is_verified, A.is_banned
                FROM app_user A
                LEFT JOIN ref_role B ON B.id = A.role_id
                WHERE A.email=%s AND A.hashed_password=%s
                LIMIT 1
            """, [email, hashed])
            row = cursor.fetchone()

        if not row:
            r = redirect('login')
            set_cookie_safe(r, "flash_msg", "Нэвтрэх нэр эсвэл нууц үг буруу", 10)
            set_cookie_safe(r, "flash_status", 400, 10)
            return r

        user_id, email_db, role_id, role_name, is_verified, is_banned = row

        # Баталгаажсан ба хориглогдоогүй
        if is_verified and not is_banned:
            redirect_page = 'admin_dashboard' if (role_name and role_name.lower() == 'admin') else 'teacher_dashboard'
            response = redirect(redirect_page)

            set_cookie_safe(response, "user_id", user_id, 3600*24)
            set_cookie_safe(response, "email", email_db, 3600*24)
            set_cookie_safe(response, "role_id", role_id, 3600*24)
            set_cookie_safe(response, "role_name", (role_name or "").lower(), 3600*24)

            set_cookie_safe(response, "flash_msg", "Амжилттай нэвтэрлээ!", 10)
            set_cookie_safe(response, "flash_status", 200, 10)
            return response

        # Баталгаажсан боловч is_banned == True (админ баталгаажуулалт хийгдээгүй / хязгаарласан)
        if is_verified and is_banned:
            r = redirect('login')
            set_cookie_safe(r, "flash_msg", "Таны нэвтрэл баталгаажаагүй байна. Админ баталгаажуулсны дараа нэвтрэх боломжтой болно.", 10)
            set_cookie_safe(r, "flash_status", 403, 10)
            return r

        # Баталгаажаагүй
        r = redirect('login')
        set_cookie_safe(r, "flash_msg", "Имэйл баталгаажаагүй байна.", 10)
        set_cookie_safe(r, "flash_status", 400, 10)
        return r

    return render(request, "login.html", {"flash": flash})


# ========================================================================
# LOGOUT
# ========================================================================
def logout_view(request):
    response = redirect("login")
    response.delete_cookie("user_id")
    response.delete_cookie("email")
    response.delete_cookie("role_id")
    response.delete_cookie("role_name")
    response.delete_cookie("flash_msg")
    response.delete_cookie("flash_status")
    return response


# ========================================================================
# PASSWORD RESET — REQUEST EMAIL
# ========================================================================
@csrf_protect
def reset_password_request(request):
    if request.method == "POST":
        email = request.POST.get("email")

        # lookup user (танд is_verified=true гэж байгаа — хэрэв хүсвэл энэ шалгалтыг өөрчлөх боломжтой)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id FROM app_user
                WHERE email=%s AND is_verified=true
                LIMIT 1
            """, [email])
            user = cursor.fetchone()

        if not user:
            r = redirect("reset_password_request")
            set_cookie_safe(r, "flash_msg", "Имэйл олдсонгүй.", 5)
            set_cookie_safe(r, "flash_status", 400, 5)
            return r

        user_id = user[0]
        token = _generate_token()
        expires = _now_naive() + timezone.timedelta(minutes=10)

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO app_user_token (user_id, token_type, expires_at, token, created_at)
                VALUES (%s, 'RESET_PASSWORD', %s, %s, now())
            """, [user_id, expires, token])

        reset_url = f"http://localhost:8000/reset/confirm/?token={token}"

        # School email template
        send_school_email(
            to=email,
            subject="Нууц үг сэргээх хүсэлт",
            message="Доорх товч дээр дарж нууц үгээ сэргээнэ үү.",
            button_text="Нууц үг сэргээх",
            button_link=reset_url
        )

        r = redirect("login")
        set_cookie_safe(r, "flash_msg", "Сэргээх линк илгээгдлээ.", 5)
        set_cookie_safe(r, "flash_status", 200, 5)
        return r

    return render(request, "auth/reset_request.html")


# ========================================================================
# PASSWORD RESET — CONFIRM NEW PASSWORD
# ========================================================================
@csrf_protect
def reset_password_confirm(request):
    token = request.GET.get("token") or request.POST.get("token")

    if not token:
        # Токен байхгүй / муу хүсэлт
        r = redirect("login")
        set_cookie_safe(r, "flash_msg", "Токен олдсонгүй эсвэл буруу байна.", 5)
        set_cookie_safe(r, "flash_status", 400, 5)
        return r

    # Токен-г мэдээлэлтэй нь хайна
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, user_id, expires_at, token_type
            FROM app_user_token
            WHERE token=%s AND token_type='RESET_PASSWORD'
            ORDER BY id DESC
            LIMIT 1
        """, [token])
        row = cursor.fetchone()

    if not row:
        # Токен олдоогүй
        r = redirect("login")
        set_cookie_safe(r, "flash_msg", "Токен буруу эсвэл ашиглагдсан байна.", 5)
        set_cookie_safe(r, "flash_status", 400, 5)
        return r

    token_id, user_id, expires, token_type = row

    # Token-ны хугацаа дууссан эсэхийг шалгах
    now_naive = _now_naive()
    if expires is None or expires < now_naive:
        r = redirect("login")
        set_cookie_safe(r, "flash_msg", "Сэргээх токены хугацаа дууссан байна. Давтан хүсэлт илгээнэ үү.", 5)
        set_cookie_safe(r, "flash_status", 400, 5)
        return r

    # POST -> шинэ нууц үг хадгалах
    if request.method == "POST":
        pw = request.POST.get("password")
        pw2 = request.POST.get("confirm_password")  # frontend-д confirm талбар байгаа гэж үзнэ

        # Алдааны мэдээлэл template-д харуулахын тулд dict-д цуглуулна
        context = {"token": token, "errors": []}

        if not pw or not pw2:
            context["errors"].append("Нууц үг болон давтан нууц үг хоёул шаардлагатай.")
            return render(request, "auth/reset_confirm.html", context)

        if pw != pw2:
            context["errors"].append("Нууц үг хоорондоо таарахгүй байна.")
            return render(request, "auth/reset_confirm.html", context)

        # За одоо нууц үгийг шинэчилнэ
        hashed = _hash_md5(pw)
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE app_user SET hashed_password=%s WHERE id=%s
                    """, [hashed, user_id])

                    cursor.execute("""
                        UPDATE app_user_token SET token_type='used' WHERE id=%s
                    """, [token_id])
        except Exception as e:
            # Хэрэв DB алдаа гарвал хэрэглэгчид мэдээлэл харуулна
            context["errors"].append("Серверийн алдаа: " + str(e))
            return render(request, "auth/reset_confirm.html", context)

        # Амжилттай шинэчлэгдлээ — login руу redirect хийж flash харуулах
        r = redirect("login")
        set_cookie_safe(r, "flash_msg", "Нууц үг амжилттай шинэчлэгдлээ. Одоо нэвтэрнэ үү.", 5)
        set_cookie_safe(r, "flash_status", 200, 5)
        return r

    # GET үед: токен хүчинтэй тул хэрэглэгч рүү шинэ нууц үг оруулах хуудас харуулна
    return render(request, "auth/reset_confirm.html", {"token": token})


# ========================================================================
# TEACHER REGISTER
# ========================================================================
@csrf_protect
def teacher_register(request):
    if request.method == "POST":
        email = request.POST.get("email")
        name = request.POST.get("name")
        pw = request.POST.get("password")

        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM app_user WHERE email=%s LIMIT 1", [email])
            if cursor.fetchone():
                return render(request, "auth/register.html", {"error": "Имэйл давхцаж байна."})

        # hashed password
        try:
            hashed = _hash_md5(pw)
        except Exception:
            hashed = hashlib.md5(str(pw or "").encode()).hexdigest()

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    # ref_role-аас 'teacher' id-ийг авна
                    cursor.execute("SELECT id FROM ref_role WHERE name='teacher' LIMIT 1")
                    role_row = cursor.fetchone()
                    if not role_row:
                        raise Exception("role 'teacher' олдсонгүй.")
                    role_id = role_row[0]

                    # Багш бүртгэхдээ is_verified=false, is_banned=true (админ хянаж баталгаажуулна)
                    cursor.execute("""
                        INSERT INTO app_user (email, role_id, is_verified, is_banned, created_at, hashed_password)
                        VALUES (%s, %s, false, true, now(), %s)
                        RETURNING id
                    """, [email, role_id, hashed])
                    user_id = cursor.fetchone()[0]

                    cursor.execute("""
                        INSERT INTO teacher_profile (user_id, name)
                        VALUES (%s, %s)
                    """, [user_id, name])

            r = redirect("login")
            set_cookie_safe(r, "flash_msg", "Амжилттай бүртгэгдлээ. Админ баталгаажуулсны дараа нэвтэрнэ үү.", 10)
            set_cookie_safe(r, "flash_status", 200, 10)
            return r

        except Exception as e:
            return render(request, "auth/register.html", {"error": str(e)})

    return render(request, "auth/register.html")
