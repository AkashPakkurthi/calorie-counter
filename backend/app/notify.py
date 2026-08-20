"""Daily nudge email, sent through Brevo's transactional API.

Composing the message is a pure function of the day's numbers, so it can be
tested without touching the network or sending anything.
"""

import logging

import httpx

from .config import get_settings
from .schemas import DayOut

logger = logging.getLogger(__name__)
settings = get_settings()

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
TIMEOUT = 20.0


class NotifyError(RuntimeError):
    """Raised when the mail cannot be sent -- reported, never silently dropped."""


def configured() -> bool:
    return bool(settings.brevo_api_key and settings.brevo_sender_email)


def _bar(consumed: float, target: float, width: int = 20) -> str:
    if target <= 0:
        return ""
    filled = max(0, min(width, round(consumed / target * width)))
    return "█" * filled + "·" * (width - filled)


def compose(day: DayOut, name: str = "", mode: str = "evening") -> tuple[str, str, str]:
    """Return (subject, html, text) for one person's day.

    `mode` only changes the wording: a morning mail is a prompt to start
    logging, an evening one reports where the day landed.
    """
    greeting = f"Hi {name}," if name else "Hi,"
    totals, targets = day.totals, day.targets
    logged = sum(len(v) for v in day.meals.values())
    remaining = round(targets.daily_calories - totals.calories)
    link = settings.app_url.rstrip("/") or ""

    if logged == 0:
        if mode == "morning":
            subject = "Log your breakfast"
            headline = "Nothing logged yet today."
            body_lines = [
                f"Your budget for today is {targets.daily_calories} kcal and "
                f"{targets.protein_g} g of protein.",
                "Type what you had -- a rough description is enough, the app "
                "works out the portions.",
            ]
        else:
            subject = "Nothing logged today"
            headline = "You haven't logged anything today."
            body_lines = [
                "A quick entry now keeps the streak honest -- even a rough "
                "description is enough, the app works out the rest.",
            ]
    else:
        over = totals.calories > targets.daily_calories
        subject = (
            f"{round(totals.calories)} kcal today"
            f" -- {abs(remaining)} {'over' if over else 'left'}"
        )
        headline = (
            f"{round(totals.calories)} of {targets.daily_calories} kcal"
            f" ({abs(remaining)} {'over budget' if over else 'still available'})"
        )
        body_lines = [
            f"Protein {round(totals.protein_g)}/{targets.protein_g} g"
            f"  {_bar(totals.protein_g, targets.protein_g)}",
            f"Carbs   {round(totals.carbs_g)}/{targets.carbs_g} g",
            f"Fat     {round(totals.fat_g)}/{targets.fat_g} g",
            f"Fibre   {round(totals.fiber_g)}/{targets.fiber_g} g",
        ]
        if day.activity.calories_burned:
            body_lines.append(
                f"Burned {round(day.activity.calories_burned)} kcal "
                f"-> net {round(day.net_calories)} kcal"
            )
        if totals.protein_g < targets.protein_g * 0.8:
            body_lines.append(
                f"Protein is short by {round(targets.protein_g - totals.protein_g)} g "
                "-- curd, dal or eggs would close the gap."
            )

    if day.weight_stale_days is None or day.weight_stale_days > 7:
        body_lines.append("It has been over a week since your last weigh-in.")

    text = "\n".join([greeting, "", headline, ""] + body_lines + ["", link])
    rows = "".join(f"<p style='margin:4px 0'>{line}</p>" for line in body_lines)
    html = f"""
    <div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;
                background:#121218;color:#ececf2;padding:24px;border-radius:12px;
                max-width:520px">
      <p style="color:#9191a6;margin:0 0 12px">{greeting}</p>
      <h2 style="margin:0 0 16px;font-size:20px">{headline}</h2>
      <div style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
                  font-size:14px;color:#a5a5b8">{rows}</div>
      {f'<p style="margin-top:20px"><a href="{link}" style="background:#3987e5;color:#0b0b0f;padding:10px 16px;border-radius:8px;text-decoration:none;font-weight:600">Open the tracker</a></p>' if link else ''}
    </div>
    """
    return subject, html, text


async def send(to_email: str, subject: str, html: str, text: str) -> None:
    if not configured():
        raise NotifyError("BREVO_API_KEY and BREVO_SENDER_EMAIL are not set")

    payload = {
        "sender": {
            "email": settings.brevo_sender_email,
            "name": settings.brevo_sender_name,
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html,
        "textContent": text,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                BREVO_URL,
                json=payload,
                headers={
                    "api-key": settings.brevo_api_key,
                    "accept": "application/json",
                },
            )
    except httpx.HTTPError as exc:
        # A blocked or unreachable host (corporate VPN, DNS, TLS) must read as
        # a mail failure, not leak an httpx traceback out of the endpoint.
        raise NotifyError(f"Could not reach Brevo: {exc}") from exc
    if response.status_code >= 300:
        # Brevo puts the reason in the body; the status alone is not enough.
        raise NotifyError(f"Brevo rejected the send ({response.status_code}): {response.text[:200]}")
    logger.info("daily email sent to %s", to_email)
