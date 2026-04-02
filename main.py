"""
main.py  —  FastAPI application entry point.

Run:
    uvicorn main:app --reload --port 8000

Structure:
    main.py
    config.py
    auth.py
    database.py
    routers/
        config.py
        properties.py
        bookings.py
        admin.py
        booking_requests.py
    services/
        __init__.py
        email.py
    static/
        index.html
        admin.html
        js/
            config-injector.js
            gallery.js
            admin.js
        css/
            styles.css
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from routers import config, properties, bookings, admin, booking_requests, chat


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/api/docs" if settings.debug else None,
    redoc_url=None,
)

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────
app.include_router(config.router)
app.include_router(properties.router)
app.include_router(bookings.router)
app.include_router(admin.router)
app.include_router(booking_requests.router)
app.include_router(chat.router)

# ── Static files ──────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Page routes ───────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse("static/index.html")


@app.get("/admin", include_in_schema=False)
def serve_admin():
    return FileResponse("static/admin.html")


# ── Health check ─────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "app": settings.app_name}