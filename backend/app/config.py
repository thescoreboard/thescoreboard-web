"""
Centralized configuration — all env vars read here, nowhere else.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = "TheScoreBoard"
    VERSION: str = "2.0.0"
    ENV: str = os.getenv("ENV", "dev")  # "dev" | "prod"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))

    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")

    # CORS
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173,http://localhost:8081,http://localhost:19006")

    # Public base URL — used to build absolute share / OG-image URLs.
    # In production set to: https://api.yourdomain.com
    APP_URL: str = os.getenv("APP_URL", "http://localhost:8000")

    # The canonical frontend SPA URL — used in share-page redirects.
    # In production set to: https://app.yourdomain.com
    SITE_URL: str = os.getenv("SITE_URL", "http://localhost:5173")

    # Supabase Storage (service key stays backend-only — never exposed to browser)
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

    # Supabase anon/public key — safe to expose to the browser via VITE_ prefix.
    # The frontend uses it only for signed-upload PUT requests.
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")

    # Storage bucket names
    BUCKET_LOGOS: str = "logos"
    BUCKET_TEAM_BANNERS: str = "team-banners"
    BUCKET_TOURNAMENT_POSTERS: str = "tournament-posters"
    BUCKET_OG_CACHE: str = "og-cache"

    # Per-bucket upload size limits (bytes)
    MAX_LOGO_SIZE: int = 2 * 1024 * 1024        # 2 MB
    MAX_POSTER_SIZE: int = 5 * 1024 * 1024       # 5 MB

    ALLOWED_IMAGE_TYPES: list = ["image/jpeg", "image/png", "image/webp"]

    @property
    def is_prod(self) -> bool:
        return self.ENV == "prod"

    @property
    def supabase_configured(self) -> bool:
        return bool(self.SUPABASE_URL and self.SUPABASE_SERVICE_KEY)


settings = Settings()

# ── Boot-time secret guard ────────────────────────────────────
# Anyone who knows the signing key can forge valid JWTs for ANY user, so we
# refuse to boot with a known placeholder key whenever the process is actually
# serving public traffic.
#
# The tricky part: local dev legitimately runs with a placeholder key against a
# REMOTE (Supabase) dev database, so "remote DB" is NOT a safe prod signal.
# The reliable signal is the public-facing URLs: in production they point at a
# real domain, while every local-dev URL is localhost. This also catches the
# "forgot to set ENV=prod on the prod host" misconfiguration.
_PLACEHOLDER_SECRETS = {
    "",
    "change-me-in-production",
    "change-me-to-a-random-64-char-string",
}

_LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0")


def _serves_public_traffic() -> bool:
    combined = f"{settings.FRONTEND_URL} {settings.SITE_URL} {settings.APP_URL}"
    return not any(h in combined for h in _LOCAL_HOSTS)


if settings.SECRET_KEY in _PLACEHOLDER_SECRETS and (
    settings.ENV == "prod" or _serves_public_traffic()
):
    raise RuntimeError(
        "SECRET_KEY is a placeholder but this instance is serving public traffic. "
        "Set SECRET_KEY to a cryptographically secure random value. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
