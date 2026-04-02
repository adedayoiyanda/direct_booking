"""
routers/properties.py  —  Public properties listing endpoint.
GET /properties                    →  All available properties (public)
GET /properties/{id}               →  Single property detail (public)
GET /properties/{id}/booked-dates  →  Booked date ranges for calendar (public)
"""
from uuid import UUID
from typing import Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from decimal import Decimal
from database import public_db

router = APIRouter(prefix="/properties", tags=["Properties"])


class Property(BaseModel):
    id:              UUID
    name:            str
    description:     Optional[str]                  = None
    price_per_night: Decimal
    image_url:       Optional[str]                  = None
    location:        Optional[str]                  = None
    max_guests:      int
    amenities:       Optional[list[str]]            = []
    is_available:    bool
    currency:        Optional[str]                  = "NGN"
    featured_on:     Optional[list[str]]            = []
    images:          Optional[list[dict[str, Any]]] = []
    # ── Promo / Discount ─────────────────────────
    discount_percent: Optional[Decimal]             = Decimal("0")
    promo_label:      Optional[str]                 = None
    promo_expires:    Optional[str]                 = None
    promo_note:       Optional[str]                 = None


# ── Column list sent to Supabase ──────────────────────────────────────────────
PROPERTY_FIELDS = (
    "id, name, description, price_per_night, image_url, "
    "location, max_guests, amenities, is_available, "
    "currency, featured_on, images, "
    "discount_percent, promo_label, promo_expires, promo_note"
)


@router.get("", response_model=list[Property])
def list_properties():
    """Returns all available properties including promo/discount data."""
    result = (
        public_db.table("properties")
        .select(PROPERTY_FIELDS)
        .eq("is_available", True)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data


@router.get("/{property_id}", response_model=Property)
def get_property(property_id: UUID):
    """Returns a single available property by ID."""
    result = (
        public_db.table("properties")
        .select(PROPERTY_FIELDS)
        .eq("id", str(property_id))
        .eq("is_available", True)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Property not found.")
    return result.data


@router.get("/{property_id}/booked-dates")
def get_booked_dates(property_id: UUID):
    """
    Returns confirmed/pending bookings for a property.
    Used by the frontend availability calendar to mark booked dates in red.
    """
    result = (
        public_db.table("bookings")
        .select("check_in, check_out")
        .eq("property_id", str(property_id))
        .in_("status", ["confirmed", "pending"])
        .execute()
    )
    return result.data