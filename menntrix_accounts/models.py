import os
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class UserAccountManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra):
        if not email:
            raise ValueError("Email required")
        user = self.model(email=email, username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra):
        return self.create_user(email, username, password, **extra)


class UserAccount(AbstractBaseUser):
    id = models.AutoField(primary_key=True)
    firstname = models.TextField(blank=True, null=True)
    lastname = models.TextField(blank=True, null=True)
    middlename = models.TextField(blank=True, null=True)
    email = models.TextField(unique=True)
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=128)

    profile_name_menntrix = models.TextField(blank=True, null=True)
    profile_picture_menntrix = models.CharField(max_length=2500, blank=True, null=True)
    mobile_no_menntrix = models.TextField(blank=True, null=True)
    mobile_code_menntrix = models.CharField(max_length=250, blank=True, null=True)
    status_profile_name_menntrix = models.TextField(blank=True, null=True)
    status_profile_picture_menntrix = models.TextField(blank=True, null=True)

    gender = models.TextField(blank=True, null=True)
    dob = models.TextField(blank=True, null=True)
    mobile = models.TextField(blank=True, null=True)
    address = models.CharField(max_length=200, blank=True, null=True)
    nearest = models.CharField(max_length=200, blank=True, null=True)
    state = models.CharField(max_length=200, blank=True, null=True)
    community = models.CharField(max_length=100, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    country_code = models.CharField(max_length=50, blank=True, null=True)
    planet = models.CharField(max_length=100, blank=True, null=True)
    currency = models.CharField(max_length=100, blank=True, null=True)

    bank_name = models.CharField(max_length=100, blank=True, null=True)
    bank_acc_name = models.CharField(max_length=100, blank=True, null=True)
    bank_acc_no = models.CharField(max_length=100, blank=True, null=True)
    bank_acc_type = models.CharField(max_length=100, blank=True, null=True)

    status = models.CharField(max_length=100, blank=True, null=True)

    # ============================================================
    # ADMIN ROLE
    # Add or remove usernames here to grant/revoke admin access.
    # ============================================================
    ADMIN_USERNAMES = {"Jehovah", "menntrix_admin"}

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserAccountManager()

    class Meta:
        managed = os.getenv("MENNTRIX_DEV_MANAGED_USER", "False") == "True"
        db_table = "useraccount"

    def __str__(self):
        return self.username or self.email

    @property
    def is_menntrix_admin(self):
        return (self.username or "") in self.ADMIN_USERNAMES

    @property
    def is_staff(self):
        return self.is_menntrix_admin

    @property
    def is_superuser(self):
        return self.is_menntrix_admin

    @property
    def is_active(self):
        return (self.status or "").lower() != "inactive"

    def has_perm(self, perm, obj=None):
        return self.is_menntrix_admin

    def has_module_perms(self, app_label):
        return self.is_menntrix_admin


class Country(models.Model):
    country_id = models.AutoField(primary_key=True)
    country_name = models.CharField(max_length=100, blank=True, null=True)
    country_code = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "country"
        ordering = ["country_name"]

    def __str__(self):
        return self.country_name or f"Country #{self.country_id}"