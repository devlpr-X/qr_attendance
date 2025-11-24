from django.shortcuts import render
from ..utils import classify_flash

# mock data туршилтаар
USERS = [
    {'email': 'admin@example.com', 'name': 'Админ', 'role': 'Admin', 'is_verified': True},
    {'email': 'teacher@example.com', 'name': 'Багш', 'role': 'Teacher', 'is_verified': True},
    {'email': 'student@example.com', 'name': 'Сурагч', 'role': 'Student', 'is_verified': False},
]

def users_list(request):
    return render(request, 'admin/dashboard.html', {'users': USERS})


# from django.shortcuts import render, redirect
# from app_core.helpers import query

# def index(request):
#     return render(request, "dashboard.html")


# def list_users(request):
#     page = int(request.GET.get("page", 1))
#     limit = 10
#     start = (page - 1) * limit

#     total = query(
#         "SELECT COUNT(*) FROM app_user",
#         fetchone=True
#     )[0]

#     users = query(f"""
#         SELECT u.id, u.email, r.name, u.is_verified, u.is_banned, u.created_at
#         FROM app_user u
#         JOIN ref_role r ON r.id = u.role_id
#         ORDER BY u.created_at DESC
#         LIMIT {limit} OFFSET {start}
#     """, fetchall=True)

#     return render(request, "users.html", {
#         "users": users,
#         "page": page,
#         "pages": range(1, (total // limit) + 2)
#     })


# def delete_user(request, user_id):
#     query("""
#         UPDATE app_user SET is_banned = TRUE WHERE id = %s
#     """, [user_id], commit=True)

#     return redirect("list_users")
