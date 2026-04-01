"""
routers/properties.py  —  Public properties listing endpoint.

GET /properties          →  All available properties (public)
GET /properties/{id}     →  Single property detail (public)
"""
from uuid import UUID
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from decimal import Decimal

from database import public_db

router = APIRouter(prefix="/properties", tags=["Properties"])


class Property(BaseModel):
    id: UUID
    name: str
    description: str | None
    price_per_night: Decimal
    image_url: str | None
    location: str | None
    max_guests: int
    amenities: list[str] | None
    is_available: bool
    # --- NEW FIELDS ADDED HERE ---
    currency: str | None = "NGN"
    featured_on: list[str] | None = []
    images: list[dict[str, Any]] | None = []


# --- ADDED NEW COLUMNS TO THE SELECT QUERY ---
PROPERTY_FIELDS = (
    "id, name, description, price_per_night, image_url, "
    "location, max_guests, amenities, is_available, "
    "currency, featured_on, images"
)


@router.get("", response_model=list[Property])
def list_properties():
    """
    Returns all properties where is_available = true.
    RLS on the public client enforces this automatically.
    """
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