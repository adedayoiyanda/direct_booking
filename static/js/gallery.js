/**
 * gallery.js
 * ─────────────────────────────────────────────────────────────
 * Loads properties from GET /properties and renders a booking
 * gallery with a modal that triggers the Paystack Inline Popup.
 *
 * Depends on:
 *   • config-injector.js  (fires "configLoaded" event)
 *   • Paystack inline JS  (loaded in HTML: https://js.paystack.co/v2/inline.js)
 * ─────────────────────────────────────────────────────────────
 */

const PROPERTIES_ENDPOINT = "/properties";
const BOOKINGS_ENDPOINT   = "/bookings";

// ── Booking modal state ──────────────────────────────────────
let _selectedProperty = null;

// ── Fetch properties ─────────────────────────────────────────

async function fetchProperties() {
  const res = await fetch(PROPERTIES_ENDPOINT);
  if (!res.ok) throw new Error("Could not load properties.");
  return res.json();
}

// ── Card renderer ─────────────────────────────────────────────

function renderPropertyCard(property) {
  const price = Number(property.price_per_night).toLocaleString("en-NG", {
    style: "currency",
    currency: "NGN",
    minimumFractionDigits: 0,
  });

  const amenityTags = (property.amenities || [])
    .map((a) => `<span class="amenity-tag">${a}</span>`)
    .join("");

  const card = document.createElement("article");
  card.className = "property-card";
  card.innerHTML = `
    <div class="property-card__image-wrap">
      <img
        src="${property.image_url || "/static/img/placeholder.jpg"}"
        alt="${property.name}"
        loading="lazy"
        class="property-card__image"
        onerror="this.src='/static/img/placeholder.jpg'"
      />
      ${property.location ? `<span class="property-card__location">📍 ${property.location}</span>` : ""}
    </div>
    <div class="property-card__body">
      <h3 class="property-card__name">${property.name}</h3>
      <p  class="property-card__desc">${property.description || ""}</p>
      <div class="property-card__amenities">${amenityTags}</div>
      <div class="property-card__footer">
        <div class="property-card__price">
          <span class="property-card__price-amount">${price}</span>
          <span class="property-card__price-unit">/ night</span>
        </div>
        <button
          class="btn btn--primary book-btn"
          data-property-id="${property.id}"
          aria-label="Book ${property.name}"
        >Book Now</button>
      </div>
    </div>
  `;

  card.querySelector(".book-btn").addEventListener("click", () =>
    openBookingModal(property)
  );

  return card;
}

// ── Booking modal ─────────────────────────────────────────────

function openBookingModal(property) {
  _selectedProperty = property;

  document.getElementById("modal-property-name").textContent = property.name;
  document.getElementById("modal-price-display").textContent =
    `₦${Number(property.price_per_night).toLocaleString()} / night`;

  updateModalTotal();

  const modal = document.getElementById("booking-modal");
  modal.classList.add("is-open");
  modal.querySelector(".modal__content").focus();
}

function closeBookingModal() {
  document.getElementById("booking-modal").classList.remove("is-open");
  document.getElementById("booking-form").reset();
  _selectedProperty = null;
}

function updateModalTotal() {
  if (!_selectedProperty) return;
  const checkIn  = document.getElementById("field-check-in").value;
  const checkOut = document.getElementById("field-check-out").value;
  if (!checkIn || !checkOut) return;

  const nights = Math.round(
    (new Date(checkOut) - new Date(checkIn)) / (1000 * 60 * 60 * 24)
  );
  if (nights <= 0) {
    document.getElementById("modal-total").textContent = "–";
    return;
  }
  const total = nights * Number(_selectedProperty.price_per_night);
  document.getElementById("modal-total").textContent =
    `₦${total.toLocaleString()} (${nights} night${nights > 1 ? "s" : ""})`;
}

// ── Paystack popup ────────────────────────────────────────────

