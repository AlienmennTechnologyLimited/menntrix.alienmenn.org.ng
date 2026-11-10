from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages as flash
from django.conf import settings
from django.db.models import Q
from django.http import HttpResponseForbidden
from .models import UserAccount, Country


# ============================================================
# HELPERS
# ============================================================

def _require_admin(request):
    u = request.user
    return u.is_authenticated and getattr(u, "is_menntrix_admin", False)


# ============================================================
# PUBLIC PAGES
# ============================================================

def splash(request):
    return render(request, "menntrix/index.html")


def home(request):
    return render(request, "menntrix/home.html")


def signin_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            request.session[settings.MENNTRIX_SESSION_USER_KEY] = user.username

            try:
                from menntrix_core.notifications import log_activity
                log_activity(user, "login", "session", "", "Signed in", request)
            except Exception:
                pass

            return redirect("dashboard")
        return render(
            request,
            "menntrix/signin.html",
            {"error_message": "Invalid credentials"},
        )
    return render(request, "menntrix/signin.html")


def signup_view(request):
    countries = Country.objects.all()

    if request.method == "POST":
        email = request.POST.get("email")
        username = request.POST.get("username")
        password = request.POST.get("password")
        confirm = request.POST.get("confirmpassword")

        if password != confirm:
            return render(request, "menntrix/signup.html",
                          {"error_message": "Passwords do not match", "countries": countries})

        if UserAccount.objects.filter(email=email).exists():
            return render(request, "menntrix/signup.html",
                          {"error_message": "Email already registered", "countries": countries})

        if UserAccount.objects.filter(username=username).exists():
            return render(request, "menntrix/signup.html",
                          {"error_message": "Username taken", "countries": countries})

        user = UserAccount(
            email=email,
            username=username,
            firstname=request.POST.get("firstname"),
            lastname=request.POST.get("lastname"),
            gender=request.POST.get("gender"),
            dob=request.POST.get("dob"),
            country=request.POST.get("country"),
            country_code=request.POST.get("country_code"),
            mobile=request.POST.get("mobile"),
            currency=request.POST.get("currency", "NGN"),
        )
        user.set_password(password)
        user.save()

        login(request, user)
        request.session[settings.MENNTRIX_SESSION_USER_KEY] = user.username

        try:
            from menntrix_core.notifications import log_activity, send_email
            log_activity(user, "signup", "user", user.id, "Created account", request)
            send_email(
                subject="Welcome to MENNTRIX",
                to_email=user.email,
                template="emails/welcome.html",
                context={"user": user},
            )
        except Exception:
            pass

        return redirect("dashboard")

    return render(request, "menntrix/signup.html", {"countries": countries})


def logout_view(request):
    if request.user.is_authenticated:
        try:
            from menntrix_core.notifications import log_activity
            log_activity(request.user, "logout", "session", "", "Signed out", request)
        except Exception:
            pass

    logout(request)
    request.session.flush()
    return redirect("signin")


# ============================================================
# ADMIN — USER MANAGEMENT
# ============================================================

@login_required
def admin_users(request):
    if not _require_admin(request):
        return HttpResponseForbidden("You do not have permission to manage users.")

    q = (request.GET.get("q") or "").strip()

    qs = UserAccount.objects.all().order_by("username")
    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(firstname__icontains=q)
            | Q(lastname__icontains=q)
        )

    qs = qs[:500]
    admin_names = set(UserAccount.ADMIN_USERNAMES)

    return render(request, "menntrix/admin_users.html", {
        "users": qs,
        "admin_names": admin_names,
        "q": q,
    })


@login_required
def admin_user_edit(request, user_id):
    if not _require_admin(request):
        return HttpResponseForbidden("You do not have permission to edit users.")

    target = get_object_or_404(UserAccount, id=user_id)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "make_admin":
            if not target.username:
                flash.error(request, "This user has no username and cannot be made admin.")
            else:
                UserAccount.ADMIN_USERNAMES.add(target.username)
                flash.success(request, f"{target.username} is now an admin.")
            return redirect("admin_user_edit", user_id=target.id)

        if action == "remove_admin":
            if target.id == request.user.id:
                flash.error(request, "You cannot remove your own admin access.")
            elif target.username in UserAccount.ADMIN_USERNAMES:
                UserAccount.ADMIN_USERNAMES.discard(target.username)
                flash.success(request, f"{target.username} is no longer an admin.")
            return redirect("admin_user_edit", user_id=target.id)

        if action == "toggle_active":
            if target.id == request.user.id:
                flash.error(request, "You cannot deactivate your own account.")
            else:
                is_inactive = (target.status or "").lower() == "inactive"
                target.status = "active" if is_inactive else "inactive"
                target.save(update_fields=["status"])
                flash.success(request, f"{target.username} is now {target.status}.")
            return redirect("admin_user_edit", user_id=target.id)

        if action == "save_profile":
            target.firstname = request.POST.get("firstname") or target.firstname
            target.lastname = request.POST.get("lastname") or target.lastname
            target.email = request.POST.get("email") or target.email
            target.mobile = request.POST.get("mobile") or target.mobile
            target.country = request.POST.get("country") or target.country
            target.save(update_fields=["firstname", "lastname", "email", "mobile", "country"])
            flash.success(request, "Profile updated.")
            return redirect("admin_user_edit", user_id=target.id)

        if action == "reset_password":
            new_pass = (request.POST.get("new_password") or "").strip()
            if len(new_pass) < 8:
                flash.error(request, "Password must be at least 8 characters.")
            else:
                target.set_password(new_pass)
                target.save()
                flash.success(request, f"Password reset for {target.username}.")
            return redirect("admin_user_edit", user_id=target.id)

    return render(request, "menntrix/admin_user_edit.html", {
        "target": target,
        "is_admin": target.username in UserAccount.ADMIN_USERNAMES,
    })