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