async function initiatePayment(formData) {
  const submitBtn = document.getElementById("modal-submit-btn");
  submitBtn.disabled = true;
  submitBtn.textContent = "Processing…";

  try {
    // 1. Create pending booking on backend
    const res = await fetch(BOOKINGS_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        property_id:  _selectedProperty.id,
        guest_name:   formData.get("guest_name"),
        guest_email:  formData.get("guest_email"),
        check_in:     formData.get("check_in"),
        check_out:    formData.get("check_out"),
        num_guests:   parseInt(formData.get("num_guests"), 10),
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Booking creation failed.");
    }

    const { booking_id, payment_ref, total_price, paystack_public_key } = await res.json();

    // 2. Launch Paystack inline popup
    const handler = PaystackPop.setup({
      key:       paystack_public_key,
      email:     formData.get("guest_email"),
      amount:    Math.round(total_price * 100),   // Paystack expects kobo
      ref:       payment_ref,
      currency:  "NGN",
      metadata: {
        custom_fields: [
          { display_name: "Property",  variable_name: "property",  value: _selectedProperty.name },
          { display_name: "Booking ID", variable_name: "booking_id", value: booking_id },
        ],
      },
      onSuccess(response) {
        closeBookingModal();
        showSuccessBanner(
          `Payment received! 🎉 Check your email for confirmation. Ref: ${response.reference}`
        );
      },
      onCancel() {
        showToast("Payment cancelled. Your booking is held for 15 minutes.", "warn");
      },
    });

    handler.openIframe();
    closeBookingModal();
  } catch (err) {
    showToast(err.message || "Something went wrong. Please try again.", "error");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Proceed to Payment";
  }
}

// ── UI helpers ────────────────────────────────────────────────

function showSuccessBanner(message) {
  const banner = document.getElementById("success-banner");
  if (!banner) return;
  banner.textContent = message;
  banner.hidden = false;
  banner.scrollIntoView({ behavior: "smooth", block: "center" });
}

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("toast--visible"));
  setTimeout(() => {
    toast.classList.remove("toast--visible");
    toast.addEventListener("transitionend", () => toast.remove());
  }, 4500);
}

function showEmptyState(container) {
  container.innerHTML = `
    <div class="empty-state">
      <p>No properties available at the moment. Check back soon!</p>
    </div>
  `;
}

function showErrorState(container) {
  container.innerHTML = `
    <div class="empty-state empty-state--error">
      <p>Could not load properties. Please refresh the page.</p>
    </div>
  `;
}

// ── Gallery init ──────────────────────────────────────────────

async function initGallery() {
  const grid = document.getElementById("properties-grid");
  if (!grid) return;

  // Show skeleton loading
  grid.innerHTML = Array(3).fill(
    `<div class="property-card property-card--skeleton"></div>`
  ).join("");

  try {
    const properties = await fetchProperties();

    grid.innerHTML = "";
    if (!properties.length) {
      showEmptyState(grid);
      return;
    }

    const fragment = document.createDocumentFragment();
    properties.forEach((p) => fragment.appendChild(renderPropertyCard(p)));
    grid.appendChild(fragment);

    // Stagger-animate cards in
    grid.querySelectorAll(".property-card").forEach((card, i) => {
      card.style.animationDelay = `${i * 80}ms`;
      card.classList.add("animate-in");
    });
  } catch (err) {
    console.error("[gallery] Error:", err);
    showErrorState(grid);
  }
}

// ── Event wiring ─────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  initGallery();

  // Close modal on backdrop click or × button
  document.getElementById("booking-modal")?.addEventListener("click", (e) => {
    if (e.target.id === "booking-modal" || e.target.dataset.closeModal) {
      closeBookingModal();
    }
  });

  // Close on Escape
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeBookingModal();
  });

  // Date change → recalculate total
  ["field-check-in", "field-check-out"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", updateModalTotal);
  });

  // Set min date to today on date inputs
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("field-check-in")?.setAttribute("min", today);
  document.getElementById("field-check-out")?.setAttribute("min", today);

  // Form submission
  document.getElementById("booking-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    initiatePayment(new FormData(e.target));
  });
});
