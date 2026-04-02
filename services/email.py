"""
services/email.py
─────────────────
Resend-powered emails for booking request notifications.
Works with plain dicts returned directly from the Supabase client.

Install:   pip install resend
Env vars to add to your .env / hosting config:

    RESEND_API_KEY=re_xxxxxxxxxxxx
    EMAIL_FROM=bookings@yourdomain.com
    ADMIN_EMAIL=you@youremail.com
    BUSINESS_NAME=My Stays
"""

import os
import urllib.parse

import resend
from dotenv import load_dotenv

# Load .env before reading any environment variables
load_dotenv()

# ── Configure at import time ──────────────────────────────────────────────────
resend.api_key = os.environ["RESEND_API_KEY"]

FROM_ADDRESS  = os.getenv("EMAIL_FROM",    "bookings@yourdomain.com")
ADMIN_EMAIL   = os.getenv("ADMIN_EMAIL",   "you@youremail.com")
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "My Stays")

CURRENCY_SYMBOLS = {
    "NGN": "₦", "USD": "$", "EUR": "€",
    "GBP": "£", "GHS": "₵", "KES": "KSh", "ZAR": "R",
}


# ── Formatting helpers ────────────────────────────────────────────────────────

def _fmt(amount, currency: str = "NGN") -> str:
    if amount is None:
        return "—"
    sym = CURRENCY_SYMBOLS.get(currency, f"{currency} ")
    return f"{sym}{float(amount):,.0f}"


def _guest_str(data: dict) -> str:
    adults   = int(data.get("adults")   or 1)
    children = int(data.get("children") or 0)
    infants  = int(data.get("infants")  or 0)
    parts    = [f"{adults} adult{'s' if adults != 1 else ''}"]
    if children:
        parts.append(f"{children} child{'ren' if children != 1 else ''}")
    if infants:
        parts.append(f"{infants} infant{'s' if infants != 1 else ''}")
    return ", ".join(parts)


# ── Admin notification HTML ───────────────────────────────────────────────────

