"""
database.py  —  Supabase client factory.

Two clients are provided:
  • db        – service-role client (full access, server-side only)
  • public_db – anon-key client    (respects RLS, safe for public reads)
"""
from functools import lru_cache
from supabase import create_client, Client
from config import settings


@lru_cache
def get_db() -> Client:
    """Service-role Supabase client (bypasses RLS). Never expose this key."""
    return create_client(settings.supabase_url, settings.supabase_service_key)


@lru_cache
def get_public_db() -> Client:
    """Anon-key Supabase client (respects RLS). Safe for public data reads."""
    return create_client(settings.supabase_url, settings.supabase_anon_key)


# Convenience singletons imported across routers
db: Client = get_db()
public_db: Client = get_public_db()
