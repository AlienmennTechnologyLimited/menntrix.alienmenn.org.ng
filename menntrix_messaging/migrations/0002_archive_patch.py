from django.db import migrations
from django.db import connection


def apply_archive_patch(apps, schema_editor):
    # Skip on SQLite (dev) — archive table only exists in MySQL
    if connection.vendor != "mysql":
        return
    with connection.cursor() as cursor:
        cursor.execute("""
            ALTER TABLE `archive`
                ADD COLUMN `menntrix_context_type` VARCHAR(50) NULL,
                ADD COLUMN `menntrix_context_id` VARCHAR(64) NULL,
                ADD COLUMN `menntrix_recipient_id` VARCHAR(100) NULL,
                ADD COLUMN `menntrix_group_id` VARCHAR(64) NULL,
                ADD COLUMN `menntrix_duration_sec` INT NULL,
                ADD COLUMN `menntrix_mime_type` VARCHAR(100) NULL,
                ADD COLUMN `menntrix_file_size_bytes` BIGINT NULL,
                ADD INDEX `idx_menntrix_context` (`menntrix_context_type`, `menntrix_context_id`),
                ADD INDEX `idx_menntrix_recipient` (`menntrix_recipient_id`);
        """)


def reverse_archive_patch(apps, schema_editor):
    if connection.vendor != "mysql":
        return
    with connection.cursor() as cursor:
        cursor.execute("""
            ALTER TABLE `archive`
                DROP INDEX `idx_menntrix_context`,
                DROP INDEX `idx_menntrix_recipient`,
                DROP COLUMN `menntrix_context_type`,
                DROP COLUMN `menntrix_context_id`,
                DROP COLUMN `menntrix_recipient_id`,
                DROP COLUMN `menntrix_group_id`,
                DROP COLUMN `menntrix_duration_sec`,
                DROP COLUMN `menntrix_mime_type`,
                DROP COLUMN `menntrix_file_size_bytes`;
        """)


class Migration(migrations.Migration):
    dependencies = [
        ("menntrix_messaging", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(apply_archive_patch, reverse_archive_patch),
    ]