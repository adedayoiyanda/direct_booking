-- ============================================================
-- BOOKING SITE SCHEMA  |  Run this in Supabase SQL Editor
-- ============================================================

-- 1. SITE CONFIGURATION
-- Stores all branding, colors, and copy manageable by admin
CREATE TABLE IF NOT EXISTS site_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_name   TEXT NOT NULL DEFAULT 'My Booking Co.',
    primary_color   TEXT NOT NULL DEFAULT '#2563eb',
    accent_color    TEXT NOT NULL DEFAULT '#f59e0b',
    contact_email   TEXT NOT NULL DEFAULT 'hello@example.com',
    hero_text       TEXT NOT NULL DEFAULT 'Find Your Perfect Stay',
    hero_subtext    TEXT NOT NULL DEFAULT 'Discover handpicked properties for every occasion.',
    logo_url        TEXT,
    footer_text     TEXT NOT NULL DEFAULT '© 2025. All rights reserved.',
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Seed one default row so GET /config never returns empty
INSERT INTO site_config (business_name, primary_color, contact_email, hero_text)
VALUES ('StayEase', '#1a1a2e', 'hello@stayease.com', 'Find Your Perfect Stay')
ON CONFLICT DO NOTHING;

-- 2. PROPERTIES
-- Each bookable listing managed from the admin dashboard
CREATE TABLE IF NOT EXISTS properties (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    description     TEXT,
    price_per_night NUMERIC(10, 2) NOT NULL,
    image_url       TEXT,
    location        TEXT,
    max_guests      INT DEFAULT 2,
    amenities       TEXT[],          -- e.g. ARRAY['WiFi','Pool','AC']
    is_available    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 3. BOOKINGS
-- Created on checkout, updated by Paystack webhook
CREATE TABLE IF NOT EXISTS bookings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id     UUID NOT NULL REFERENCES properties(id) ON DELETE RESTRICT,
    guest_name      TEXT NOT NULL,
    guest_email     TEXT NOT NULL,
    check_in        DATE NOT NULL,
    check_out       DATE NOT NULL,
    num_guests      INT NOT NULL DEFAULT 1,
    total_price     NUMERIC(10, 2) NOT NULL,
    payment_ref     TEXT UNIQUE,     -- Paystack reference
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'confirmed', 'cancelled', 'refunded')),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ── Indexes ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_bookings_payment_ref  ON bookings(payment_ref);
CREATE INDEX IF NOT EXISTS idx_bookings_property_id  ON bookings(property_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status       ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_properties_available  ON properties(is_available);

-- ── Auto-update updated_at ───────────────────────────────────
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$;

CREATE TRIGGER trg_properties_updated
    BEFORE UPDATE ON properties
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TRIGGER trg_bookings_updated
    BEFORE UPDATE ON bookings
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ── Row Level Security ───────────────────────────────────────
-- Public: read-only for config & available properties
ALTER TABLE site_config  ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties   ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings     ENABLE ROW LEVEL SECURITY;

-- site_config: anyone can read; only service role can write
CREATE POLICY "public_read_config"
    ON site_config FOR SELECT USING (true);

-- properties: anyone can read available ones; service role writes
CREATE POLICY "public_read_available_properties"
    ON properties FOR SELECT USING (is_available = true);

-- bookings: guests can insert; service role manages everything
CREATE POLICY "guests_can_insert_booking"
    ON bookings FOR INSERT WITH CHECK (true);

-- ── Storage bucket (run separately or via Dashboard) ─────────
-- INSERT INTO storage.buckets (id, name, public)
-- VALUES ('property-images', 'property-images', true);
