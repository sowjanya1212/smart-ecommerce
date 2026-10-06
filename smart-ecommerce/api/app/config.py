"""Settings read from environment variables (and the project-root .env file)."""
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


def _load_env():
    env_file = ROOT_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()


def _get(name, default=""):
    return os.environ.get(name, default)


class Settings:
    def __init__(self):
        self.DATABASE_URL = self._database_url(_get("DATABASE_URL"))
        self.JWT_SECRET = _get("JWT_SECRET", "dev-insecure-jwt-secret-change-me-please")
        self.JWT_ALGORITHM = "HS256"
        self.ACCESS_TOKEN_MINUTES = int(_get("ACCESS_TOKEN_MINUTES", "60"))
        self.REFRESH_TOKEN_DAYS = int(_get("REFRESH_TOKEN_DAYS", "7"))
        self.PASSWORD_ITERATIONS = int(_get("PASSWORD_ITERATIONS", "600000"))
        self.CORS_ORIGINS = [o.strip() for o in _get("CORS_ORIGINS", "http://localhost:8000").split(",") if o.strip()]
        self.CURRENCY = _get("CURRENCY", "usd").lower()
        self.INTERNAL_SECRET = _get("INTERNAL_SECRET", "change-me-internal")
        self.MEDIA_ROOT = Path(_get("MEDIA_ROOT", str(ROOT_DIR / "media")))

        self.STRIPE_SECRET_KEY = _get("STRIPE_SECRET_KEY")
        self.STRIPE_PUBLISHABLE_KEY = _get("STRIPE_PUBLISHABLE_KEY")
        self.STRIPE_WEBHOOK_SECRET = _get("STRIPE_WEBHOOK_SECRET")

        self.AUTH0_DOMAIN = _get("AUTH0_DOMAIN")
        self.AUTH0_CLIENT_ID = _get("AUTH0_CLIENT_ID")

        self.SMTP_HOST = _get("SMTP_HOST")
        self.SMTP_PORT = int(_get("SMTP_PORT", "587"))
        self.SMTP_USER = _get("SMTP_USER")
        self.SMTP_PASSWORD = _get("SMTP_PASSWORD")
        self.SMTP_TLS = _get("SMTP_TLS", "1") == "1"
        self.EMAIL_FROM = _get("EMAIL_FROM", "Smart Shop <no-reply@smartshop.local>")

    @staticmethod
    def _database_url(url):
        if url.startswith(("postgres://", "postgresql://")):
            return url.replace("postgres://", "postgresql+psycopg2://", 1).replace(
                "postgresql://", "postgresql+psycopg2://", 1)
        if url.startswith("postgresql+"):
            return url
        path = url[len("sqlite:///"):] if url.startswith("sqlite:///") else "data/db.sqlite3"
        path = Path(path)
        if not path.is_absolute():
            path = ROOT_DIR / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path}"

    @property
    def stripe_enabled(self):
        return bool(self.STRIPE_SECRET_KEY)


settings = Settings()
