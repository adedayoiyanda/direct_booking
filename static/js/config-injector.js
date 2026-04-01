/**
 * config-injector.js
 * ─────────────────────────────────────────────────────────────
 * Fetches /config on DOMContentLoaded and:
 *   1. Applies CSS custom properties for live theming
 *   2. Injects business_name, hero_text, and other copy into the DOM
 *   3. Sets the page <title> and favicon fallback
 *   4. Dispatches a "configLoaded" event so other modules can react
 *
 * Usage:  import { configInjector } from './config-injector.js';
 *         // OR include this script with defer — it self-initialises.
 * ─────────────────────────────────────────────────────────────
 */

const CONFIG_ENDPOINT = "/config";

// ── Colour utilities ────────────────────────────────────────

/**
 * Derive a readable foreground colour (black or white) for any hex bg.
 * Uses the W3C relative luminance formula.
 */
function contrastColor(hex) {
  const clean = hex.replace("#", "");
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.5 ? "#1a1a2e" : "#ffffff";
}

/**
 * Lighten or darken a hex colour by a given amount (-255 to 255).
 */
function shiftColor(hex, amount) {
  const clean = hex.replace("#", "");
  const clamp = (v) => Math.max(0, Math.min(255, v));
  const r = clamp(parseInt(clean.slice(0, 2), 16) + amount);
  const g = clamp(parseInt(clean.slice(2, 4), 16) + amount);
  const b = clamp(parseInt(clean.slice(4, 6), 16) + amount);
  return `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

// ── Theme applicator ────────────────────────────────────────

/**
 * Writes all CSS custom properties derived from the config onto :root.
 * Components only need to reference var(--color-primary) etc.
 *
 * @param {object} config  Response from GET /config
 */
function applyTheme(config) {
  const root = document.documentElement;
  const primary = config.primary_color || "#0f1923";
  const accent  = config.accent_color  || "#c9a84c";
  const bg      = config.bg_color      || "#f7f4ef";
  const surface = config.surface_color || "#ffffff";

  const vars = {
    "--color-primary":        primary,
    "--color-primary-hover":  shiftColor(primary, 30),
    "--color-primary-dark":   shiftColor(primary, -30),
    "--color-primary-text":   contrastColor(primary),
    "--color-accent":         accent,
    "--color-accent-hover":   shiftColor(accent, 20),
    "--color-accent-text":    contrastColor(accent),
    "--color-bg":             bg,
    "--color-surface":        surface,
  };

  for (const [prop, value] of Object.entries(vars)) {
    root.style.setProperty(prop, value);
  }
}

  

// ── DOM injector ─────────────────────────────────────────────

/**
 * Finds elements with data-config="<field>" and fills their textContent,
 * or their src/href for special fields.
 *
 * Markup examples:
 *   <h1 data-config="business_name"></h1>
 *   <p  data-config="hero_text"></p>
 *   <img data-config="logo_url" alt="logo" />
 *   <a  data-config-href="contact_email"></a>
 *
 * @param {object} config
 */
function injectContent(config) {
  // Text content injection
  document.querySelectorAll("[data-config]").forEach((el) => {
    const field = el.dataset.config;
    const value = config[field];
    if (value === undefined || value === null) return;

    if (el.tagName === "IMG") {
      el.src = value;
      el.alt = config.business_name || "Logo";
    } else {
      el.textContent = value;
    }
  });

  // href injection (e.g. mailto: links)
  document.querySelectorAll("[data-config-href]").forEach((el) => {
    const field = el.dataset.configHref;
    const value = config[field];
    if (!value) return;

    if (field === "contact_email") {
      el.href = `mailto:${value}`;
      if (!el.textContent.trim()) el.textContent = value;
    } else {
      el.href = value;
    }
  });

  // HTML injection (rich text fields — use sparingly)
  document.querySelectorAll("[data-config-html]").forEach((el) => {
    const field = el.dataset.configHtml;
    const value = config[field];
    if (value) el.innerHTML = value;
  });
}

// ── Page metadata ────────────────────────────────────────────

function applyMetadata(config) {
  // Browser tab title
  if (config.business_name) {
    document.title = config.business_name;
  }

  // OG / meta description
  const metaDesc = document.querySelector('meta[name="description"]');
  if (metaDesc && config.hero_subtext) {
    metaDesc.setAttribute("content", config.hero_subtext);
  }

  // Favicon — use logo_url if it looks like an icon; fallback gracefully
  if (config.logo_url) {
    let favicon = document.querySelector('link[rel="icon"]');
    if (!favicon) {
      favicon = document.createElement("link");
      favicon.rel = "icon";
      document.head.appendChild(favicon);
    }
    favicon.href = config.logo_url;
  }
}

// ── Main initialiser ─────────────────────────────────────────

/**
 * Fetches /config, applies theme + content, and dispatches "configLoaded".
 * Call this once on DOMContentLoaded (done automatically below).
 *
 * @returns {Promise<object>}  The config object, in case callers need it.
 */
async function initConfigInjector() {
  try {
    const res = await fetch(CONFIG_ENDPOINT);
    if (!res.ok) throw new Error(`/config returned ${res.status}`);

    const config = await res.json();

    applyTheme(config);
    injectContent(config);
    applyMetadata(config);

    // Broadcast to sibling modules (gallery.js, etc.)
    document.dispatchEvent(
      new CustomEvent("configLoaded", { detail: config, bubbles: true })
    );

    return config;
  } catch (err) {
    console.error("[config-injector] Failed to load site config:", err);
    // Don't crash the page — silently continue with CSS defaults
    return null;
  }
}

// ── Auto-init ────────────────────────────────────────────────

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initConfigInjector);
} else {
  // Already parsed (e.g. script loaded with defer after DOM ready)
  initConfigInjector();
}

export { initConfigInjector, applyTheme, injectContent };
