"""HTTP side of accounts: the guard middleware, /api/auth/*, /api/admin/*, /api/shares/*."""
from __future__ import annotations

import hmac
import secrets
from typing import Any

from fastapi import APIRouter, Body, Request, Response
from fastapi.responses import JSONResponse
from starlette.requests import Request as StarletteRequest

from . import auth, sharing
from .auth import AuthError, current_user, limiter

PUBLIC_API = {"/api/health", "/api/auth/state", "/api/auth/login", "/api/auth/signup", "/api/auth/setup",
              "/api/auth/logout"}

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "font-src 'self' data:; connect-src 'self'; frame-src 'self' blob:; object-src 'none'; "
       "base-uri 'self'; form-action 'self'; frame-ancestors 'self'")


def _json(status: int, detail: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status, headers=headers)


class AuthMiddleware:
    """Pure ASGI middleware: security headers everywhere; on /api, CSRF + Origin checks on writes and
    a valid approved session on everything but the public endpoints."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = StarletteRequest(scope)
        https = request.url.scheme == "https"
        path = scope["path"]
        is_api = path.startswith("/api/")

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                h = message.setdefault("headers", [])
                names = {k.lower() for k, _ in h}
                extra = [(b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"same-origin"),
                         (b"x-frame-options", b"SAMEORIGIN"), (b"cross-origin-opener-policy", b"same-origin")]
                ctype = dict(h).get(b"content-type", b"")
                if ctype.startswith(b"text/html"):
                    extra.append((b"content-security-policy", CSP.encode()))
                if is_api and b"cache-control" not in names and not ctype.startswith(b"application/pdf"):
                    extra.append((b"cache-control", b"no-store"))
                if https and auth.enabled():
                    extra.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                h.extend((k, v) for k, v in extra if k not in names)
            await send(message)

        if not is_api:
            return await self.app(scope, receive, send_with_headers)

        method = scope["method"].upper()
        unsafe = method not in auth.SAFE_METHODS
        if not auth.enabled():
            # Desktop / auth off: refuse cross-site writes (another web page posting to 127.0.0.1).
            if unsafe and not auth.origin_ok(request):
                return await _json(403, "Origine refusée")(scope, receive, send_with_headers)
            token = current_user.set(None)
            try:
                return await self.app(scope, receive, send_with_headers)
            finally:
                current_user.reset(token)

        user, csrf = None, None
        tok = request.cookies.get(auth.SESSION_COOKIE)
        if tok:
            found = auth.store().session(tok)
            if found:
                user, csrf = found
        if unsafe:
            if not auth.origin_ok(request):
                return await _json(403, "Origine refusée")(scope, receive, send_with_headers)
            sent = request.headers.get(auth.CSRF_HEADER, "")
            expected = csrf or request.cookies.get(auth.CSRF_COOKIE, "")
            if not expected or not sent or not hmac.compare_digest(sent.encode(), expected.encode()):
                return await _json(403, "Jeton de sécurité invalide. Rechargez la page.")(scope, receive, send_with_headers)
        if user is None and path not in PUBLIC_API:
            return await _json(401, "Connexion requise")(scope, receive, send_with_headers)
        token = current_user.set(user)
        try:
            return await self.app(scope, receive, send_with_headers)
        finally:
            current_user.reset(token)


router = APIRouter()


def _err(exc: AuthError) -> JSONResponse:
    return _json(exc.status, exc.detail, exc.headers)


def _str(p: dict[str, Any], key: str, maxlen: int = 300) -> str:
    v = p.get(key, "")
    if not isinstance(v, str):
        raise AuthError(400, f"Champ {key} invalide")
    v = v.strip() if key != "password" and not key.endswith("password") else v
    if len(v) > maxlen:
        raise AuthError(400, f"Champ {key} trop long")
    return v


def _state(request: Request, response, user: auth.User | None) -> dict[str, Any]:
    if not auth.enabled():
        return {"enabled": False, "user": None, "library_mode": "local", "sharing": False}
    s = auth.store()
    out: dict[str, Any] = {"enabled": True, "user": user.public() if user else None,
                           "needs_setup": s.admin_count() == 0, "library_mode": auth.library_mode(),
                           "sharing": auth.library_mode() == "per-user"}
    if user and user.is_admin:
        out["pending"] = s.count("status = 'pending'")
    if not user:
        auth.ensure_anon_csrf(response, request)
    return out


def _login_response(request: Request, user: auth.User, status: int = 200) -> JSONResponse:
    old = request.cookies.get(auth.SESSION_COOKIE)
    if old:
        auth.store().delete_session(old)  # never keep a previous session alive next to the new one
    token, csrf = auth.store().create_session(user.id, auth.client_ip(request), request.headers.get("user-agent", ""))
    resp = JSONResponse({"user": user.public()}, status_code=status)
    auth.set_session_cookies(resp, request, token, csrf)
    return resp


@router.get("/api/auth/state")
def auth_state(request: Request, response: Response):
    return _state(request, response, current_user.get())


@router.post("/api/auth/login")
def login(request: Request, payload: dict[str, Any] = Body(...)):
    try:
        if not auth.enabled():
            raise AuthError(404, "Comptes désactivés")
        ip = auth.client_ip(request)
        email = _str(payload, "email", 320).lower()
        pw = _str(payload, "password", 256)
        limiter.check(f"login-ip:{ip}", *auth.LOGIN_IP)
        limiter.check(f"login-email:{email}", *auth.LOGIN_EMAIL)
        limiter.hit(f"login-ip:{ip}")
        s = auth.store()
        user, stored = s.user_by_email(email)
        if not auth.verify_password(stored, pw) or not user:
            limiter.hit(f"login-email:{email}")
            raise AuthError(401, "Courriel ou mot de passe incorrect.")
        limiter.clear(f"login-email:{email}")
        try:
            if auth.hasher().check_needs_rehash(stored):
                s.set_password(user.id, pw)
        except Exception:  # noqa: BLE001
            pass
        if user.status == "pending":
            raise AuthError(403, "Votre demande de compte est en attente d'approbation par un administrateur.")
        if user.status == "rejected":
            raise AuthError(403, "Votre demande de compte a été refusée." + (f" Motif : {user.note}" if user.note else ""))
        if user.status != "approved":
            raise AuthError(403, "Ce compte est désactivé. Communiquez avec un administrateur.")
        return _login_response(request, user)
    except AuthError as exc:
        return _err(exc)


@router.post("/api/auth/logout")
def logout(request: Request):
    tok = request.cookies.get(auth.SESSION_COOKIE)
    if tok and auth.enabled():
        auth.store().delete_session(tok)
    resp = JSONResponse({"ok": True})
    auth.clear_session_cookies(resp, request)
    resp.set_cookie(auth.CSRF_COOKIE, secrets.token_urlsafe(32), httponly=False, samesite="strict", path="/",
                    secure=auth._cookie_secure(request))
    return resp


@router.post("/api/auth/signup")
def signup(request: Request, payload: dict[str, Any] = Body(...)):
    try:
        if not auth.enabled():
            raise AuthError(404, "Comptes désactivés")
        if payload.get("website"):  # honeypot field, hidden in the form
            return JSONResponse({"ok": True}, status_code=202)
        ip = auth.client_ip(request)
        limiter.check(f"signup-ip:{ip}", *auth.SIGNUP_IP)
        name = _str(payload, "name", 120)
        email = _str(payload, "email", 320).lower()
        pw = _str(payload, "password", 256)
        reason = _str(payload, "reason", 2000)
        if len(name) < 2:
            raise AuthError(400, "Indiquez votre nom.")
        if not auth.EMAIL_RE.match(email):
            raise AuthError(400, "Adresse courriel invalide.")
        if len(reason) < 15:
            raise AuthError(400, "Expliquez en quelques mots pourquoi vous demandez un compte (15 caractères au minimum).")
        prob = auth.password_problem(pw, email)
        if prob:
            raise AuthError(400, prob)
        limiter.hit(f"signup-ip:{ip}")
        s = auth.store()
        existing, _ = s.user_by_email(email)
        if existing is None:
            u = s.create_user(email, name, pw, reason=reason, library="__new__")
            s.update_user(u.id, library=f"users/{u.id}")
        else:
            auth.hash_password(pw)  # same work either way: no timing hint that the address exists
        # Same answer whether or not the address was already registered (no account discovery).
        return JSONResponse({"ok": True, "message": "Demande envoyée. Un administrateur doit l'approuver avant "
                                                    "que vous puissiez vous connecter."}, status_code=202)
    except AuthError as exc:
        return _err(exc)


@router.post("/api/auth/setup")
def setup_admin(request: Request, payload: dict[str, Any] = Body(...)):
    try:
        if not auth.enabled():
            raise AuthError(404, "Comptes désactivés")
        ip = auth.client_ip(request)
        limiter.check(f"setup-ip:{ip}", *auth.SETUP_IP)
        limiter.hit(f"setup-ip:{ip}")
        s = auth.store()
        if s.admin_count():
            raise AuthError(409, "Un administrateur existe déjà.")
        if not auth.check_setup_token(_str(payload, "token", 100)):
            raise AuthError(403, "Code de configuration invalide. Il est affiché dans le journal du serveur "
                                 "(docker compose logs examgen).")
        name = _str(payload, "name", 120) or "Administrateur"
        email = _str(payload, "email", 320).lower()
        pw = _str(payload, "password", 256)
        if not auth.EMAIL_RE.match(email):
            raise AuthError(400, "Adresse courriel invalide.")
        prob = auth.password_problem(pw, email)
        if prob:
            raise AuthError(400, prob)
        user = auth.create_admin(s, email, name, pw)
        auth.bootstrap(s)  # clears the setup code
        return _login_response(request, user, 201)
    except AuthError as exc:
        return _err(exc)


@router.post("/api/auth/password")
def change_password(request: Request, payload: dict[str, Any] = Body(...)):
    try:
        user = current_user.get()
        if not user:
            raise AuthError(401, "Connexion requise")
        limiter.check(f"pw-user:{user.id}", *auth.PASSWORD_USER)
        limiter.hit(f"pw-user:{user.id}")
        s = auth.store()
        _, stored = s.user_by_email(user.email)
        if not auth.verify_password(stored, _str(payload, "current_password", 256)):
            raise AuthError(400, "Mot de passe actuel incorrect.")
        new = _str(payload, "new_password", 256)
        prob = auth.password_problem(new, user.email)
        if prob:
            raise AuthError(400, prob)
        s.set_password(user.id, new)
        s.revoke_sessions(user.id, keep=request.cookies.get(auth.SESSION_COOKIE))
        return {"ok": True}
    except AuthError as exc:
        return _err(exc)


# ------------------------------------------------------------------ admin
@router.get("/api/admin/users")
def admin_users(status: str | None = None):
    try:
        auth.require_admin()
        if status and status not in auth.STATUSES:
            raise AuthError(400, "Statut invalide")
        s = auth.store()
        return {"users": [u.admin_view() for u in s.users(status)],
                "counts": {st: s.count("status = ?", (st,)) for st in auth.STATUSES}}
    except AuthError as exc:
        return _err(exc)


def _target(uid: int) -> auth.User:
    u = auth.store().user_by_id(uid)
    if not u:
        raise AuthError(404, "Utilisateur introuvable")
    return u


def _would_remove_last_admin(u: auth.User) -> bool:
    return u.is_admin and auth.store().admin_count() <= 1


@router.post("/api/admin/users/{uid}/{action}")
def admin_action(uid: int, action: str, payload: dict[str, Any] = Body(default={})):
    try:
        admin = auth.require_admin()
        s = auth.store()
        u = _target(uid)
        note = _str(payload or {}, "note", 500) if payload else ""
        stamp = {"decided_at": auth._now(), "decided_by": admin.email}
        extra: dict[str, Any] = {}
        if action == "approve":
            s.update_user(uid, status="approved", note="", **stamp)
            auth.provision_library(s.user_by_id(uid))  # type: ignore[arg-type]
        elif action == "reject":
            if u.status != "pending":
                raise AuthError(400, "Seules les demandes en attente peuvent être refusées.")
            s.update_user(uid, status="rejected", note=note, **stamp)
        elif action == "disable":
            if uid == admin.id or _would_remove_last_admin(u):
                raise AuthError(400, "Impossible de désactiver ce compte (dernier administrateur ou vous-même).")
            s.update_user(uid, status="disabled", note=note, **stamp)
            s.revoke_sessions(uid)
        elif action == "enable":
            s.update_user(uid, status="approved", note="", **stamp)
            auth.provision_library(s.user_by_id(uid))  # type: ignore[arg-type]
        elif action in {"make-admin", "make-user"}:
            if action == "make-user" and (uid == admin.id or _would_remove_last_admin(u)):
                raise AuthError(400, "Impossible de retirer le dernier administrateur ou vous-même.")
            if u.status != "approved":
                raise AuthError(400, "Approuvez d'abord ce compte.")
            s.update_user(uid, role="admin" if action == "make-admin" else "user")
        elif action == "reset-password":
            temp = "-".join(secrets.token_urlsafe(4) for _ in range(3))
            s.set_password(uid, temp)
            s.revoke_sessions(uid)
            extra["temporary_password"] = temp
        else:
            raise AuthError(404, "Action inconnue")
        return {"user": s.user_by_id(uid).admin_view(), **extra}  # type: ignore[union-attr]
    except AuthError as exc:
        return _err(exc)


@router.delete("/api/admin/users/{uid}")
def admin_delete(uid: int):
    try:
        admin = auth.require_admin()
        u = _target(uid)
        if uid == admin.id or _would_remove_last_admin(u):
            raise AuthError(400, "Impossible de supprimer ce compte.")
        auth.store().delete_user(uid)  # the teacher's library folder stays on disk
        return {"deleted": uid}
    except AuthError as exc:
        return _err(exc)


# ------------------------------------------------------------------ sharing
def _sharer() -> auth.User:
    u = current_user.get()
    if not auth.enabled() or not u or auth.library_mode() != "per-user":
        raise AuthError(404, "Le partage est disponible dans l'application web avec une banque par enseignant.")
    return u


@router.get("/api/shares")
def list_shares():
    try:
        u = _sharer()
        return {"shares": sharing.my_shares(u), "users": sharing.directory(u)}
    except AuthError as exc:
        return _err(exc)


@router.put("/api/shares")
def put_share(payload: dict[str, Any] = Body(...)):
    try:
        u = _sharer()
        target = _str(payload, "target", 400)
        if target != "*":
            from .api import own_lib
            try:
                own_lib().get(target)
            except KeyError as exc:
                raise AuthError(404, "Question introuvable dans votre banque") from exc
        ids = payload.get("user_ids") or []
        if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
            raise AuthError(400, "Liste d'utilisateurs invalide")
        return sharing.set_share(u, target, _str(payload, "audience", 10), ids)
    except AuthError as exc:
        return _err(exc)


@router.delete("/api/shares/{share_id}")
def remove_share(share_id: int):
    try:
        sharing.delete_share(_sharer(), share_id)
        return {"deleted": share_id}
    except AuthError as exc:
        return _err(exc)


@router.post("/api/shares/copy")
def copy_shared(payload: dict[str, Any] = Body(...)):
    try:
        u = _sharer()
        from .api import own_lib
        view = sharing.SharedLibrary(own_lib(), u)
        return {"id": sharing.copy_to_own(view, _str(payload, "id", 400))}
    except AuthError as exc:
        return _err(exc)
