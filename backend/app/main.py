"""
app/main.py — FastAPI application entry point.

Responsibilities:
  - Lifespan context: initialise Supabase Realtime subscription + Telegram webhook
  - CORS middleware (allow FRONTEND_URL)
  - Mount all 3 routers under /api/v1
  - GET /health
  - POST /telegram/webhook  — receives Telegram updates
  - POST /internal/run-predictive-agent — called by Render Cron nightly
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.agents_followup import run_predictive_agent, start_followup_agent
from app.config import settings
from app.database import init_supabase_realtime
from app.routers_admin import router as admin_router
from app.routers_analytics import router as analytics_router
from app.routers_complaints import router as complaints_router
from app.services import telegram_app


# ── Lifespan ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
      1. Initialise async Supabase client + Realtime subscription.
      2. Register Telegram webhook.
      3. Start Follow-Up agent background task.
    Shutdown: cancel background tasks cleanly.
    """
    # Supabase Realtime — non-fatal: server boots even if realtime is unavailable
    try:
        await init_supabase_realtime()
    except Exception as exc:
        print(f"[Realtime] Could not start subscription thread: {exc}")

    # Telegram webhook registration
    try:
        await telegram_app.initialize()
        webhook_url = f"{settings.BACKEND_URL}/telegram/webhook"
        await telegram_app.bot.set_webhook(
            url=webhook_url,
            secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
            allowed_updates=["message", "callback_query"],
        )
        print(f"[Telegram] Webhook set to {webhook_url}")
    except Exception as e:
        print(f"[Telegram] Could not set webhook: {e}")

    # Follow-Up Agent — runs as a background asyncio task
    followup_task = asyncio.create_task(start_followup_agent())

    yield

    # Shutdown
    followup_task.cancel()
    try:
        await followup_task
    except asyncio.CancelledError:
        pass

    try:
        await telegram_app.shutdown()
    except Exception:
        pass


# ── App factory ───────────────────────────────────────────────────────

app = FastAPI(
    title="PS-CRM Grievance Management API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — allow the React/Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────

app.include_router(complaints_router, prefix="/api/v1")
app.include_router(admin_router,      prefix="/api/v1")
app.include_router(analytics_router,  prefix="/api/v1")


# ── Public health check ────────────────────────────────────────────────

@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok"}


# ── Telegram webhook ───────────────────────────────────────────────────

@app.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(request: Request):
    """
    Receives Telegram updates.  Validates X-Telegram-Bot-Api-Secret-Token header.
    """
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")

    import json
    from telegram import Update

    body = await request.body()
    update = Update.de_json(json.loads(body), telegram_app.bot)
    await telegram_app.process_update(update)
    return Response(status_code=200)


# ── Internal Cron — Predictive Agent ──────────────────────────────────

def _verify_cron_key(x_internal_key: str = Header(...)):
    if x_internal_key != settings.INTERNAL_CRON_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorised")


@app.post("/internal/run-predictive-agent", tags=["infra"], dependencies=[Depends(_verify_cron_key)])
async def run_predictive_agent_endpoint(background_tasks: BackgroundTasks):
    """
    Called nightly by Render Cron at 02:00 IST.
    Runs DBSCAN hotspot detection in a background task so the HTTP
    response returns immediately and the Cron job doesn't time out.
    """
    background_tasks.add_task(run_predictive_agent)
    return {"message": "Predictive agent triggered"}
