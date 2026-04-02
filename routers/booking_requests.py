"""
routers/booking_requests.py
────────────────────────────
Drop into your existing  routers/  folder.

Uses your Supabase client directly (same pattern as your other routers)
— no SQLAlchemy, no ORM, no Base.

Endpoints:
  POST  /bookings/request                    — public, no auth
  GET   /admin/booking-requests              — admin auth required
  GET   /admin/booking-requests/{id}         — admin auth required
  PATCH /admin/booking-requests/{id}/status  — admin auth required
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field

# ── Same imports your other routers use ──────────────────────────────────────
from database import db                 # service-role Supabase client
from auth import get_current_admin      # your existing admin auth dependency
from services.email import (
    send_admin_notification,
    send_guest_confirmation,
)
# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter(tags=["Booking Requests"])

TABLE = "booking_requests"


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class BookingRequestCreate(BaseModel):
    # Identity
    reference:         str

    # Property
    property_id:       Optional[str]   = None
    property_name:     str
    property_location: Optional[str]   = None
    property_url:      Optional[str]   = None

    # Guest
    guest_name:        str
    guest_email:       EmailStr
    guest_phone:       Optional[str]   = None

    # Stay
    check_in:          str             # "YYYY-MM-DD"
    check_out:         str             # "YYYY-MM-DD"
    nights:            Optional[int]   = None
    adults:            int             = Field(default=1, ge=1)
    children:          int             = Field(default=0, ge=0)
    infants:           int             = Field(default=0, ge=0)
    total_guests:      Optional[int]   = None

    # Pricing
    price_per_night:   Optional[float] = None
    discount_percent:  float           = Field(default=0, ge=0, le=100)
    discount_amount:   float           = Field(default=0, ge=0)
    estimated_total:   Optional[float] = None
    currency:          str             = "NGN"

    # Promo
    promo_label:       Optional[str]   = None

    # Extra
    special_requests:  Optional[str]   = None
    submitted_at:      Optional[str]   = None  # ISO string from frontend


class StatusUpdate(BaseModel):
    status: str  # "new" | "reviewed" | "confirmed" | "cancelled"


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _row_not_found():
    raise HTTPException(status_code=404, detail="Booking request not found.")


def _db_error(msg: str, exc: Exception):
    """Log and raise a clean 500 for unexpected Supabase errors."""
    print(f"[booking_requests] {msg}: {exc}")
    raise HTTPException(status_code=500, detail=msg)


# ══════════════════════════════════════════════════════════════════════════════
# POST /bookings/request   (public — no auth)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/bookings/request",
    status_code=status.HTTP_201_CREATED,
    summary="Submit a booking request (public)",
)
def create_booking_request(payload: BookingRequestCreate):

    # ── Guard: reject duplicate reference ────────────────────────────────────
    try:
        existing = (
            db.table(TABLE)
            .select("id")
            .eq("reference", payload.reference)
            .execute()
        )
    except Exception as exc:
        _db_error("Failed to check for duplicate reference", exc)

    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A request with this reference already exists.",
        )

    # ── Build row dict ────────────────────────────────────────────────────────
    row = {
        "reference":         payload.reference,
        "property_id":       payload.property_id,       # UUID string or None
        "property_name":     payload.property_name,
        "property_location": payload.property_location,
        "property_url":      payload.property_url,
        "guest_name":        payload.guest_name,
        "guest_email":       payload.guest_email,
        "guest_phone":       payload.guest_phone,
        "check_in":          payload.check_in,           # "YYYY-MM-DD" → Supabase DATE
        "check_out":         payload.check_out,
        "nights":            payload.nights,
        "adults":            payload.adults,
        "children":          payload.children,
        "infants":           payload.infants,
        "total_guests":      payload.total_guests,
        "price_per_night":   payload.price_per_night,
        "discount_percent":  payload.discount_percent,
        "discount_amount":   payload.discount_amount,
        "estimated_total":   payload.estimated_total,
        "currency":          payload.currency,
        "promo_label":       payload.promo_label,
        "special_requests":  payload.special_requests,
        "submitted_at":      payload.submitted_at or datetime.utcnow().isoformat(),
        "status":            "new",
    }

    # Strip None values for fields Supabase will default (keeps insert clean)
    row = {k: v for k, v in row.items() if v is not None or k in (
        "property_id", "property_location", "property_url",
        "guest_phone", "promo_label", "special_requests",
        "price_per_night", "estimated_total", "nights", "total_guests",
    )}

    # ── Insert ────────────────────────────────────────────────────────────────
    try:
        result = db.table(TABLE).insert(row).execute()
    except Exception as exc:
        _db_error("Failed to insert booking request", exc)

    if not result.data:
        raise HTTPException(status_code=500, detail="Insert returned no data.")

    saved = result.data[0]

    # ── Send emails (non-fatal — request is already saved) ────────────────────
    send_admin_notification(saved)
    send_guest_confirmation(saved)

    return saved


# ══════════════════════════════════════════════════════════════════════════════
# GET /admin/booking-requests   (admin)
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/admin/booking-requests",
    summary="List all booking requests (admin)",
)
def list_booking_requests(
    status:  Optional[str] = Query(None, description="Filter: new|reviewed|confirmed|cancelled"),
    limit:   int           = Query(200,  ge=1, le=500),
    offset:  int           = Query(0,    ge=0),
    _:       dict          = Depends(get_current_admin),
):
    try:
        query = (
            db.table(TABLE)
            .select("*")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )
        if status:
            query = query.eq("status", status)

        result = query.execute()
    except Exception as exc:
        _db_error("Failed to fetch booking requests", exc)

    return result.data


# ══════════════════════════════════════════════════════════════════════════════
# GET /admin/booking-requests/{id}   (admin)
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/admin/booking-requests/{request_id}",
    summary="Get a single booking request (admin)",
)
def get_booking_request(
    request_id: str,
    _: dict = Depends(get_current_admin),
):
    try:
        result = (
            db.table(TABLE)
            .select("*")
            .eq("id", request_id)
            .execute()
        )
    except Exception as exc:
        _db_error("Failed to fetch booking request", exc)

    if not result.data:
        _row_not_found()

    return result.data[0]


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /admin/booking-requests/{id}/status   (admin)
# ══════════════════════════════════════════════════════════════════════════════

@router.patch(
    "/admin/booking-requests/{request_id}/status",
    summary="Update booking request status (admin)",
)
def update_status(
    request_id: str,
    payload:    StatusUpdate,
    _:          dict = Depends(get_current_admin),
):
    valid = {"new", "reviewed", "confirmed", "cancelled"}
    if payload.status not in valid:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of: {', '.join(sorted(valid))}",
        )

    try:
        result = (
            db.table(TABLE)
            .update({
                "status":     payload.status,
                "updated_at": datetime.utcnow().isoformat(),
            })
            .eq("id", request_id)
            .execute()
        )
    except Exception as exc:
        _db_error("Failed to update booking request status", exc)

    if not result.data:
        _row_not_found()

    return result.data[0]