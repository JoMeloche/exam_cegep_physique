"""Accounts for the web app: sign-up with a reason, admin approval, sessions, CSRF, rate limits.

Off in the desktop app (EXAMGEN_DESKTOP=1) or with EXAMGEN_AUTH=0; on everywhere else.

Storage: SQLite in <EXAM_APP_HOME>/.examgen/auth.sqlite3 (override EXAMGEN_AUTH_DB).
Passwords: argon2id (argon2-cffi). Sessions: random 256-bit token in an HttpOnly, SameSite=Lax
cookie; only its SHA-256 is stored. CSRF: the session's token must be echoed in X-CSRF-Token on
every POST/PUT/PATCH/DELETE (double submit, bound to the session), and a foreign Origin is refused.
"""
from __future__ import annotations

import contextvars
import datetime as dt
import hashlib
import hmac
import logging
import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

log = logging.getLogger("examgen.auth")

SESSION_COOKIE = "examgen_session"
CSRF_COOKIE = "examgen_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
STATUSES = ("pending", "approved", "rejected", "disabled")

current_user: contextvars.ContextVar["User | None"] = contextvars.ContextVar("examgen_user", default=None)


class AuthError(Exception):
    def __init__(self, status: int, detail: str, headers: dict[str, str] | None = None):
        super().__init__(detail)
        self.status, self.detail, self.headers = status, detail, headers or {}


# ------------------------------------------------------------------ settings
def desktop_mode() -> bool:
    return os.environ.get("EXAMGEN_DESKTOP") == "1"


def enabled() -> bool:
    if desktop_mode():
        return False
    return os.environ.get("EXAMGEN_AUTH", "1").strip().lower() not in {"0", "false", "no", "off"}


def library_mode() -> str:
    m = os.environ.get("EXAMGEN_LIBRARY_MODE", "per-user").strip().lower()
    return "shared" if m == "shared" else "per-user"


def base_root() -> Path:
    env = os.environ.get("EXAM_APP_HOME")
    return Path(env).expanduser() if env else Path.home() / "exam_app"


