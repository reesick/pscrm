"""
app/services.py — All external service integrations.

Telegram bot, SMTP email, Bhashini translation, Gemini LLM,
and the unified notification dispatcher.
"""
from __future__ import annotations

import json
import re
from typing import Optional

import aiosmtplib
import httpx
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import google.generativeai as genai

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from app.config import settings
from app.models import ClassificationResult


# ═══════════════════════════════════════════════════════════════════════
# SMTP EMAIL
# ═══════════════════════════════════════════════════════════════════════

async def send_email(to: str, subject: str, body_html: str) -> bool:
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html"))
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        return True
    except Exception as e:
        print(f"[SMTP] Failed to send to {to}: {e}")
        return False


async def send_complaint_received(to: str, grievance_id: str) -> bool:
    return await send_email(
        to,
        f"Complaint Received — {grievance_id}",
        f"<p>Your complaint <strong>{grievance_id}</strong> has been received and is being processed. "
        f"You can track its progress using this ID.</p>",
    )


async def send_status_update(to: str, grievance_id: str, new_status: str) -> bool:
    return await send_email(
        to,
        f"Status Update — {grievance_id}",
        f"<p>Your complaint <strong>{grievance_id}</strong> status has changed to "
        f"<strong>{new_status}</strong>.</p>",
    )


async def send_sla_warning_email(to: str, grievance_id: str, pct: int) -> bool:
    return await send_email(
        to,
        f"SLA Warning ({pct}%) — {grievance_id}",
        f"<p>Complaint <strong>{grievance_id}</strong> has consumed {pct}% of its SLA window. "
        f"Please take action immediately.</p>",
    )


async def send_escalation_alert(to: str, grievance_id: str, reason: str) -> bool:
    return await send_email(
        to,
        f"Escalation Alert — {grievance_id}",
        f"<p>Complaint <strong>{grievance_id}</strong> has been escalated. "
        f"Reason: <em>{reason}</em></p>",
    )


async def send_contractor_assignment(to: str, work_order_id: str, details: dict) -> bool:
    return await send_email(
        to,
        f"New Work Order Assigned — {work_order_id[:8]}",
        f"<p>You have been assigned work order <strong>{work_order_id[:8]}</strong>. "
        f"Category: {details.get('category', 'N/A')}. "
        f"Please log in to view details and upload proof photos.</p>",
    )


# ═══════════════════════════════════════════════════════════════════════
# TELEGRAM BOT
# ═══════════════════════════════════════════════════════════════════════

# Conversation states for /complaint flow
_DESCRIPTION, _LOCATION, _PHOTO = range(3)

telegram_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()


# ── /start command ────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to PS-CRM — Delhi MCD Complaint System.\n\n"
        "Use /complaint to file a new complaint, or /status <grievance_id> "
        "to check your complaint status.\n\n"
        "You can write in Hindi or English."
    )


# ── /status <id> ──────────────────────────────────────────────────────

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /status <grievance_id>\nExample: /status MCD-20250315-A7K2M")
        return
    grievance_id = ctx.args[0].strip().upper()
    try:
        from app.database import get_supabase
        sb = await get_supabase()
        result = await sb.table("complaints") \
            .select("grievance_id, status, category, sla_deadline, created_at") \
            .eq("grievance_id", grievance_id) \
            .maybe_single() \
            .execute()
        if not result.data:
            await update.message.reply_text(f"No complaint found with ID: {grievance_id}")
            return
        c = result.data
        text = (
            f"*Complaint: {c['grievance_id']}*\n"
            f"Status: {c['status']}\n"
            f"Category: {c.get('category', 'Pending classification')}\n"
            f"Filed on: {c['created_at'][:10]}\n"
        )
        if c.get("sla_deadline"):
            text += f"SLA Deadline: {c['sla_deadline'][:16]}\n"
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text("Could not fetch status. Please try again later.")


# ── /complaint — multi-step ConversationHandler ───────────────────────

async def _complaint_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    await update.message.reply_text(
        "Please describe the issue in detail. Include location details if possible."
    )
    return _DESCRIPTION


