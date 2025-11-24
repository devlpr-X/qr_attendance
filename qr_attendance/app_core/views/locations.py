# app_core/views/locations.py
from django.shortcuts import render, redirect
from django.db import connection, transaction
from ..utils import _is_admin, set_cookie_safe, get_cookie_safe

# List
def locations_list(request):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, latitude, longitude, radius_m FROM location ORDER BY id DESC")
        rows = cursor.fetchall()

    locations = [{'id': r[0], 'name': r[1], 'lat': r[2], 'lon': r[3], 'radius_m': r[4]} for r in rows]
    return render(request, 'admin/locations/list.html', {'locations': locations})

# View single
def location_view(request, loc_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, latitude, longitude, radius_m FROM location WHERE id = %s", [loc_id])
        row = cursor.fetchone()
    if not row:
        response = redirect('locations_list')
        set_cookie_safe(response, 'flash_msg', 'Байршил олдсонгүй', 6)
        set_cookie_safe(response, 'flash_status', 404, 6)
        return response

    loc = {'id': row[0], 'name': row[1], 'lat': row[2], 'lon': row[3], 'radius_m': row[4]}
    return render(request, 'admin/locations/view.html', {'loc': loc})

# Add
def location_add(request):
    if not _is_admin(request):
        return redirect('login')

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        lat = request.POST.get('latitude')
        lon = request.POST.get('longitude')
        radius = request.POST.get('radius_m') or 100

        # validation
        if not name:
            return render(request, 'admin/locations/add.html', {'error': 'Байршлын нэр оруулна уу.'})
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            radius_i = int(radius)
        except Exception:
            return render(request, 'admin/locations/add.html', {'error': 'Өгөгдсөн координат/зай буруу байна.'})

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO location (name, latitude, longitude, radius_m)
                        VALUES (%s, %s, %s, %s) RETURNING id
                    """, [name, lat_f, lon_f, radius_i])
                    new_id = cursor.fetchone()[0]

            response = redirect('locations_list')
            set_cookie_safe(response, 'flash_msg', 'Байршил амжилттай нэмэгдлээ.', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response
        except Exception as e:
            return render(request, 'admin/locations/add.html', {'error': f'Хадгалах үед алдаа: {str(e)}'})

    # GET
    return render(request, 'admin/locations/add.html')

# Edit
def location_edit(request, loc_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, latitude, longitude, radius_m FROM location WHERE id = %s", [loc_id])
        row = cursor.fetchone()
    if not row:
        response = redirect('locations_list')
        set_cookie_safe(response, 'flash_msg', 'Байршил олдсонгүй.', 6)
        set_cookie_safe(response, 'flash_status', 404, 6)
        return response

    loc = {'id': row[0], 'name': row[1], 'lat': row[2], 'lon': row[3], 'radius_m': row[4]}
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        lat = request.POST.get('latitude')
        lon = request.POST.get('longitude')
        radius = request.POST.get('radius_m') or 100

        if not name:
            return render(request, 'admin/locations/edit.html', {'loc': loc, 'error': 'Нэр оруулна уу.'})

        try:
            lat_f = float(lat)
            lon_f = float(lon)
            radius_i = int(radius)
        except Exception:
            return render(request, 'admin/locations/edit.html', {'loc': loc, 'error': 'Координат/зай буруу байна.'})

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE location
                        SET name = %s, latitude = %s, longitude = %s, radius_m = %s
                        WHERE id = %s
                    """, [name, lat_f, lon_f, radius_i, loc_id])
            response = redirect('locations_list')
            set_cookie_safe(response, 'flash_msg', 'Байршил шинэчлэгдлээ.', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response
        except Exception as e:
            return render(request, 'admin/locations/edit.html', {'loc': loc, 'error': f'Шинэчлэхэд алдаа: {str(e)}'})

    return render(request, 'admin/locations/edit.html', {'loc': loc})

# Delete
def location_delete(request, loc_id):
    if not _is_admin(request):
        return redirect('login')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM location WHERE id = %s", [loc_id])
        row = cursor.fetchone()
    if not row:
        response = redirect('locations_list')
        set_cookie_safe(response, 'flash_msg', 'Байршил олдсонгүй.', 6)
        set_cookie_safe(response, 'flash_status', 404, 6)
        return response

    if request.method == 'POST':
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM location WHERE id = %s", [loc_id])
            response = redirect('locations_list')
            set_cookie_safe(response, 'flash_msg', 'Байршил амжилттай устлаа.', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response
        except Exception as e:
            response = redirect('locations_list')
            set_cookie_safe(response, 'flash_msg', f'Устгах үед алдаа: {str(e)}', 6)
            set_cookie_safe(response, 'flash_status', 500, 6)
            return response

    return render(request, 'admin/locations/delete_confirm.html', {'loc': {'id': row[0], 'name': row[1]}})