def _hours(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def idle_timeout() -> float:
    return _hours("EXAMGEN_SESSION_IDLE_HOURS", 24) * 3600


def max_age() -> float:
    return _hours("EXAMGEN_SESSION_MAX_HOURS", 24 * 7) * 3600


# ------------------------------------------------------------------ passwords
_hasher = None


def hasher():
    global _hasher
    if _hasher is None:
        from argon2 import PasswordHasher  # imported lazily: the desktop app never needs it
        _hasher = PasswordHasher()  # argon2id, RFC 9106 low-memory profile
    return _hasher


def hash_password(pw: str) -> str:
    return hasher().hash(pw)


def verify_password(stored: str | None, pw: str) -> bool:
    from argon2.exceptions import InvalidHashError, VerificationError
    try:
        return hasher().verify(stored or _DUMMY_HASH(), pw)  # dummy keeps timing equal for unknown emails
    except (VerificationError, InvalidHashError):
        return False


_dummy: str | None = None


def _DUMMY_HASH() -> str:  # noqa: N802
    global _dummy
    if _dummy is None:
        _dummy = hash_password(secrets.token_urlsafe(16))
    return _dummy


def password_problem(pw: str, email: str = "") -> str | None:
    if len(pw) < 10:
        return "Le mot de passe doit contenir au moins 10 caractères."
    if len(pw) > 256:
        return "Le mot de passe est trop long (256 caractères au maximum)."
    if email and pw.strip().lower() == email.strip().lower():
        return "Le mot de passe ne peut pas être votre courriel."
    if len(set(pw)) < 4:
        return "Choisissez un mot de passe moins répétitif."
    return None


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> float:
    return time.time()


def _iso(ts: float | None) -> str | None:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat() if ts else None


# ------------------------------------------------------------------ rate limiting
class RateLimiter:
    """Sliding windows in memory (one server process). key -> timestamps of recent hits."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, window: float, now: float) -> deque[float]:
        q = self._hits[key]
        while q and q[0] <= now - window:
            q.popleft()
        return q

    def check(self, key: str, limit: int, window: float) -> None:
        """Raise 429 if `key` already has `limit` hits in the last `window` seconds."""
        now = _now()
        with self._lock:
            q = self._prune(key, window, now)
            if len(q) >= limit:
                retry = int(q[0] + window - now) + 1
                raise AuthError(429, f"Trop de tentatives. Réessayez dans {max(1, retry // 60 or 1)} min.",
                                {"Retry-After": str(retry)})

    def hit(self, key: str) -> None:
        with self._lock:
            self._hits[key].append(_now())

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
LOGIN_IP = (30, 15 * 60)       # attempts per IP per 15 min
LOGIN_EMAIL = (8, 15 * 60)     # failed attempts per account per 15 min
SIGNUP_IP = (5, 60 * 60)       # sign-up requests per IP per hour
SETUP_IP = (10, 15 * 60)
PASSWORD_USER = (10, 15 * 60)


# ------------------------------------------------------------------ storage
@dataclass
class User:
    id: int
    email: str
    name: str
    role: str
    status: str
    reason: str
    library: str
    created_at: float
    decided_at: float | None = None
    decided_by: str | None = None
    note: str = ""
    last_login: float | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin" and self.status == "approved"

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "email": self.email, "name": self.name, "role": self.role, "status": self.status}

    def admin_view(self) -> dict[str, Any]:
        return {**self.public(), "reason": self.reason, "note": self.note, "created_at": _iso(self.created_at),
                "decided_at": _iso(self.decided_at), "decided_by": self.decided_by,
                "last_login": _iso(self.last_login)}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  status TEXT NOT NULL DEFAULT 'pending',
  reason TEXT NOT NULL DEFAULT '',
  library TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  created_at REAL NOT NULL,
  decided_at REAL,
  decided_by TEXT,
  last_login REAL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  csrf TEXT NOT NULL,
  created_at REAL NOT NULL,
  last_seen REAL NOT NULL,
  ip TEXT,
  user_agent TEXT
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS shares (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target TEXT NOT NULL,             -- '*' (whole bank) or a question id course/topic/name
  audience TEXT NOT NULL,           -- 'all' (every approved user) or 'users' (share_members)
  created_at REAL NOT NULL,
  UNIQUE (owner_id, target)
);
CREATE TABLE IF NOT EXISTS share_members (
  share_id INTEGER NOT NULL REFERENCES shares(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY (share_id, user_id)
);
"""
_USER_COLS = "id, email, name, role, status, reason, library, created_at, decided_at, decided_by, note, last_login"


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path.parent, 0o700)
        except OSError:
            pass
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA journal_mode = WAL")
        self._db.executescript(_SCHEMA)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def q(self, sql: str, args: tuple = ()) -> list[tuple]:
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    def x(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._db.execute(sql, args)

    # users
    def _user(self, row: tuple | None) -> User | None:
        return User(*row) if row else None

    def user_by_id(self, uid: int) -> User | None:
        rows = self.q(f"SELECT {_USER_COLS} FROM users WHERE id = ?", (uid,))
        return self._user(rows[0] if rows else None)

    def user_by_email(self, email: str) -> tuple[User | None, str | None]:
        rows = self.q(f"SELECT {_USER_COLS}, password_hash FROM users WHERE email = ?", (email.strip(),))
        if not rows:
            return None, None
        return User(*rows[0][:-1]), rows[0][-1]

    def users(self, status: str | None = None) -> list[User]:
        if status:
            rows = self.q(f"SELECT {_USER_COLS} FROM users WHERE status = ? ORDER BY created_at DESC", (status,))
        else:
            rows = self.q(f"SELECT {_USER_COLS} FROM users ORDER BY created_at DESC")
        return [User(*r) for r in rows]

    def count(self, where: str = "1=1", args: tuple = ()) -> int:
        return self.q(f"SELECT COUNT(*) FROM users WHERE {where}", args)[0][0]

    def admin_count(self) -> int:
        return self.count("role = 'admin' AND status = 'approved'")

    def create_user(self, email: str, name: str, password: str, *, reason: str = "", role: str = "user",
                    status: str = "pending", library: str = "") -> User:
        cur = self.x("INSERT INTO users (email, name, password_hash, role, status, reason, library, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (email.strip(), name.strip(), hash_password(password), role, status, reason.strip(), library, _now()))
        return self.user_by_id(cur.lastrowid)  # type: ignore[arg-type,return-value]

    def update_user(self, uid: int, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.x(f"UPDATE users SET {cols} WHERE id = ?", (*fields.values(), uid))

    def set_password(self, uid: int, password: str) -> None:
        self.update_user(uid, password_hash=hash_password(password))

    def delete_user(self, uid: int) -> None:
        self.x("DELETE FROM users WHERE id = ?", (uid,))

    # sessions
    def create_session(self, uid: int, ip: str, ua: str) -> tuple[str, str]:
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = _now()
        self.x("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)", (_sha(token), uid, csrf, now, now, ip, ua[:300]))
        self.x("UPDATE users SET last_login = ? WHERE id = ?", (now, uid))
        return token, csrf

    def session(self, token: str) -> tuple[User, str] | None:
        th = _sha(token)
        rows = self.q("SELECT user_id, csrf, created_at, last_seen FROM sessions WHERE token_hash = ?", (th,))
        if not rows:
            return None
        uid, csrf, created, seen = rows[0]
        now = _now()
        if now - created > max_age() or now - seen > idle_timeout():
            self.x("DELETE FROM sessions WHERE token_hash = ?", (th,))
            return None
        user = self.user_by_id(uid)
        if not user or user.status != "approved":
            self.x("DELETE FROM sessions WHERE token_hash = ?", (th,))
            return None
        if now - seen > 60:
            self.x("UPDATE sessions SET last_seen = ? WHERE token_hash = ?", (now, th))
        return user, csrf

    def delete_session(self, token: str) -> None:
        self.x("DELETE FROM sessions WHERE token_hash = ?", (_sha(token),))

    def revoke_sessions(self, uid: int, keep: str | None = None) -> None:
        if keep:
            self.x("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (uid, _sha(keep)))
        else:
            self.x("DELETE FROM sessions WHERE user_id = ?", (uid,))

    def purge_expired(self) -> None:
        now = _now()
        self.x("DELETE FROM sessions WHERE created_at < ? OR last_seen < ?", (now - max_age(), now - idle_timeout()))


_store: Store | None = None
_store_lock = threading.Lock()


def db_path() -> Path:
    env = os.environ.get("EXAMGEN_AUTH_DB")
    return Path(env).expanduser() if env else base_root() / ".examgen" / "auth.sqlite3"


def store() -> Store:
    global _store
    p = db_path()
    with _store_lock:
        if _store is None or _store.path != p:
            _store = Store(p)
            bootstrap(_store)
    return _store


# ------------------------------------------------------------------ first admin
_setup_token: str | None = None


def bootstrap(s: Store) -> None:
    """Create the first admin from EXAMGEN_ADMIN_EMAIL / EXAMGEN_ADMIN_PASSWORD, or print a one-time
    setup code to the server log so the first admin can be created from the browser."""
    global _setup_token
    if s.admin_count():
        _setup_token = None
        return
    email = os.environ.get("EXAMGEN_ADMIN_EMAIL", "").strip()
    pw = os.environ.get("EXAMGEN_ADMIN_PASSWORD", "")
    pw_file = os.environ.get("EXAMGEN_ADMIN_PASSWORD_FILE", "")
    if not pw and pw_file and Path(pw_file).is_file():
        pw = Path(pw_file).read_text(encoding="utf-8").strip()
    if email and pw:
        prob = password_problem(pw, email)
        if prob or not EMAIL_RE.match(email):
            log.error("EXAMGEN_ADMIN_EMAIL / EXAMGEN_ADMIN_PASSWORD ignorés : %s", prob or "courriel invalide")
        else:
            create_admin(s, email, os.environ.get("EXAMGEN_ADMIN_NAME", "Administrateur"), pw)
            log.warning("Compte administrateur %s créé à partir des variables d'environnement.", email)
            return
    if os.environ.get("EXAMGEN_QUIET_SETUP") == "1":
        return
    _setup_token = os.environ.get("EXAMGEN_SETUP_TOKEN") or secrets.token_hex(10)
    msg = (f"\n{'=' * 64}\n  Aucun administrateur. Ouvrez l'application et entrez ce code de\n"
           f"  configuration pour créer le compte administrateur :\n\n      {_setup_token}\n{'=' * 64}\n")
    print(msg, flush=True)
    log.warning("Code de configuration administrateur : %s", _setup_token)


def needs_setup() -> bool:
    return store().admin_count() == 0


def check_setup_token(token: str) -> bool:
    return bool(_setup_token) and hmac.compare_digest(_setup_token.encode(), (token or "").strip().encode())


def create_admin(s: Store, email: str, name: str, password: str) -> User:
    """Create (or promote) an admin. The very first account to own the root library is the one that
    keeps the bank that was already at EXAM_APP_HOME, so an existing installation loses nothing."""
    existing, _ = s.user_by_email(email)
    if existing:
        s.update_user(existing.id, role="admin", status="approved", decided_at=_now(), decided_by="setup")
        s.set_password(existing.id, password)
        u = s.user_by_id(existing.id)
    else:
        root_taken = s.count("library = ''") > 0
        u = s.create_user(email, name, password, role="admin", status="approved", library="__new__")
        s.update_user(u.id, library=f"users/{u.id}" if root_taken else "", decided_at=_now(), decided_by="setup")
        u = s.user_by_id(u.id)
    provision_library(u)  # type: ignore[arg-type]
    return u  # type: ignore[return-value]


# ------------------------------------------------------------------ per-user libraries
def library_root(user: User | None) -> Path:
    base = base_root()
    if user is None or library_mode() == "shared" or not user.library:
        return base
    p = (base / user.library).resolve()
    if base.resolve() not in p.parents:
        raise AuthError(500, "Bibliothèque invalide")
    return p


def provision_library(user: User) -> None:
    """Give a teacher their own library, seeded with the starter bank (EXAMGEN_SEED) the first time."""
    root = library_root(user)
    q = root / "questions"
    if q.exists() and any(q.iterdir()):
        return
    root.mkdir(parents=True, exist_ok=True)
    seed = os.environ.get("EXAMGEN_SEED", "")
    seed_dir = Path(seed) if seed else None
    if seed_dir and (seed_dir / "questions").exists():
        for item in seed_dir.iterdir():
            dest = root / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            elif not dest.exists():
                shutil.copy2(item, dest)


# ------------------------------------------------------------------ request helpers
def client_ip(request) -> str:
    return request.client.host if request.client else "?"


def _cookie_secure(request) -> bool:
    v = os.environ.get("EXAMGEN_SECURE_COOKIES", "auto").strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    return request.url.scheme == "https"


def set_session_cookies(response, request, token: str, csrf: str) -> None:
    secure = _cookie_secure(request)
    response.set_cookie(SESSION_COOKIE, token, max_age=int(max_age()), httponly=True, secure=secure,
                        samesite="lax", path="/")
    response.set_cookie(CSRF_COOKIE, csrf, max_age=int(max_age()), httponly=False, secure=secure,
                        samesite="strict", path="/")


def clear_session_cookies(response, request) -> None:
    secure = _cookie_secure(request)
    response.delete_cookie(SESSION_COOKIE, path="/", secure=secure, httponly=True, samesite="lax")


def ensure_anon_csrf(response, request) -> str:
    """Anonymous visitors get a CSRF cookie too, so login/sign-up are protected."""
    tok = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)
    response.set_cookie(CSRF_COOKIE, tok, httponly=False, secure=_cookie_secure(request), samesite="strict", path="/")
    return tok


def origin_ok(request) -> bool:
    origin = request.headers.get("origin")
    if not origin or origin == "null":
        return origin is None  # "null" origins (sandboxed frames, file://) are refused
    host = request.headers.get("host", "")
    if urlsplit(origin).netloc.lower() == host.lower():
        return True
    trusted = {o.strip().rstrip("/").lower() for o in os.environ.get("EXAMGEN_TRUSTED_ORIGINS", "").split(",") if o.strip()}
    return origin.rstrip("/").lower() in trusted


def require_admin() -> User:
    u = current_user.get()
    if not enabled():
        raise AuthError(404, "Comptes désactivés")
    if not u or not u.is_admin:
        raise AuthError(403, "Réservé aux administrateurs")
    return u
