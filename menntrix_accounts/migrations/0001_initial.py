from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserAccount",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("firstname", models.TextField(blank=True, null=True)),
                ("lastname", models.TextField(blank=True, null=True)),
                ("middlename", models.TextField(blank=True, null=True)),
                ("email", models.TextField(unique=True)),
                ("username", models.CharField(max_length=100, unique=True)),
                ("password", models.CharField(max_length=128)),
                ("profile_name_menntrix", models.TextField(blank=True, null=True)),
                ("profile_picture_menntrix", models.CharField(blank=True, max_length=2500, null=True)),
                ("mobile_no_menntrix", models.TextField(blank=True, null=True)),
                ("mobile_code_menntrix", models.CharField(blank=True, max_length=250, null=True)),
                ("status_profile_name_menntrix", models.TextField(blank=True, null=True)),
                ("status_profile_picture_menntrix", models.TextField(blank=True, null=True)),
                ("gender", models.TextField(blank=True, null=True)),
                ("dob", models.TextField(blank=True, null=True)),
                ("mobile", models.TextField(blank=True, null=True)),
                ("address", models.CharField(blank=True, max_length=200, null=True)),
                ("nearest", models.CharField(blank=True, max_length=200, null=True)),
                ("state", models.CharField(blank=True, max_length=200, null=True)),
                ("community", models.CharField(blank=True, max_length=100, null=True)),
                ("region", models.CharField(blank=True, max_length=100, null=True)),
                ("country", models.CharField(blank=True, max_length=100, null=True)),
                ("country_code", models.CharField(blank=True, max_length=50, null=True)),
                ("planet", models.CharField(blank=True, max_length=100, null=True)),
                ("currency", models.CharField(blank=True, max_length=100, null=True)),
                ("bank_name", models.CharField(blank=True, max_length=100, null=True)),
                ("bank_acc_name", models.CharField(blank=True, max_length=100, null=True)),
                ("bank_acc_no", models.CharField(blank=True, max_length=100, null=True)),
                ("bank_acc_type", models.CharField(blank=True, max_length=100, null=True)),
                ("status", models.CharField(blank=True, max_length=100, null=True)),
                
    
            ],
            options={
                "db_table": "useraccount",
                "managed": False,
            },
        ),
    ]