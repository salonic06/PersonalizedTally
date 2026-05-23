from __future__ import annotations

import os

# Dev UI on localhost or another device on your LAN (Vite default port 5173).
_LAN_DEV_UI = (
    r"https?://localhost:5173"
    r"|https?://127\.0\.0\.1:5173"
    r"|https?://192\.168\.\d{1,3}\.\d{1,3}:5173"
    r"|https?://10\.\d{1,3}\.\d{1,3}\.\d{1,3}:5173"
)


def cors_settings() -> dict:
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    extra = os.environ.get("PT_WEB_ORIGINS", "")
    for part in extra.split(","):
        p = part.strip()
        if p and p not in origins:
            origins.append(p)
    return {
        "allow_origins": origins,
        "allow_origin_regex": _LAN_DEV_UI,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST"],
        "allow_headers": ["*"],
    }
