from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone

from app_core.utils import _is_admin, set_cookie_safe

import json


def _get_schools():
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM location ORDER BY name")
        rows = cursor.fetchall()
    return [{"id": r[0], "name": r[1]} for r in rows]


def _get_programs():
    """
    Return programs plus the school_id (via department) so frontend can filter by school.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT p.id, p.name, p.code, d.school_id
            FROM program p
            JOIN department d ON p.department_id = d.id
            ORDER BY p.code, p.name
        """)
        rows = cursor.fetchall()
    return [
        {"id": r[0], "name": r[1], "code": r[2] or "", "school_id": r[3]}
        for r in rows
    ]


def _get_semesters():
    """
    Бүх semester Мөрүүдийг авах (school_id-тай). Frontend-д дамжуулна.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, school_id, school_year, term, name, start_date, end_date, is_active, created_at
            FROM semester
            ORDER BY school_id, school_year DESC, term DESC
        """)
        rows = cursor.fetchall()

    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "school_id": r[1],
            "school_year": r[2],
            "term": r[3],
            "name": r[4],
            "start_date": str(r[5]) if r[5] else "",
            "end_date": str(r[6]) if r[6] else "",
            "is_active": r[7],
            "created_at": str(r[8]) if r[8] else ""
        })
    return items


def _detect_year_column():
    """
    class_group дээр жил хадгалах баганы нэрийг олно.
    Priority: school_year, schoolyear, semester_id, semester, year
    Буцах: баганын нэр (string) эсвэл None
    """
    candidates = ['school_year', 'schoolyear', 'semester_id', 'semester', 'year']
    with connection.cursor() as cursor:
        for col in candidates:
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_name = 'class_group' AND column_name = %s
            """, [col])
            if cursor.fetchone()[0] > 0:
                return col
    return None


def _get_class_groups():
    """
    Үндсэн хүснэгтээс анги бүлгүүдийг авна.
    Хэрэв class_group-д жил хадгалах багана байдаг бол тэрийг ашиглана.
    Semester хүснэгттэй зөвхөн тухайн онтой холбогдсон хамгийн сүүлийн (term өндөр) semester.name-г LEFT JOIN LATERAL-аар авна.
    """

    year_col = _detect_year_column()

    if year_col:
        # dynamic select: include the year column
        # LEFT JOIN LATERAL to get semester name matching school+year (latest term)
        with connection.cursor() as cursor:
            sql = f"""
                SELECT
                    cg.id,
                    cg.school_id,
                    l.name AS school_name,
                    cg.program_id,
                    p.name AS program_name,
                    p.code AS program_code,
                    cg.year_level,
                    cg.group_number,
                    cg.name,
                    cg.{year_col} AS class_school_year,
                    sem_lookup.semester_name,
                    sem_lookup.semester_id,
                    cg.created_at
                FROM class_group cg
                JOIN location l ON cg.school_id = l.id
                JOIN program p ON cg.program_id = p.id
                LEFT JOIN LATERAL (
                    SELECT s.id AS semester_id, s.name AS semester_name
                    FROM semester s
                    WHERE s.school_id = cg.school_id
                      AND s.school_year = cg.{year_col}
                    ORDER BY s.term DESC
                    LIMIT 1
                ) sem_lookup ON TRUE
                ORDER BY l.name, cg.year_level, p.code, cg.group_number NULLS LAST, cg.id
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
    else:
        # no year column on class_group: return without year info
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    cg.id,
                    cg.school_id,
                    l.name AS school_name,
                    cg.program_id,
                    p.name AS program_name,
                    p.code AS program_code,
                    cg.year_level,
                    cg.group_number,
                    cg.name,
                    NULL AS class_school_year,
                    NULL AS semester_name,
                    NULL AS semester_id,
                    cg.created_at
                FROM class_group cg
                JOIN location l ON cg.school_id = l.id
                JOIN program p ON cg.program_id = p.id
                ORDER BY l.name, cg.year_level, p.code, cg.group_number NULLS LAST, cg.id
            """)
            rows = cursor.fetchall()

    items = []
    for r in rows:
        created = r[12]
        created_str = created.strftime("%Y-%m-%d %H:%M:%S") if created else ""
        items.append({
            "id": r[0],
            "school_id": r[1],
            "school_name": r[2],
            "program_id": r[3],
            "program_name": r[4],
            "program_code": r[5] or "",
            "year_level": r[6],
            "group_number": r[7],
            "name": r[8],
            # canonical: class_school_year (numeric) and semester_name (text from semester table)
            "school_year": r[9],
            "semester_name": r[10] or "",
            "semester_ref_id": r[11],  # may be null
            "created_at": created_str
        })
    return items


@csrf_protect
def class_group_manage(request):
    if not _is_admin(request):
        return redirect("login")

    error = None

    # resolve which column to write the school_year into (if any)
    year_col = _detect_year_column()

    if request.method == "POST":
        action = request.POST.get("action")

        # We accept POST field named "school_year" from forms.
        posted_year = request.POST.get("school_year")  # may be '' or None
        # normalize to integer or None
        try:
            posted_year_val = int(posted_year) if posted_year not in (None, "") else None
        except Exception:
            posted_year_val = None

        if action == "add":
            school_id = request.POST.get("school_id")
            program_id = request.POST.get("program_id")
            year_level = request.POST.get("year_level")
            group_number = request.POST.get("group_number") or None
            name = request.POST.get("name", "").strip()

            if not school_id or not program_id or not year_level or not name:
                error = "Сургууль, хөтөлбөр, курс, анги нэр заавал шаардлагатай."
            else:
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            if year_col:
                                # include dynamic column for school_year
                                sql = f"""
                                    INSERT INTO class_group
                                    (school_id, program_id, {year_col}, year_level, group_number, name, created_at)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """
                                params = [school_id, program_id, posted_year_val, year_level, group_number, name, timezone.now()]
                                cursor.execute(sql, params)
                            else:
                                # no year column available: insert without it
                                cursor.execute("""
                                    INSERT INTO class_group
                                    (school_id, program_id, year_level, group_number, name, created_at)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, [school_id, program_id, year_level, group_number, name, timezone.now()])

                    resp = redirect("class_group_manage")
                    set_cookie_safe(resp, "flash_msg", "Анги бүлэг амжилттай нэмэгдлээ", 5)
                    set_cookie_safe(resp, "flash_status", 200, 5)
                    return resp
                except Exception as e:
                    error = f"Нэмэх үед алдаа гарлаа: {e}"

        elif action == "edit":
            _id = request.POST.get("id")
            school_id = request.POST.get("school_id")
            program_id = request.POST.get("program_id")
            year_level = request.POST.get("year_level")
            group_number = request.POST.get("group_number") or None
            name = request.POST.get("name", "").strip()

            if not _id or not school_id or not program_id or not year_level or not name:
                error = "Бүх талбарыг бөглөнө үү."
            else:
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            if year_col:
                                sql = f"""
                                    UPDATE class_group
                                    SET school_id = %s,
                                        program_id = %s,
                                        {year_col} = %s,
                                        year_level = %s,
                                        group_number = %s,
                                        name = %s
                                    WHERE id = %s
                                """
                                params = [school_id, program_id, posted_year_val, year_level, group_number, name, _id]
                                cursor.execute(sql, params)
                            else:
                                cursor.execute("""
                                    UPDATE class_group
                                    SET school_id = %s,
                                        program_id = %s,
                                        year_level = %s,
                                        group_number = %s,
                                        name = %s
                                    WHERE id = %s
                                """, [school_id, program_id, year_level, group_number, name, _id])

                    resp = redirect("class_group_manage")
                    set_cookie_safe(resp, "flash_msg", "Анги бүлэг шинэчлэгдлээ", 5)
                    set_cookie_safe(resp, "flash_status", 200, 5)
                    return resp
                except Exception as e:
                    error = f"Шинэчлэхэд алдаа гарлаа: {e}"

        elif action == "delete":
            _id = request.POST.get("id")
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM student_class_group WHERE class_group_id = %s", [_id])
                        cursor.execute("DELETE FROM class_group WHERE id = %s", [_id])

                resp = redirect("class_group_manage")
                set_cookie_safe(resp, "flash_msg", "Анги бүлэг устгагдлаа", 5)
                set_cookie_safe(resp, "flash_status", 200, 5)
                return resp
            except Exception as e:
                error = f"Устгахад алдаа гарлаа: {e}"

    # GET
    schools = _get_schools()
    programs = _get_programs()
    semesters = _get_semesters()  # used to derive available school_years
    items = _get_class_groups()

    return render(request, "admin/look_up/class_group_manage.html", {
        "error": error,
        "schools": schools,
        "schools_json": json.dumps(schools, ensure_ascii=False),
        "programs_json": json.dumps(programs, ensure_ascii=False),
        "semesters_json": json.dumps(semesters, ensure_ascii=False),
        "items": json.dumps(items, ensure_ascii=False),
    })
