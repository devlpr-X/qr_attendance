from django.db import connection

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