def _build_admin_html(data: dict) -> str:
    currency    = data.get("currency", "NGN")
    disc_pct    = float(data.get("discount_percent") or 0)
    disc_amt    = float(data.get("discount_amount")  or 0)
    ppn         = float(data.get("price_per_night")  or 0)
    nights      = int(data.get("nights") or 0)
    base_total  = ppn * nights
    final_total = float(data.get("estimated_total") or base_total)
    has_promo   = bool(data.get("promo_label") or disc_pct > 0)

    # Promo banner
    promo_banner = ""
    if has_promo:
        parts = []
        if data.get("promo_label"): parts.append(data["promo_label"])
        if disc_pct:                parts.append(f"{int(disc_pct)}% off")
        promo_banner = f"""
        <div style="background:linear-gradient(135deg,#7c3aed,#a855f7);
                    padding:10px 32px;text-align:center;font-size:13px;
                    font-weight:600;color:#fff;letter-spacing:.04em">
            🏷️ &nbsp;{" · ".join(parts)} — Promo applied to this request
        </div>"""

    # Price breakdown rows
    breakdown = f"""
        <tr>
          <td style="padding:8px 0;font-size:13px;color:#64748b">
            {_fmt(ppn, currency)} × {nights or "?"} nights
          </td>
          <td style="padding:8px 0;font-size:13px;color:#0f172a;
                     text-align:right;font-weight:500">
            {_fmt(base_total, currency)}
          </td>
        </tr>"""

    if disc_pct and disc_amt:
        breakdown += f"""
        <tr>
          <td style="padding:4px 0;font-size:13px;color:#7c3aed">
            {int(disc_pct)}% discount
          </td>
          <td style="padding:4px 0;font-size:13px;color:#7c3aed;
                     text-align:right;font-weight:500">
            −{_fmt(disc_amt, currency)}
          </td>
        </tr>"""

    breakdown += f"""
        <tr style="border-top:1px solid #e2e8f0">
          <td style="padding:10px 0 4px;font-size:14px;font-weight:700;color:#0f172a">
            Estimated Total
          </td>
          <td style="padding:10px 0 4px;font-size:16px;font-weight:700;
                     color:#0f172a;text-align:right">
            {_fmt(final_total, currency)}
          </td>
        </tr>"""

    # Special requests
    special_block = ""
    if data.get("special_requests"):
        special_block = f"""
        <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;
                    padding:14px 18px;margin-bottom:20px">
          <p style="font-size:11px;font-weight:700;text-transform:uppercase;
                    letter-spacing:.08em;color:#92400e;margin:0 0 6px">
            Special Requests
          </p>
          <p style="font-size:13px;color:#92400e;margin:0;line-height:1.6">
            {data["special_requests"]}
          </p>
        </div>"""

    # Reply mailto
    reply_subj = urllib.parse.quote(
        f"Re: Booking Request — {data.get('property_name', 'Property')} "
        f"({data.get('reference', '')})"
    )
    reply_body = urllib.parse.quote(
        f"Hi {data.get('guest_name')},\n\n"
        f"Thank you for your booking request for "
        f"{data.get('property_name', 'the property')}.\n\n"
        f"Booking Reference: {data.get('reference')}\n"
        f"Check-in:  {data.get('check_in')}\n"
        f"Check-out: {data.get('check_out')}\n"
        f"Guests:    {_guest_str(data)}\n"
        f"Est. Total: {_fmt(final_total, currency)}\n\n"
        f"[YOUR MESSAGE HERE]\n\n"
        f"Payment instructions:\n[ADD PAYMENT DETAILS]\n\n"
        f"Kind regards,\nThe {BUSINESS_NAME} Team"
    )
    reply_href = (
        f"mailto:{data.get('guest_email')}"
        f"?subject={reply_subj}&body={reply_body}"
    )

    # WhatsApp button
    wa_btn = ""
    phone = "".join(c for c in (data.get("guest_phone") or "") if c.isdigit())
    if phone:
        wa_msg = (
            f"Hi {data.get('guest_name')}, thanks for your booking request for "
            f"{data.get('property_name', 'the property')} "
            f"({data.get('check_in')} → {data.get('check_out')}). "
            f"Ref: {data.get('reference')}. "
            f"We're reviewing your request and will be in touch shortly!"
        )
        wa_btn = f"""
        <a href="https://wa.me/{phone}?text={urllib.parse.quote(wa_msg)}"
           style="display:block;background:#25d366;color:#fff;text-decoration:none;
                  font-size:14px;font-weight:600;padding:13px 24px;border-radius:10px;
                  text-align:center;margin-top:10px">
          💬 &nbsp;WhatsApp Guest
        </a>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><title>New Booking Request</title></head>
<body style="margin:0;padding:0;background:#f4f1ec;font-family:'Segoe UI',Arial,sans-serif">
<div style="max-width:620px;margin:40px auto;background:#fff;border-radius:16px;
            overflow:hidden;box-shadow:0 4px 24px rgba(15,25,35,.1)">

  <!-- Header -->
  <div style="background:#0f1923;padding:24px 32px;
              display:flex;align-items:center;justify-content:space-between">
    <div>
      <div style="font-family:Georgia,serif;font-size:20px;font-weight:600;
                  color:#fff">{BUSINESS_NAME}</div>
      <div style="font-size:11px;color:rgba(255,255,255,.4);margin-top:3px;
                  text-transform:uppercase;letter-spacing:.12em">Admin Notification</div>
    </div>
    <div style="background:rgba(201,168,76,.15);border:1px solid rgba(201,168,76,.3);
                border-radius:999px;padding:5px 14px;font-size:12px;
                font-weight:600;color:#c9a84c">
      📩 New Request
    </div>
  </div>

  {promo_banner}

  <div style="padding:28px 32px">

    <h2 style="margin:0 0 6px;font-family:Georgia,serif;font-size:22px;
               font-weight:500;color:#0f1923">New Booking Request</h2>
    <p style="margin:0 0 24px;font-size:13px;color:#7a8a97">
      Ref:&nbsp;<strong style="color:#0f1923;font-family:monospace">
      {data.get("reference", "—")}</strong>
      &nbsp;·&nbsp; {data.get("submitted_at", "Just now")}
    </p>

    <!-- Property card -->
    <div style="background:#f4f1ec;border-radius:10px;padding:16px 20px;margin-bottom:20px">
      <p style="font-size:11px;font-weight:700;text-transform:uppercase;
                letter-spacing:.1em;color:#7a8a97;margin:0 0 5px">Property</p>
      <p style="font-size:17px;font-weight:600;color:#0f1923;margin:0 0 4px;
                font-family:Georgia,serif">
        {data.get("property_name", "—")}
      </p>
      <p style="font-size:13px;color:#7a8a97;margin:0 0 10px">
        📍 {data.get("property_location") or "Location not specified"}
      </p>
      <a href="{data.get("property_url", "#")}"
         style="font-size:12px;color:#c9a84c;font-weight:600;text-decoration:none">
        View property on site →
      </a>
    </div>

    <!-- Guest details -->
    <div style="background:#f4f1ec;border-radius:10px;padding:16px 20px;margin-bottom:20px">
      <p style="font-size:11px;font-weight:700;text-transform:uppercase;
                letter-spacing:.1em;color:#7a8a97;margin:0 0 12px">Guest Details</p>
      <table style="width:100%;border-collapse:collapse">
        <tr>
          <td style="padding:5px 0;font-size:13px;color:#7a8a97;width:110px">Name</td>
          <td style="padding:5px 0;font-size:13px;font-weight:600;color:#0f1923">
            {data.get("guest_name", "—")}
          </td>
        </tr>
        <tr>
          <td style="padding:5px 0;font-size:13px;color:#7a8a97">Email</td>
          <td style="padding:5px 0;font-size:13px">
            <a href="mailto:{data.get("guest_email", "")}"
               style="color:#c9a84c;text-decoration:none">
              {data.get("guest_email", "—")}
            </a>
          </td>
        </tr>
        <tr>
          <td style="padding:5px 0;font-size:13px;color:#7a8a97">Phone</td>
          <td style="padding:5px 0;font-size:13px;color:#0f1923">
            {data.get("guest_phone") or "—"}
          </td>
        </tr>
        <tr>
          <td style="padding:5px 0;font-size:13px;color:#7a8a97">Guests</td>
          <td style="padding:5px 0;font-size:13px;color:#0f1923">
            {_guest_str(data)}
          </td>
        </tr>
      </table>
    </div>

    <!-- Dates -->
    <div style="display:grid;grid-template-columns:1fr 1fr auto;gap:10px;margin-bottom:20px">
      <div style="background:#0f1923;border-radius:10px;padding:14px 16px">
        <p style="font-size:10px;text-transform:uppercase;letter-spacing:.1em;
                  color:rgba(255,255,255,.4);margin:0 0 4px">Check-in</p>
        <p style="font-size:17px;font-family:Georgia,serif;font-weight:500;
                  color:#fff;margin:0">{data.get("check_in", "—")}</p>
      </div>
      <div style="background:#0f1923;border-radius:10px;padding:14px 16px">
        <p style="font-size:10px;text-transform:uppercase;letter-spacing:.1em;
                  color:rgba(255,255,255,.4);margin:0 0 4px">Check-out</p>
        <p style="font-size:17px;font-family:Georgia,serif;font-weight:500;
                  color:#fff;margin:0">{data.get("check_out", "—")}</p>
      </div>
      <div style="background:#1a2c3d;border-radius:10px;padding:14px 16px;
                  text-align:center;min-width:64px">
        <p style="font-size:10px;text-transform:uppercase;letter-spacing:.1em;
                  color:rgba(255,255,255,.4);margin:0 0 4px">Nights</p>
        <p style="font-size:22px;font-family:Georgia,serif;font-weight:500;
                  color:#c9a84c;margin:0">{data.get("nights", "?")}</p>
      </div>
    </div>

    <!-- Price -->
    <div style="background:#f4f1ec;border-radius:10px;padding:16px 20px;margin-bottom:20px">
      <p style="font-size:11px;font-weight:700;text-transform:uppercase;
                letter-spacing:.1em;color:#7a8a97;margin:0 0 12px">Price Breakdown</p>
      <table style="width:100%;border-collapse:collapse">{breakdown}</table>
    </div>

    {special_block}

    <!-- CTAs -->
    <a href="{reply_href}"
       style="display:block;background:#c9a84c;color:#0f1923;text-decoration:none;
              font-size:15px;font-weight:700;padding:14px 24px;border-radius:10px;
              text-align:center;letter-spacing:.02em">
      ✉ &nbsp;Reply to Guest
    </a>
    {wa_btn}
    <a href="{data.get("property_url", "#")}"
       style="display:block;background:#f4f1ec;color:#0f1923;text-decoration:none;
              font-size:14px;font-weight:500;padding:12px 24px;border-radius:10px;
              text-align:center;border:1.5px solid rgba(15,25,35,.12);margin-top:10px">
      🏠 &nbsp;View Property on Site
    </a>

  </div>

  <!-- Footer -->
  <div style="padding:16px 32px;border-top:1px solid #e9e5dd;
              display:flex;justify-content:space-between;align-items:center">
    <span style="font-size:12px;color:#7a8a97">{BUSINESS_NAME} Admin</span>
    <span style="font-size:11px;color:#b0bec5">Automated notification</span>
  </div>
</div>
</body>
</html>"""


