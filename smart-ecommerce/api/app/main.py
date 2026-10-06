import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import ROOT_DIR, settings
from .realtime import manager
from .routers import admin_api, auth, cart, notifications, orders, payments, products, realtime_api

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.bind_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title="Smart E-Commerce API", version="1.0.0",
              description="User panel API: auth, catalogue, cart, Stripe checkout, orders, notifications.",
              lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth, products, cart, orders, payments, notifications, admin_api):
    app.include_router(r.router, prefix="/api")
app.include_router(realtime_api.router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.get("/api/config", tags=["meta"])
def public_config():
    """Values the frontend needs at start-up (all safe to expose)."""
    return {
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY or None,
        "mock_payments": not settings.stripe_enabled,
        "auth0": {"domain": settings.AUTH0_DOMAIN, "client_id": settings.AUTH0_CLIENT_ID}
        if settings.AUTH0_DOMAIN and settings.AUTH0_CLIENT_ID else None,
    }


settings.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.MEDIA_ROOT), name="media")
# Frontend last: it is mounted at "/" and would shadow later routes.
app.mount("/", StaticFiles(directory=ROOT_DIR / "frontend", html=True), name="frontend")
