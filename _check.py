from django.db import connection

with connection.cursor() as c:
    c.execute("SHOW TABLES LIKE 'menntrix%timeline%'")
    print("TABLES:", c.fetchall())

from menntrix_core.models import TimelinePost
print("DB_TABLE:", TimelinePost._meta.db_table)
print("ROWS:", TimelinePost.objects.count())
