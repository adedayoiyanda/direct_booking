"""
routers/admin.py  —  Protected admin endpoints.
All routes require a valid JWT (via get_current_admin dependency).
POST   /admin/login                 →  Username + password → JWT
GET    /admin/config                →  Read full site config
PUT    /admin/config                →  Update site config (colors, copy, etc.)
GET    /admin/properties            →  List ALL properties (incl. unavailable)
POST   /admin/properties            →  Create new property
PUT    /admin/properties/{id}       →  Update a property
DELETE /admin/properties/{id}       →  Soft-delete (sets is_available = false)
POST   /admin/upload-image          →  Upload image to Supabase Storage → returns URL
GET    /admin/bookings              →  List all bookings with filters
"""
import uuid
from typing import Annotated, Optional, List, Dict, Any
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from auth import create_access_token, get_current_admin, verify_admin_credentials
from config import settings
from database import db

router = APIRouter(prefix="/admin", tags=["Admin"])
AdminUser = Annotated[dict, Depends(get_current_admin)]
STORAGE_BUCKET = "property-images"


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def admin_login(payload: LoginRequest):
    if not verify_admin_credentials(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
    token = create_access_token({"sub": payload.username, "role": "admin"})
    return {"access_token": token, "token_type": "bearer"}


# ── Site Config ───────────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    business_name:     Optional[str] = None
    primary_color:     Optional[str] = None
    accent_color:      Optional[str] = None
    bg_color:          Optional[str] = None
    surface_color:     Optional[str] = None
    contact_email:     Optional[str] = None
    hero_text:         Optional[str] = None
    hero_subtext:      Optional[str] = None
    logo_url:          Optional[str] = None
    footer_text:       Optional[str] = None
    hero_bg_type:      Optional[str] = None
    hero_bg_color:     Optional[str] = None
    hero_bg_media_url: Optional[str] = None

@router.get("/config")
def admin_get_config(_: AdminUser):
    result = db.table("site_config").select("*").limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Config not found.")
    return result.data[0]

@router.put("/config")
def admin_update_config(payload: ConfigUpdate, _: AdminUser):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    config = db.table("site_config").select("id").limit(1).execute()
    if not config.data:
        raise HTTPException(status_code=404, detail="Config not found.")
    row_id = config.data[0]["id"]
    result = db.table("site_config").update(updates).eq("id", row_id).execute()
    if not result.data:
        raise HTTPException(
            status_code=400,
            detail="Database rejected the save. Check RLS policies.",
        )
    return {"message": "Config updated.", "data": result.data[0]}


# ── Properties ────────────────────────────────────────────────────────────────

class PropertyCreate(BaseModel):
    name:             str
    description:      Optional[str]            = None
    price_per_night:  float
    image_url:        Optional[str]            = None
    images:           List[Dict[str, Any]]     = []
    location:         Optional[str]            = None
    max_guests:       int                      = 2
    amenities:        Optional[List[str]]      = []
    is_available:     bool                     = True
    currency:         str                      = "NGN"
    featured_on:      List[str]                = []
    # ── Promo / Discount fields (new) ────────────────────────
    discount_percent: float                    = 0
    promo_label:      Optional[str]            = None
    promo_expires:    Optional[str]            = None   # "YYYY-MM-DD"
    promo_note:       Optional[str]            = None   # internal only


class PropertyUpdate(PropertyCreate):
    name:            Optional[str]   = None
    price_per_night: Optional[float] = None

@router.get("/properties")
def admin_list_properties(_: AdminUser):
    result = (
        db.table("properties")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data

@router.post("/properties", status_code=status.HTTP_201_CREATED)
def admin_create_property(payload: PropertyCreate, _: AdminUser):
    result = db.table("properties").insert(payload.model_dump()).execute()
    return result.data[0]

@router.put("/properties/{property_id}")
def admin_update_property(property_id: str, payload: PropertyUpdate, _: AdminUser):
    updates = {
        k: v
        for k, v in payload.model_dump(exclude_unset=True).items()
        if v is not None
    }
    # discount_percent = 0 is valid (disabling a discount), so don't filter it out
    if "discount_percent" in payload.model_dump(exclude_unset=True):
        updates["discount_percent"] = payload.discount_percent

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    result = (
        db.table("properties")
        .update(updates)
        .eq("id", property_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Property not found.")
    return result.data[0]

@router.delete("/properties/{property_id}")
def admin_delete_property(property_id: str, _: AdminUser):
    db.table("properties").update({"is_available": False}).eq("id", property_id).execute()
    return {"message": "Property hidden from public listing."}


# ── Image Upload ──────────────────────────────────────────────────────────────

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_MB   = 25

@router.post("/upload-image")
async def upload_property_image(file: UploadFile = File(...), _: AdminUser = None):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_TYPES)}",
        )
    contents = await file.read()
    if len(contents) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds {MAX_SIZE_MB}MB limit.")
    ext         = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "jpg"
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    db.storage.from_(STORAGE_BUCKET).upload(
        path=unique_name,
        file=contents,
        file_options={"content-type": file.content_type},
    )
    public_url = db.storage.from_(STORAGE_BUCKET).get_public_url(unique_name)
    return {"url": public_url, "filename": unique_name}


# ── Bookings ──────────────────────────────────────────────────────────────────

@router.get("/bookings")
def admin_list_bookings(
    _: AdminUser,
    status:      Optional[str] = None,
    property_id: Optional[str] = None,
):
    query = (
        db.table("bookings")
        .select("*, properties(name)")
        .order("created_at", desc=True)
    )
    if status:
        query = query.eq("status", status)
    if property_id:
        query = query.eq("property_id", property_id)
    return query.execute().data