async def _complaint_description(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["description"] = update.message.text
    ctx.user_data["telegram_chat_id"] = update.effective_chat.id
    await update.message.reply_text(
        "Please share your location using the 📎 attachment button → Location. "
        "Or type your approximate address."
    )
    return _LOCATION


async def _complaint_location_coords(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    loc = update.message.location
    ctx.user_data["lat"] = loc.latitude
    ctx.user_data["lng"] = loc.longitude
    await update.message.reply_text(
        "Location received! Please send a photo of the issue (optional — tap /skip to proceed without one)."
    )
    return _PHOTO


async def _complaint_location_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    # Fallback: text address — use Delhi centre coordinates as placeholder
    ctx.user_data["lat"] = 28.6139
    ctx.user_data["lng"] = 77.2090
    ctx.user_data["location_text"] = update.message.text
    await update.message.reply_text(
        "Address noted. Please send a photo of the issue (optional — tap /skip to proceed without one)."
    )
    return _PHOTO


async def _complaint_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    media_urls: list[str] = []
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        media_urls.append(file.file_path)
    return await _submit_complaint_telegram(update, ctx, media_urls)


async def _complaint_skip_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    return await _submit_complaint_telegram(update, ctx, [])


async def _complaint_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Complaint cancelled. Type /complaint to start again.")
    return ConversationHandler.END


async def _submit_complaint_telegram(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    media_urls: list[str],
) -> int:
    """Internal — submits complaint data from Telegram flow to the DB."""
    from app.database import get_supabase, hash_email
    from app.utils import (
        generate_grievance_id,
        classify_with_rules,
        compute_sla_deadline,
        log_event,
    )
    try:
        raw_text = ctx.user_data.get("description", "")
        lat = ctx.user_data.get("lat", 28.6139)
        lng = ctx.user_data.get("lng", 77.2090)
        telegram_chat_id = ctx.user_data.get("telegram_chat_id")

        translated = await translate_to_english(raw_text)
        grievance_id = generate_grievance_id()
        classification = classify_with_rules(translated)

        if classification.confidence < 0.85:
            try:
                classification = await classify_with_gemini(translated)
            except GeminiFailure:
                pass  # keep rule-engine result

        sla_deadline = compute_sla_deadline(classification.category)

        sb = await get_supabase()
        complaint = await sb.table("complaints").insert({
            "grievance_id":              grievance_id,
            "citizen_telegram_chat_id":  telegram_chat_id,
            "raw_text":                  raw_text,
            "translated_text":           translated,
            "category":                  classification.category,
            "urgency":                   classification.urgency,
            "status":                    "NEW",
            "channel":                   "telegram",
            "location":                  f"SRID=4326;POINT({lng} {lat})",
            "media_urls":                media_urls,
            "sla_deadline":              sla_deadline.isoformat(),
            "llm_used":                  classification.llm_used,
            "classification_confidence": classification.confidence,
        }).execute()

        complaint_id = complaint.data[0]["id"]

        for dept_name in classification.departments:
            dept = await sb.table("departments").select("id").eq("name", dept_name).maybe_single().execute()
            if dept.data:
                await sb.table("complaint_departments").insert({
                    "complaint_id":  complaint_id,
                    "department_id": dept.data["id"],
                    "sub_status":    "NEW",
                    "sla_deadline":  sla_deadline.isoformat(),
                }).execute()

        await log_event(complaint_id, "complaint_created", "system", payload={"channel": "telegram"})

        await update.message.reply_text(
            f"✅ Complaint received!\n\n"
            f"*Grievance ID:* `{grievance_id}`\n"
            f"*Category:* {classification.category}\n"
            f"*SLA Deadline:* {sla_deadline.strftime('%d %b %Y %H:%M')} UTC\n\n"
            f"Use /status {grievance_id} to track your complaint.",
            parse_mode="Markdown",
        )
    except Exception as e:
        print(f"[Telegram] Complaint submission failed: {e}")
        await update.message.reply_text(
            "Sorry, there was an error submitting your complaint. Please try again later."
        )
    return ConversationHandler.END


# ── Message handler — survey replies ──────────────────────────────────

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    # If user has an active survey → route to survey agent handler
    from app.agents_followup import handle_citizen_survey_reply
    await handle_citizen_survey_reply(
        str(update.effective_chat.id),
        update.message.text,
    )


# ── Send helper — called by notification dispatcher and agents ─────────

async def telegram_send(chat_id: str, text: str) -> None:
    await telegram_app.bot.send_message(
        chat_id=int(chat_id),
        text=text,
        parse_mode="Markdown",
    )


# ── Wire up handlers ──────────────────────────────────────────────────

_complaint_conv = ConversationHandler(
    entry_points=[CommandHandler("complaint", _complaint_start)],
    states={
        _DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, _complaint_description)],
        _LOCATION: [
            MessageHandler(filters.LOCATION, _complaint_location_coords),
            MessageHandler(filters.TEXT & ~filters.COMMAND, _complaint_location_text),
        ],
        _PHOTO: [
            MessageHandler(filters.PHOTO, _complaint_photo),
            CommandHandler("skip", _complaint_skip_photo),
        ],
    },
    fallbacks=[CommandHandler("cancel", _complaint_cancel)],
)

