from __future__ import annotations

import asyncio
import hashlib
import threading
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from supabase._async.client import AsyncClient, create_client as create_async_client

from app.config import settings
from app.models import CurrentUser


# ── Singleton Supabase async client (PostgREST / Storage / Auth) ──────
# Uses SERVICE_ROLE_KEY — agents need to bypass RLS for cross-ward reads.
# Citizen-facing reads that must respect RLS pass the user's JWT explicitly.

_supabase: Optional[AsyncClient] = None


async def get_supabase() -> AsyncClient:
    global _supabase
    if _supabase is None:
        _supabase = await create_async_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )
    return _supabase


# ── Supabase Realtime subscription ───────────────────────────────────
# supabase-py 2.3.4's AsyncClient is a PostgREST-only wrapper; it has no
# .channel() method.  Realtime requires the lower-level `realtime.Socket`
# API which uses blocking sync wrappers internally and must run in a
# dedicated daemon thread with its own event loop.

_realtime_thread: Optional[threading.Thread] = None


def _run_realtime_blocking(main_loop: asyncio.AbstractEventLoop) -> None:
    """Blocking realtime listener — runs in a daemon thread with its own event loop."""
    # Give the thread its own event loop so realtime-py's internal
    # asyncio.get_event_loop().run_until_complete() calls work correctly.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    ws_url = (
        settings.SUPABASE_URL
        .replace("https://", "wss://")
        .replace("http://", "ws://")
        + f"/realtime/v1/websocket?apikey={settings.SUPABASE_SERVICE_ROLE_KEY}&vsn=1.0.0"
    )

    def handle_insert(payload: dict) -> None:
        # Payload from realtime-py: {"record": {...}, "type": "INSERT", ...}
        record = (
            payload.get("record")
            or payload.get("new")
            or payload.get("data", {}).get("record")
            or {}
        )
        cid = record.get("id")
        if cid and not main_loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                on_new_complaint({"new": {"id": cid}}), main_loop
            )

    try:
        from realtime import Socket as RealtimeSocket
        socket = RealtimeSocket(
            ws_url,
            params={"apikey": settings.SUPABASE_SERVICE_ROLE_KEY},
        )
        socket.connect()
        channel = socket.set_channel("realtime:public:complaints")
        channel.join().on("INSERT", handle_insert)
        print("[Realtime] Listening for new complaints …")
        socket.listen()  # blocks until connection drops
    except Exception as exc:
        print(f"[Realtime] Listener stopped: {exc}")


async def init_supabase_realtime() -> None:
    global _realtime_thread
    main_loop = asyncio.get_event_loop()
    _realtime_thread = threading.Thread(
        target=_run_realtime_blocking,
        args=(main_loop,),
        daemon=True,
        name="supabase-realtime",
    )
    _realtime_thread.start()
    print("[Realtime] Subscription thread started")


async def on_new_complaint(payload: dict) -> None:
    # Lazy import to avoid circular dependency at module load time
    from app.agents import supervisor_agent_run
    complaint_id = payload["new"]["id"]
    await supervisor_agent_run(complaint_id)


# ── PostGIS helper queries ────────────────────────────────────────────
# find_nearest_assets: ST_DWithin radius query — returns list of Asset rows
# assign_ward: ST_Contains check — returns ward_id UUID
# These are called by GeoSpatial Agent (agents.py)

async def find_nearest_assets(
    lat: float,
    lng: float,
    asset_type: Optional[str],
    radius_m: int = 50,
) -> list[dict]:
    sb = await get_supabase()
    # RPC defined in supabase/migrations/006_functions.sql
    result = await sb.rpc("find_nearby_assets", {
        "lat":         lat,
        "lng":         lng,
        "radius_m":    radius_m,
        "p_asset_type": asset_type,
    }).execute()
    return result.data or []


async def assign_ward(lat: float, lng: float) -> Optional[str]:
    sb = await get_supabase()
    # RPC defined in supabase/migrations/006_functions.sql
    result = await sb.rpc("find_ward_for_point", {
        "lat": lat,
        "lng": lng,
    }).execute()
    return result.data if result.data else None


# ── Auth helpers ──────────────────────────────────────────────────────

async def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> CurrentUser:
    """
    Validates the Bearer JWT from the Authorization header.
    Supabase verifies it; we extract role + ward from user metadata.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = authorization.split(" ", 1)[1]
    sb = await get_supabase()
    try:
        user_response = await sb.auth.get_user(token)
        user = user_response.user
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token validation failed")

    metadata = user.user_metadata or {}
    app_meta = user.app_metadata or {}

    # Prefer DB lookup — Supabase JWTs don't carry custom role in metadata
    officer_result = await sb.table("officers").select("role, ward_ids").eq("id", user.id).maybe_single().execute()
    if officer_result and officer_result.data:
        role = officer_result.data["role"]
        ward_ids: list = officer_result.data.get("ward_ids") or []
        ward_id = ward_ids[0] if ward_ids else None
        zone_ward_ids = ward_ids
    else:
        role = metadata.get("role") or app_meta.get("role", "jssa")
        ward_id = metadata.get("ward_id")
        zone_ward_ids = metadata.get("zone_ward_ids", [])

    return CurrentUser(
        id=user.id,
        role=role,
        ward_id=ward_id,
        zone_ward_ids=zone_ward_ids,
        email=user.email,
    )


def require_role(*allowed_roles: str):
    """Dependency factory that enforces role-based access control."""
    async def check_role(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not permitted. Required: {list(allowed_roles)}",
            )
        return current_user
    return check_role


# ── Email hash helper ─────────────────────────────────────────────────

def hash_email(email: str) -> str:
    """SHA-256 hash of email — citizens' raw emails are never persisted."""
    return hashlib.sha256(email.lower().strip().encode()).hexdigest()
