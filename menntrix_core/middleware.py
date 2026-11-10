from django.conf import settings


class MenntrixSessionMiddleware:
    """Ensure MM_Username is present in the session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        key = getattr(settings, "MENNTRIX_SESSION_USER_KEY", "MM_Username")
        if request.user.is_authenticated and key not in request.session:
            request.session[key] = request.user.username
        return self.get_response(request)