# ── Guest confirmation HTML ───────────────────────────────────────────────────

def _build_guest_html(data: dict) -> str:
    currency    = data.get("currency", "NGN")
    final_total = float(data.get("estimated_total") or 0)
    disc_pct    = float(data.get("discount_percent") or 0)

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><title>Booking Request Received</title></head>
<body style="margin:0;padding:0;background:#f4f1ec;font-family:'Segoe UI',Arial,sans-serif">
<div style="max-width:560px;margin:40px auto;background:#fff;border-radius:16px;
            overflow:hidden;box-shadow:0 4px 24px rgba(15,25,35,.1)">

  <div style="background:#0f1923;padding:24px 32px;text-align:center">
    <div style="font-family:Georgia,serif;font-size:20px;font-weight:600;
                color:#fff">{BUSINESS_NAME}</div>
  </div>

  <div style="padding:32px">

    <div style="width:56px;height:56px;background:#ecfdf5;border:2px solid #a7f3d0;
                border-radius:50%;margin:0 auto 18px;text-align:center;
                line-height:56px;font-size:24px">✓</div>

    <h2 style="text-align:center;margin:0 0 8px;font-family:Georgia,serif;
               font-size:21px;font-weight:500;color:#065f46">
      Request Received!
    </h2>
    <p style="text-align:center;color:#7a8a97;font-size:13px;margin:0 0 28px">
      We've got your booking request and will be in touch within a few hours.
    </p>

    <!-- Summary -->
    <div style="background:#f4f1ec;border-radius:12px;padding:18px 20px;margin-bottom:20px">
      <p style="font-size:11px;font-weight:700;text-transform:uppercase;
                letter-spacing:.1em;color:#7a8a97;margin:0 0 14px">
        Your Booking Summary
      </p>
      <table style="width:100%;border-collapse:collapse">
        <tr>
          <td style="padding:5px 0;font-size:13px;color:#7a8a97;width:120px">Property</td>
          <td style="padding:5px 0;font-size:13px;font-weight:600;color:#0f1923">
            {data.get("property_name", "—")}
          </td>
        </tr>
        <tr>
          <td style="padding:5px 0;font-size:13px;color:#7a8a97">Reference</td>
          <td style="padding:5px 0;font-size:13px;font-weight:600;
                     color:#0f1923;font-family:monospace">
            {data.get("reference", "—")}
          </td>
        </tr>
        <tr>
          <td style="padding:5px 0;font-size:13px;color:#7a8a97">Check-in</td>
          <td style="padding:5px 0;font-size:13px;color:#0f1923">
            {data.get("check_in", "—")}
          </td>
        </tr>
        <tr>
          <td style="padding:5px 0;font-size:13px;color:#7a8a97">Check-out</td>
          <td style="padding:5px 0;font-size:13px;color:#0f1923">
            {data.get("check_out", "—")}
          </td>
        </tr>
        <tr>
          <td style="padding:5px 0;font-size:13px;color:#7a8a97">Guests</td>
          <td style="padding:5px 0;font-size:13px;color:#0f1923">
            {_guest_str(data)}
          </td>
        </tr>
        <tr style="border-top:1px solid #e2e8f0">
          <td style="padding:10px 0 0;font-size:13px;color:#7a8a97">Est. Total</td>
          <td style="padding:10px 0 0;font-size:16px;font-weight:700;color:#0f1923">
            {_fmt(final_total, currency)}
            {"<span style='font-size:12px;color:#7c3aed;margin-left:6px'>" + f"({int(disc_pct)}% discount applied)" + "</span>" if disc_pct else ""}
          </td>
        </tr>
      </table>
    </div>

    <p style="font-size:13px;color:#7a8a97;line-height:1.7;margin:0 0 20px">
      <strong style="color:#0f1923">What happens next?</strong><br/>
      Our team will confirm availability and send you payment instructions.
      No payment has been collected yet.
    </p>

    <p style="font-size:12px;color:#b0bec5;margin:0">
      Questions? Email
      <a href="mailto:{ADMIN_EMAIL}" style="color:#c9a84c">{ADMIN_EMAIL}</a>
    </p>

  </div>

  <div style="padding:16px 32px;border-top:1px solid #e9e5dd;text-align:center">
    <span style="font-size:12px;color:#b0bec5">© {BUSINESS_NAME}</span>
  </div>
