# Caddy tls internal is not in certifi. Adventure Log's OIDC client is
# requests (django-allauth discovery). Homelab skip, same idea as Transmute.
#
# Also: get_sld("travel.home.lan") can yield a cookie Domain browsers reject
# (see AdventureLog #467 / #1119). Force host-only session cookies.
import ssl
import traceback

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
        resp = _orig(self, method, url, **kwargs)
        if isinstance(url, str) and "auth." in url and "/.well-known/" not in url:
            print(
                f"adventurelog-oidc: {method} {url} -> {resp.status_code} {resp.text[:300]!r}",
                flush=True,
            )
        return resp

    requests.Session.request = _request
except Exception:
    pass

try:
    from django.conf import LazySettings

    _orig_setup = LazySettings._setup

    def _setup(self, default_settings=None):
        _orig_setup(self, default_settings)
        self._wrapped.SESSION_COOKIE_DOMAIN = None
        self._wrapped.CSRF_COOKIE_DOMAIN = None
        print("adventurelog-oidc: SESSION_COOKIE_DOMAIN=None (host-only)", flush=True)

    LazySettings._setup = _setup
except Exception as exc:
    print("adventurelog-oidc: django settings patch skipped", exc, flush=True)

try:
    from allauth.socialaccount import helpers as _allauth_helpers

    _orig_auth_err = _allauth_helpers.render_authentication_error

    def _auth_err(request, provider, *args, **kwargs):
        exc = kwargs.get("exception")
        error = kwargs.get("error")
        print(
            f"adventurelog-oidc: login failure provider={provider} error={error} exception={exc!r}",
            flush=True,
        )
        if exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__)
        return _orig_auth_err(request, provider, *args, **kwargs)

    _allauth_helpers.render_authentication_error = _auth_err
except Exception as exc:
    print("adventurelog-oidc: allauth patch skipped", exc, flush=True)