telegram_app.add_handler(CommandHandler("start", cmd_start))
telegram_app.add_handler(CommandHandler("status", cmd_status))
telegram_app.add_handler(_complaint_conv)
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


# ═══════════════════════════════════════════════════════════════════════
# BHASHINI TRANSLATION
# ═══════════════════════════════════════════════════════════════════════

BHASHINI_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"

_ENGLISH_PATTERN = re.compile(r"^[\x00-\x7F]+$")


def _is_english(text: str) -> bool:
    return bool(_ENGLISH_PATTERN.match(text.strip()))


async def translate_to_english(text: str, source_lang: str = "auto") -> str:
    if source_lang == "en" or _is_english(text):
        return text

    payload = {
        "pipelineTasks": [
            {
                "taskType": "translation",
                "config": {
                    "language": {
                        "sourceLanguage": source_lang if source_lang != "auto" else "hi",
                        "targetLanguage": "en",
                    }
                },
            }
        ],
        "inputData": {"input": [{"source": text}]},
    }
    headers = {
        "userID":    settings.BHASHINI_USER_ID,
        "ulcaApiKey": settings.BHASHINI_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(BHASHINI_URL, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()["pipelineResponse"][0]["output"][0]["target"]
    except Exception as e:
        print(f"[Bhashini] Translation failed: {e} — returning original text")
        return text


async def translate_from_english(text: str, target_lang: str) -> str:
    """Used to send Telegram notifications in citizen's preferred language."""
    if target_lang == "en":
        return text

    payload = {
        "pipelineTasks": [
            {
                "taskType": "translation",
                "config": {
                    "language": {
                        "sourceLanguage": "en",
                        "targetLanguage": target_lang,
                    }
                },
            }
        ],
        "inputData": {"input": [{"source": text}]},
    }
    headers = {
        "userID":    settings.BHASHINI_USER_ID,
        "ulcaApiKey": settings.BHASHINI_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(BHASHINI_URL, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()["pipelineResponse"][0]["output"][0]["target"]
    except Exception as e:
        print(f"[Bhashini] Reverse translation failed: {e}")
        return text


# ═══════════════════════════════════════════════════════════════════════
# GEMINI CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════

genai.configure(api_key=settings.GEMINI_API_KEY)
_gemini_model = genai.GenerativeModel("gemini-2.5-flash")

CLASSIFICATION_PROMPT = """
You are a civic complaint classification system for Delhi MCD.
Given the complaint text below, return a JSON object with exactly these fields:
- category: one of [drainage, streetlight, road, tree, garbage, water_supply, other]
- urgency: integer 1-5 (1=low, 5=critical)
- departments: list of department names from [Public Works, Electricity, Horticulture, Sanitation, Water Supply]
- asset_types: list of asset types from [pole, drain, road_segment, tree, water_main, garbage_point]

Respond with JSON only. No explanation.

Complaint: {complaint_text}
"""


class GeminiFailure(Exception):
    pass


async def classify_with_gemini(text: str) -> ClassificationResult:
    try:
        response = await _gemini_model.generate_content_async(
            CLASSIFICATION_PROMPT.format(complaint_text=text)
        )
        raw = response.text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)
        return ClassificationResult(
            category=data.get("category", "other"),
            urgency=int(data.get("urgency", 2)),
            departments=data.get("departments", []),
            asset_types=data.get("asset_types", []),
            confidence=0.95,
            llm_used=True,
        )
    except Exception as e:
        raise GeminiFailure(str(e)) from e


# ═══════════════════════════════════════════════════════════════════════
# UNIFIED NOTIFICATION DISPATCHER
# ═══════════════════════════════════════════════════════════════════════

_EVENT_SUBJECTS: dict[str, str] = {
    "new_complaint_assigned":  "New Complaint Assigned",
    "sla_escalation":          "SLA Breach — Complaint Escalated",
    "sla_warning_50":          "SLA Warning (50%) — Action Required",
    "sla_warning_90":          "SLA Warning (90%) — Urgent Action Required",
    "contractor_proof_missing": "Action Required: Proof Photo Missing",
    "complaint_reopened":       "Complaint Reopened",
    "status_update":            "Complaint Status Updated",
    "work_order_assigned":      "New Work Order Assigned",
}


def subject_from_event(event_type: str) -> str:
    return _EVENT_SUBJECTS.get(event_type, f"PS-CRM Notification: {event_type}")


def format_notification(event_type: str, payload: dict, lang: str = "en") -> str:
    complaint_id_short = str(payload.get("complaint_id", ""))[:8]
    templates: dict[str, str] = {
        "new_complaint_assigned":  f"New complaint assigned to you. ID: {complaint_id_short}. Category: {payload.get('category', 'N/A')}",
        "sla_escalation":          f"Complaint {complaint_id_short} has breached its SLA and been escalated.",
        "sla_warning_50":          f"Complaint {complaint_id_short} has used 50% of its SLA window.",
        "sla_warning_90":          f"URGENT: Complaint {complaint_id_short} has used 90% of its SLA window.",
        "contractor_proof_missing": f"Proof photo missing for complaint {complaint_id_short}. Please upload within 24 hours.",
        "complaint_reopened":       f"Complaint {complaint_id_short} has been reopened by the citizen.",
        "work_order_assigned":      f"You have been assigned a new work order for complaint {complaint_id_short}.",
    }
    return templates.get(event_type, f"Update on complaint {complaint_id_short}: {event_type}")


async def _resolve_recipient(recipient_id: str) -> dict:
    from app.database import get_supabase
    sb = await get_supabase()

    # Try officers table first
    try:
        officer = await sb.table("officers").select("*").eq("id", recipient_id).maybe_single().execute()
        if officer.data:
            return {
                "type":             officer.data["role"],
                "email":            officer.data.get("email"),
                "telegram_chat_id": officer.data.get("telegram_chat_id"),
                "preferred_language": "en",
            }
    except Exception:
        pass

    # Try contractors table
    try:
        contractor = await sb.table("contractors").select("*").eq("id", recipient_id).maybe_single().execute()
        if contractor.data:
            return {
                "type":             "contractor",
                "contact_email":    contractor.data.get("contact_email"),
                "telegram_chat_id": contractor.data.get("telegram_chat_id"),
                "preferred_language": "en",
            }
    except Exception:
        pass

    return {"type": "unknown"}


async def notify(recipient_id: str, event_type: str, payload: dict) -> None:
    """
    Routes notification to correct channel based on recipient type.
    - Citizens      → Telegram only (chat_id stored at bot interaction time)
    - JSSA/AA/FAA   → Telegram if they have a registered chat_id, else SMTP Email
    - Contractors   → SMTP Email always (contact_email field)
    - Super Admin   → Both Telegram + SMTP Email
    """
    recipient = await _resolve_recipient(recipient_id)
    message = format_notification(event_type, payload, recipient.get("preferred_language", "en"))
    r_type = recipient.get("type", "unknown")

    if r_type == "citizen":
        if recipient.get("telegram_chat_id"):
            await telegram_send(str(recipient["telegram_chat_id"]), message)

    elif r_type in ("jssa", "aa", "faa"):
        if recipient.get("telegram_chat_id"):
            await telegram_send(str(recipient["telegram_chat_id"]), message)
        elif recipient.get("email"):
            await send_email(recipient["email"], subject_from_event(event_type), f"<p>{message}</p>")

    elif r_type == "contractor":
        contact = recipient.get("contact_email")
        if contact:
            await send_email(contact, subject_from_event(event_type), f"<p>{message}</p>")

    elif r_type == "super_admin":
        if recipient.get("telegram_chat_id"):
            await telegram_send(str(recipient["telegram_chat_id"]), message)
        if recipient.get("email"):
            await send_email(recipient["email"], subject_from_event(event_type), f"<p>{message}</p>")
