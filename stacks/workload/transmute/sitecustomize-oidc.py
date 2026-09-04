# Caddy tls internal is not in certifi. Transmute's OIDC client is httpx
# (verify=True, certifi bundle). Homelab skip, same idea as Grafana/Immich.
import httpx


def _disable_verify(cls):
    orig = cls.__init__

    def _init(self, *args, **kwargs):
        kwargs["verify"] = False
        orig(self, *args, **kwargs)

    cls.__init__ = _init


_disable_verify(httpx.Client)
_disable_verify(httpx.AsyncClient)
