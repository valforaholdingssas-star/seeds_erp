from .base import *  # noqa: F401,F403

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "0") or "0")
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# Required when serving behind a public domain / HTTPS
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

# Fail closed if someone forgot to rotate the default secret
if SECRET_KEY in {"unsafe-dev-secret-change-me", "change-me-to-a-long-random-string"}:
    raise RuntimeError("DJANGO_SECRET_KEY inseguro en producción. Genera uno nuevo.")

if not env("SEEDS_SECRETS_KEY"):
    raise RuntimeError("SEEDS_SECRETS_KEY es obligatorio en producción.")
