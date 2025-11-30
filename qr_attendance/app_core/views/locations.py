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

def _insert_timeslots_for_location(cursor, location_id):
    """
    ref_constant-аас type='timeslot' мөрүүдийг авч time_setting-д оруулах.
    ref_constant columns assumed: id, type, name, value, start_time, end_time
    """
    cursor.execute("""
        INSERT INTO time_setting (location_id, name, value, start_time, end_time)
        SELECT %s, rc.name, rc.value, rc.start_time, rc.end_time
        FROM ref_constant rc
        WHERE rc.type = 'timeslot'
        ORDER BY rc.id
    """, [location_id])

# app_core/views/locations.py - Засварласан (schedule-ээс get_school_timeslots импортлож, timeslots нэмэх)
def get_school_timeslots(location_id=None):
    print("location_id: ")
    print(location_id)
    """Сургуулийн цагийн хуваарь авах, location_id-аар шүүнэ"""
    with connection.cursor() as cursor:
        if location_id is None:
            return []  
        else:
            cursor.execute("""
                SELECT name, value AS slot, start_time, end_time 
                FROM time_setting 
                WHERE location_id = %s 
                ORDER BY start_time
            """, [location_id])
        
        rows = cursor.fetchall()
    
    return [{'name': r[0], 'slot': r[1]} for r in rows]  # start_time, end_time шаардлагатай бол нэм

# app_core/views/locations.py - Засварласан (schedule-ээс get_school_timeslots импортлож, timeslots нэмэх, устгах)

# from ..views.schedule import get_school_timeslots  # schedule.py-с импортлох

# Add
def location_add(request):
    if not _is_admin(request):
        return redirect('login')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_location':
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
                        loc_id = cursor.fetchone()[0]
                response = redirect('location_edit', loc_id)
                set_cookie_safe(response, 'flash_msg', 'Байршил амжилттай нэмэгдлээ.', 6)
                set_cookie_safe(response, 'flash_status', 200, 6)
                return response
            except Exception as e:
                return render(request, 'admin/locations/add.html', {'error': f'Хадгалах үед алдаа: {str(e)}'})

    return render(request, 'admin/locations/add.html')

import re
# Edit
def location_edit(request, loc_id):
    if not _is_admin(request):
        return redirect('login')

    timeslots = get_school_timeslots(loc_id)  # Цагийн жагсаалт авах
    print(timeslots)

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, latitude, longitude, radius_m FROM location WHERE id = %s", [loc_id])
        row = cursor.fetchone()
    if not row:
        response = redirect('locations_list')
        set_cookie_safe(response, 'flash_msg', 'Байршил олдсонгүй.', 6)
        set_cookie_safe(response, 'flash_status', 404, 6)
        return response

    loc = {'id': row[0], 'name': row[1], 'lat': row[2], 'lon': row[3], 'radius_m': row[4]}

    # Одоогийн холбогдсон цагууд авах
    with connection.cursor() as cursor:
        cursor.execute("SELECT value FROM time_setting WHERE location_id = %s", [loc_id])
        selected_timeslots = [r[0] for r in cursor.fetchall()]  # value = slot "08:00-09:30"

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'edit_location':
            name = (request.POST.get('name') or '').strip()
            lat = request.POST.get('latitude')
            lon = request.POST.get('longitude')
            radius = request.POST.get('radius_m') or 100
            new_selected_timeslots = request.POST.getlist('timeslots')  # Шинэ сонгосон

            if not name:
                return render(request, 'admin/locations/edit.html', {'loc': loc, 'error': 'Нэр оруулна уу.', 'timeslots': timeslots, 'selected_timeslots': selected_timeslots})

            try:
                lat_f = float(lat)
                lon_f = float(lon)
                radius_i = int(radius)
            except Exception:
                return render(request, 'admin/locations/edit.html', {'loc': loc, 'error': 'Координат/зай буруу байна.', 'timeslots': timeslots, 'selected_timeslots': selected_timeslots})

            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            UPDATE location
                            SET name = %s, latitude = %s, longitude = %s, radius_m = %s
                            WHERE id = %s
                        """, [name, lat_f, lon_f, radius_i, loc_id])

                        # Одоогийн цагуудыг устгах, шинээр нэмэх
                        cursor.execute("DELETE FROM time_setting WHERE location_id = %s", [loc_id])

                        for slot in new_selected_timeslots:
                            slot_data = next((s for s in timeslots if s['slot'] == slot), None)
                            print(slot_data)
                            if slot_data:
                                cursor.execute("""
                                    INSERT INTO time_setting (location_id, name, value, start_time, end_time)
                                    VALUES (%s, %s, %s, %s, %s)
                                """, [loc_id, slot_data['name'], slot_data['slot'], 
                                      slot_data['slot'].split('-')[0] + ':00', slot_data['slot'].split('-')[1] + ':00'])

                response = redirect('locations_list')
                set_cookie_safe(response, 'flash_msg', 'Байршил шинэчлэгдлээ.', 6)
                set_cookie_safe(response, 'flash_status', 200, 6)
                return response
            except Exception as e:
                return render(request, 'admin/locations/edit.html', {'loc': loc, 'error': f'Шинэчлэхэд алдаа: {str(e)}', 'timeslots': timeslots, 'selected_timeslots': selected_timeslots})

        elif action == 'add_timeslot':
            slot_start = request.POST.get('slot_start')
            slot_end = request.POST.get('slot_end')
            slot_name = request.POST.get('slot_name')
            print(slot_start, slot_end, slot_name)
            if not all([slot_start, slot_end, slot_name]):
                return render(request, 'admin/locations/edit.html', {'loc': loc, 'error': 'Цагийн бүх талбарыг бөглөнө үү', 'timeslots': timeslots, 'selected_timeslots': selected_timeslots})

            try:
                with connection.cursor() as cursor:
                    print("""
                        INSERT INTO time_setting (location_id, name, value, start_time, end_time)
                        VALUES (%s, %s, %s, %s, %s)
                    """, [loc_id, slot_name, f"{slot_start}-{slot_end}", slot_start + ':00', slot_end + ':00'])
                    cursor.execute("""
                        INSERT INTO time_setting (location_id, name, value, start_time, end_time)
                        VALUES (%s, %s, %s, %s, %s)
                    """, [loc_id, slot_name, f"{slot_start}-{slot_end}", slot_start + ':00', slot_end + ':00'])

                response = redirect('location_edit', loc_id=loc_id)
                set_cookie_safe(response, 'flash_msg', 'Шинэ цаг нэмэгдлээ.', 6)
                set_cookie_safe(response, 'flash_status', 200, 6)
                return response
            except Exception as e:
                return render(request, 'admin/locations/edit.html', {'loc': loc, 'error': f'Цаг нэмэхэд алдаа: {str(e)}', 'timeslots': timeslots, 'selected_timeslots': selected_timeslots})

        elif action == 'delete_timeslot':
            slot_value = request.POST.get('slot_value')
            if slot_value:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM time_setting WHERE value = %s", [slot_value])

                    response = redirect('location_edit', loc_id=loc_id)
                    set_cookie_safe(response, 'flash_msg', 'Цаг устгагдлаа.', 6)
                    set_cookie_safe(response, 'flash_status', 200, 6)
                    return response
                except Exception as e:
                    return render(request, 'admin/locations/edit.html', {'loc': loc, 'error': f'Устгахад алдаа: {str(e)}', 'timeslots': timeslots, 'selected_timeslots': selected_timeslots})

    return render(request, 'admin/locations/edit.html', {'loc': loc, 'timeslots': timeslots, 'selected_timeslots': selected_timeslots})

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
