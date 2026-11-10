from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Group",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="menntrix_groups_owned", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "menntrix_group"},
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject", models.CharField(blank=True, default="", max_length=255)),
                ("body", models.TextField(blank=True, default="")),
                ("folder", models.CharField(choices=[("inbox", "Inbox"), ("sent", "Sent"), ("drafts", "Drafts"), ("trash", "Trash"), ("starred", "Starred")], default="inbox", max_length=20)),
                ("is_read", models.BooleanField(default=False)),
                ("is_starred", models.BooleanField(default=False)),
                ("is_deleted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messages", to="menntrix_messaging.group")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="replies", to="menntrix_messaging.message")),
                ("recipient", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="menntrix_messages_received", to=settings.AUTH_USER_MODEL)),
                ("sender", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="menntrix_messages_sent", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "menntrix_message"},
        ),
        migrations.CreateModel(
            name="GroupMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="members", to="menntrix_messaging.group")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="menntrix_groups_joined", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "menntrix_group_member", "unique_together": {("group", "user")}},
        ),
        migrations.CreateModel(
            name="MessageRecipient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="extra_recipients", to="menntrix_messaging.message")),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="menntrix_messages_cc", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "menntrix_message_recipient", "unique_together": {("message", "recipient")}},
        ),
        migrations.AddIndex(
            model_name="message",
            index=models.Index(fields=["recipient", "folder", "created_at"], name="menntrix_me_recipie_a1c1a1_idx"),
        ),
        migrations.AddIndex(
            model_name="message",
            index=models.Index(fields=["sender", "folder", "created_at"], name="menntrix_me_sender__a2c2b2_idx"),
        ),
    ]