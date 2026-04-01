"""
routers/config.py  —  Public site branding endpoint.

GET /config  →  Returns the first row of site_config (always exists after seed).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import public_db

router = APIRouter(prefix="/config", tags=["Config"])


class SiteConfig(BaseModel):
    business_name: str
    primary_color: str
    accent_color: str
    bg_color: Optional[str] = None
    surface_color: Optional[str] = None
    contact_email: str
    hero_text: str
    hero_subtext: str
    logo_url: Optional[str] = None
    footer_text: str
    
    # <--- NEW: Hero Background fields --->
    hero_bg_type: Optional[str] = None
    hero_bg_color: Optional[str] = None
    hero_bg_media_url: Optional[str] = None


@router.get("", response_model=SiteConfig)
def get_site_config():
    """
    Returns public branding/copy used by the frontend to theme itself.
    The anon-key client is used — RLS allows public SELECT on site_config.
    """
    result = (
        public_db.table("site_config")
        .select("*")  # Changed to "*" so it automatically grabs the new columns
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Site config not found.")

    return result.data[0]