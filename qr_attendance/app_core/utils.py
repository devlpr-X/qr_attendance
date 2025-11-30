# utils.py
from django.db import connection
import urllib.parse
import hashlib
import secrets

def classify_flash(status):
    try:
        code = int(status)
        if 200 <= code <= 299:
            return "success"
        elif 300 <= code <= 399:
            return "warning"
        else:
            return "error"
    except:
        return "error"

def set_cookie_safe(response, key, value, max_age=None):
    encoded = urllib.parse.quote(str(value))
    response.set_cookie(key, encoded, max_age=max_age)


def get_cookie_safe(request, key, default=None):
    raw = request.COOKIES.get(key)
    return urllib.parse.unquote(raw) if raw else default

def _is_admin(request):
    role = request.COOKIES.get('role_name', '')
    return role.lower() == 'admin'

def _generate_password(length=10):
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def _hash_md5(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()

def _get_constants(kind):
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, value FROM ref_constant WHERE type = %s ORDER BY id", [kind])
        return cursor.fetchall()
    
def query(sql, params=None, fetchone=False, fetchall=False, commit=False):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])

        if commit:
            return True
        if fetchone:
            return cursor.fetchone()
        if fetchall:
            return cursor.fetchall()

    return None
# app_core/utils_email.py

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


SCHOOL_EMAIL = "starodic@gmail.com"
SCHOOL_PASSWORD = "mevw hlex yhvd bsbd"  


def send_school_email(to, subject, message, button_text=None, button_link=None):
    msg = MIMEMultipart("alternative")
    msg["From"] = f"QR Attendance System <{SCHOOL_EMAIL}>"
    msg["To"] = to
    msg["Subject"] = subject

    html = f"""
    <html>
    <body style="font-family:Arial; background:#f5f6f7; padding:20px;">
        <div style="max-width:500px; margin:auto; background:white; padding:25px;
                    border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
            
            <h2 style="color:#1d5ede; text-align:center; margin-bottom:20px;">
                {subject}
            </h2>

            <p style="font-size:15px; color:#333; line-height:1.6;">
                {message}
            </p>
    """

    if button_link and button_text:
        html += f"""
            <div style="text-align:center; margin-top:25px;">
                <a href="{button_link}"
                   style="background:#1d5ede; padding:12px 25px; color:white;
                          text-decoration:none; border-radius:5px; font-weight:bold;">
                   {button_text}
                </a>
            </div>
        """

    html += """
            <p style="font-size:12px; color:#777; margin-top:30px; text-align:center;">
                © 2025 School Attendance System. Бүх эрх хуулиар хамгаалагдсан.
            </p>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SCHOOL_EMAIL, SCHOOL_PASSWORD)
            server.sendmail(SCHOOL_EMAIL, to, msg.as_string())
    except Exception as e:
        print("EMAIL ERROR:", e)
