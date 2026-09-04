# Caddy tls internal is not in certifi. Adventure Log's OIDC client is
# requests (django-allauth discovery). Homelab skip, same idea as Transmute.
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

try:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

try:
    import requests

    _orig = requests.Session.request

    def _request(self, method, url, **kwargs):
        kwargs["verify"] = False
        return _orig(self, method, url, **kwargs)

    requests.Session.request = _request
except Exception:
    pass
