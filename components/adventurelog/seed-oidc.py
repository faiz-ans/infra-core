#!/usr/bin/env python3
"""Idempotent Authelia SocialApp. Runs after /aio/entrypoint.sh migrate."""
import os
import sys
from pathlib import Path


def _prepare_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
    for root in ("/code", "/app", "/backend", "/server"):
        if Path(root, "manage.py").is_file():
            sys.path.insert(0, root)
            os.chdir(root)
            return


def main() -> int:
    secret = os.environ.get("OIDC_CLIENT_SECRET", "").strip()
    domain = os.environ.get("DOMAIN", "").strip()
    if not secret or not domain:
        print(
            "adventurelog-oidc: seed skipped (OIDC_CLIENT_SECRET or DOMAIN unset)",
            flush=True,
        )
        return 0

    _prepare_django()
    import django

    django.setup()

    from allauth.socialaccount.models import SocialApp
    from django.contrib.sites.models import Site

    settings = {
        "server_url": f"https://auth.{domain}",
        "token_auth_method": "client_secret_post",
        "fetch_userinfo": False,
    }

    app = SocialApp.objects.filter(provider_id="authelia").first()
    if app is None:
        app = SocialApp.objects.filter(
            provider="openid_connect", client_id="adventurelog"
        ).first()
    if app is None:
        app = SocialApp(provider="openid_connect", provider_id="authelia")

    app.provider = "openid_connect"
    app.provider_id = "authelia"
    app.name = "Authelia"
    app.client_id = "adventurelog"
    app.secret = secret
    app.settings = settings
    app.save()

    site = Site.objects.filter(pk=1).first()
    if site is None:
        site = Site.objects.create(pk=1, domain="example.com", name="example.com")
    app.sites.add(site)
    print(
        f"adventurelog-oidc: SocialApp authelia ready (site={site.domain})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"adventurelog-oidc: seed failed (non-fatal): {exc}", flush=True)
        raise SystemExit(0)
