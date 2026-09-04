# Caddy tls internal is not in certifi. Prefer the CA bundle the entrypoint
# fetched; otherwise skip verify (homelab).
import os
import ssl

import httpx

_ca = os.environ.get("TRANSMUTE_OIDC_CA") or os.environ.get("SSL_CERT_FILE")
if _ca and os.path.isfile(_ca):
    ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=_ca)
    _verify = _ca
else:
    ssl._create_default_https_context = ssl._create_unverified_context
    _verify = False


def _disable_or_pin(cls):
    orig = cls.__init__

    def _init(self, *args, **kwargs):
        kwargs["verify"] = _verify
        orig(self, *args, **kwargs)

    cls.__init__ = _init


_disable_or_pin(httpx.Client)
_disable_or_pin(httpx.AsyncClient)