</div>
</body>
</html>"""


# ── Public send functions ─────────────────────────────────────────────────────

def send_admin_notification(data: dict) -> bool:
    """
    Sends the admin notification email.
    Accepts the raw dict returned by Supabase after insert.
    Non-fatal — logs on failure but never raises.
    """
    try:
        resend.Emails.send({
            "from":    FROM_ADDRESS,
            "to":      [ADMIN_EMAIL],
            "subject": (
                f"📩 New Booking Request — "
                f"{data.get('property_name', 'Property')} "
                f"({data.get('reference', '')})"
            ),
            "html": _build_admin_html(data),
        })
        return True
    except Exception as exc:
        print(f"[email] Admin notification failed: {exc}")
        return False


def send_guest_confirmation(data: dict) -> bool:
    """
    Sends the guest confirmation email.
    Accepts the raw dict returned by Supabase after insert.
    Non-fatal — logs on failure but never raises.
    """
    try:
        resend.Emails.send({
            "from":    FROM_ADDRESS,
            "to":      [data["guest_email"]],
            "subject": (
                f"We received your booking request — "
                f"{data.get('property_name', '')}"
            ),
            "html": _build_guest_html(data),
        })
        return True
    except Exception as exc:
        print(f"[email] Guest confirmation failed: {exc}")
        return False