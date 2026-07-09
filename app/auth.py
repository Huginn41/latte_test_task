from fastapi import Cookie, Request
from fastapi.responses import RedirectResponse

COOKIE_NAME = "user_name"


def get_current_user(user_name: str | None = Cookie(default=None)) -> str | None:
    return user_name.strip() if user_name else None


def require_user(request: Request, user_name: str | None = Cookie(default=None)):
    """Dependency: redirects to /login if not authenticated."""
    if not user_name or not user_name.strip():
        return RedirectResponse(url="/login", status_code=302)
    return user_name.strip()
