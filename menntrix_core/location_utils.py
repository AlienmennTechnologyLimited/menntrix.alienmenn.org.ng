import requests
from django.conf import settings

IPAPI_TIMEOUT = 3  # seconds


def get_client_ip(request):
    """Return the client IP from a Django request."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def lookup_ip(ip):
    """Look up city/region/country/ISP for an IP. Returns dict (may be empty)."""
    if not ip:
        return {}
    if ip.startswith(("127.", "10.", "192.168.", "172.16.", "172.17.",
                      "172.18.", "172.19.", "172.2", "172.30.", "172.31.")):
        return {"city": "Local", "region": "Local", "country": "Local", "isp": "Local"}
    try:
        r = requests.get(
            f"https://ipapi.co/{ip}/json/",
            timeout=IPAPI_TIMEOUT,
            headers={"User-Agent": "MENNTRIX/1.0"},
        )
        if r.status_code == 200:
            data = r.json()
            return {
                "city": data.get("city") or "",
                "region": data.get("region") or "",
                "country": data.get("country_name") or "",
                "isp": data.get("org") or "",
            }
    except Exception:
        pass
    return {}