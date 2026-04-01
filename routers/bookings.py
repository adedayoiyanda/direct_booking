"""
routers/bookings.py  —  Booking creation & Paystack webhook handler.

POST /bookings                    →  Create a pending booking, return Paystack ref
POST /paystack-webhook            →  Validate signature, confirm booking, send email
"""
import hashlib
import hmac
import logging
from decimal import Decimal
from uuid import UUID, uuid4

import resend
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr

from config import settings
from database import db, public_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Bookings"])

# Initialise Resend SDK once
resend.api_key = settings.resend_api_key


# ── Schemas ──────────────────────────────────────────────────

class BookingRequest(BaseModel):
    property_id: UUID
    guest_name: str
    guest_email: EmailStr
    check_in: str          # ISO date string: "YYYY-MM-DD"
    check_out: str
    num_guests: int = 1


class BookingResponse(BaseModel):
    booking_id: UUID
    payment_ref: str
    total_price: Decimal
    paystack_public_key: str


# ── Helpers ──────────────────────────────────────────────────

def _calculate_total(price_per_night: Decimal, check_in: str, check_out: str) -> Decimal:
    from datetime import date
    ci = date.fromisoformat(check_in)
    co = date.fromisoformat(check_out)
    nights = (co - ci).days
    if nights <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-out must be after check-in.",
        )
    return price_per_night * nights


def _verify_paystack_signature(payload: bytes, signature: str) -> bool:
    """HMAC-SHA512 verification against Paystack webhook secret."""
    expected = hmac.new(
        settings.paystack_webhook_secret.encode(),
        payload,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _send_confirmation_email(booking: dict, property_name: str) -> None:
    """Send a booking confirmation via Resend."""
    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [booking["guest_email"]],
            "subject": f"✅ Booking Confirmed — {property_name}",
            "html": f"""
            <div style="font-family:sans-serif;max-width:560px;margin:auto">
              <h2 style="color:#1a1a2e">Your booking is confirmed! 🎉</h2>
              <p>Hi {booking['guest_name']},</p>
              <p>We're delighted to confirm your reservation for
                 <strong>{property_name}</strong>.</p>
              <table style="border-collapse:collapse;width:100%;margin:1rem 0">
                <tr><td style="padding:8px;border:1px solid #e2e8f0"><b>Check-in</b></td>
                    <td style="padding:8px;border:1px solid #e2e8f0">{booking['check_in']}</td></tr>
                <tr><td style="padding:8px;border:1px solid #e2e8f0"><b>Check-out</b></td>
                    <td style="padding:8px;border:1px solid #e2e8f0">{booking['check_out']}</td></tr>
                <tr><td style="padding:8px;border:1px solid #e2e8f0"><b>Guests</b></td>
                    <td style="padding:8px;border:1px solid #e2e8f0">{booking['num_guests']}</td></tr>
                <tr><td style="padding:8px;border:1px solid #e2e8f0"><b>Total Paid</b></td>
                    <td style="padding:8px;border:1px solid #e2e8f0">
                      ₦{booking['total_price']:,.2f}</td></tr>
                <tr><td style="padding:8px;border:1px solid #e2e8f0"><b>Reference</b></td>
                    <td style="padding:8px;border:1px solid #e2e8f0">{booking['payment_ref']}</td></tr>
              </table>
              <p>We look forward to hosting you. Reply to this email with any questions.</p>
              <hr style="border:none;border-top:1px solid #e2e8f0;margin:2rem 0"/>
              <p style="color:#64748b;font-size:12px">
                This is an automated confirmation. Please keep it for your records.</p>
            </div>
            """,
        })
        logger.info("Confirmation email sent to %s", booking["guest_email"])
    except Exception as exc:
        # Email failure must NOT break the webhook acknowledgement
        logger.error("Resend email failed: %s", exc)


# ── Routes ───────────────────────────────────────────────────

@router.post("/bookings", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(payload: BookingRequest):
    """
    1. Fetch property price from DB.
    2. Calculate total.
    3. Generate a unique Paystack reference.
    4. Insert a 'pending' booking row.
    5. Return the ref + public Paystack key for the inline popup.
    """
    # Fetch property
    prop_result = (
        public_db.table("properties")
        .select("id, name, price_per_night, is_available")
        .eq("id", str(payload.property_id))
        .single()
        .execute()
    )
    if not prop_result.data:
        raise HTTPException(status_code=404, detail="Property not found.")

    prop = prop_result.data
    if not prop["is_available"]:
        raise HTTPException(status_code=409, detail="Property is no longer available.")

    total = _calculate_total(
        Decimal(str(prop["price_per_night"])),
        payload.check_in,
        payload.check_out,
    )

    payment_ref = f"STAY-{uuid4().hex[:12].upper()}"
    booking_id = str(uuid4())

    db.table("bookings").insert({
        "id": booking_id,
        "property_id": str(payload.property_id),
        "guest_name": payload.guest_name,
        "guest_email": payload.guest_email,
        "check_in": payload.check_in,
        "check_out": payload.check_out,
        "num_guests": payload.num_guests,
        "total_price": float(total),
        "payment_ref": payment_ref,
        "status": "pending",
    }).execute()

    return BookingResponse(
        booking_id=UUID(booking_id),
        payment_ref=payment_ref,
        total_price=total,
        # Expose only the *public* Paystack key to the frontend
        paystack_public_key=settings.paystack_secret_key.replace("sk_", "pk_"),
    )


@router.post("/paystack-webhook", status_code=status.HTTP_200_OK)
async def paystack_webhook(request: Request):
    """
    Paystack calls this after every payment event.

    Security:
      • Validates x-paystack-signature (HMAC-SHA512) before touching the DB.
      • Only acts on 'charge.success' events.
      • Idempotent: repeated calls for the same ref are safe.
    """
    raw_body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    if not _verify_paystack_signature(raw_body, signature):
        logger.warning("Invalid Paystack signature — possible spoofed webhook.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bad signature.")

    import json
    event = json.loads(raw_body)

    if event.get("event") != "charge.success":
        # Acknowledge other events without acting
        return {"status": "ignored"}

    data = event.get("data", {})
    payment_ref = data.get("reference")

    if not payment_ref:
        raise HTTPException(status_code=400, detail="Missing reference in payload.")

    # Fetch the pending booking
    booking_result = (
        db.table("bookings")
        .select("*, properties(name)")
        .eq("payment_ref", payment_ref)
        .single()
        .execute()
    )

    if not booking_result.data:
        logger.warning("Webhook ref %s not found in DB.", payment_ref)
        return {"status": "not_found"}

    booking = booking_result.data

    if booking["status"] == "confirmed":
        # Already processed — idempotent response
        return {"status": "already_confirmed"}

    # Confirm the booking
    db.table("bookings").update({"status": "confirmed"}).eq("payment_ref", payment_ref).execute()

    property_name = (booking.get("properties") or {}).get("name", "your property")
    await _send_confirmation_email(booking, property_name)

    logger.info("Booking %s confirmed for %s", booking["id"], booking["guest_email"])
    return {"status": "confirmed"}
