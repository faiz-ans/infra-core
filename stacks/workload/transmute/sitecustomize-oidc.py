# Caddy tls internal is not in certifi. Transmute's OIDC client is httpx
# (verify=True, certifi bundle). Homelab skip, same idea as Grafana/Immich.
import ssl

import httpx

ssl._create_default_https_context = ssl._create_unverified_context


def _disable_verify(cls):
    orig = cls.__init__

    def _init(self, *args, **kwargs):
        kwargs["verify"] = False
        orig(self, *args, **kwargs)

    cls.__init__ = _init


_disable_verify(httpx.Client)
_disable_verify(httpx.AsyncClient)
