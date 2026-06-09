from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable, Dict

from flask import Request, jsonify, request


def _extract_bearer(req: Request) -> str:
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return ""
    return auth.split(" ", 1)[1].strip()


def _parse_groups(req: Request) -> list[str]:
    raw = req.headers.get("X-SSO-Groups", "")
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


def sso_context(req: Request) -> Dict[str, Any]:
    return {
        "user": req.headers.get("X-SSO-User", ""),
        "email": req.headers.get("X-SSO-Email", ""),
        "groups": _parse_groups(req),
        "token": _extract_bearer(req),
    }


def require_sso(required_groups: list[str] | None = None) -> Callable[..., Any]:
    required_groups = required_groups or []

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            expected_token = os.getenv("LEGALFLOW_SSO_TOKEN", "").strip()
            ctx = sso_context(request)
            if not ctx["user"] or not ctx["email"]:
                return jsonify({"ok": False, "error": "SSO headers faltantes."}), 401
            if expected_token and ctx["token"] != expected_token:
                return jsonify({"ok": False, "error": "Token SSO invalido."}), 401
            if required_groups:
                user_groups = set(ctx["groups"])
                if not any(group.lower() in user_groups for group in required_groups):
                    return jsonify({"ok": False, "error": "Sin permisos para este recurso."}), 403
            return func(*args, **kwargs)

        return wrapper

    return decorator
