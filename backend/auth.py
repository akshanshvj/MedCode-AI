"""
Auth Service — User registration, login, JWT tokens, SQLite storage.
"""
import os
import sqlite3
import hashlib
import hmac
import secrets
import time
import json
import logging
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "medcode.db")


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with _get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT    UNIQUE NOT NULL,
                name        TEXT    NOT NULL,
                password_hash TEXT  NOT NULL,
                created_at  INTEGER NOT NULL,
                is_subscribed INTEGER DEFAULT 0,
                subscription_expires INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS payments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                razorpay_order_id  TEXT,
                razorpay_payment_id TEXT,
                amount          INTEGER NOT NULL,
                currency        TEXT DEFAULT 'INR',
                status          TEXT DEFAULT 'pending',
                created_at      INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
        """)
    logger.info("Database initialised")


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000)
    return f"{salt}${h.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split('$')
        expected = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000)
        return hmac.compare_digest(expected.hex(), h)
    except Exception:
        return False


def _make_token(user_id: int, email: str) -> str:
    secret = os.getenv("JWT_SECRET", "dev_secret_change_in_production")
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}))
    payload = _b64url(json.dumps({
        "sub": user_id,
        "email": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + 60 * 60 * 24 * 30  # 30 days
    }))
    sig_input = f"{header}.{payload}"
    import hmac as _hmac, hashlib as _hl
    sig = _hmac.new(secret.encode(), sig_input.encode(), _hl.sha256).digest()
    return f"{sig_input}.{_b64url_bytes(sig)}"


def _b64url(s: str) -> str:
    import base64
    return base64.urlsafe_b64encode(s.encode()).rstrip(b'=').decode()


def _b64url_bytes(b: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


def _verify_token(token: str) -> dict | None:
    try:
        import base64, hmac as _hmac, hashlib as _hl
        secret = os.getenv("JWT_SECRET", "dev_secret_change_in_production")
        parts = token.split('.')
        if len(parts) != 3:
            return None
        sig_input = f"{parts[0]}.{parts[1]}"
        expected_sig = _hmac.new(secret.encode(), sig_input.encode(), _hl.sha256).digest()
        provided_sig = base64.urlsafe_b64decode(parts[2] + '==')
        if not _hmac.compare_digest(expected_sig, provided_sig):
            return None
        pad = 4 - len(parts[1]) % 4
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=' * pad))
        if payload.get('exp', 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ── Flask route handlers ──────────────────────────────────────────────

def register():
    data = request.get_json()
    email = (data.get('email') or '').strip().lower()
    name = (data.get('name') or '').strip()
    password = data.get('password') or ''

    if not email or '@' not in email:
        return jsonify({"error": "Valid email required"}), 400
    if not name or len(name) < 2:
        return jsonify({"error": "Name required"}), 400
    if not password or len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    try:
        with _get_db() as conn:
            conn.execute(
                "INSERT INTO users (email, name, password_hash, created_at) VALUES (?,?,?,?)",
                (email, name, _hash_password(password), int(time.time()))
            )
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        token = _make_token(user['id'], email)
        return jsonify({
            "token": token,
            "user": {"id": user['id'], "email": email, "name": name,
                     "is_subscribed": False}
        })
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already registered"}), 409


def login():
    data = request.get_json()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    with _get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    if not user or not _verify_password(password, user['password_hash']):
        return jsonify({"error": "Invalid email or password"}), 401

    now = int(time.time())
    is_sub = bool(user['is_subscribed']) and user['subscription_expires'] > now
    token = _make_token(user['id'], email)
    return jsonify({
        "token": token,
        "user": {
            "id": user['id'],
            "email": email,
            "name": user['name'],
            "is_subscribed": is_sub,
            "subscription_expires": user['subscription_expires']
        }
    })


def get_me():
    token = _extract_token()
    if not token:
        return jsonify({"error": "Not authenticated"}), 401
    payload = _verify_token(token)
    if not payload:
        return jsonify({"error": "Invalid or expired token"}), 401

    with _get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id=?", (payload['sub'],)).fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404

    now = int(time.time())
    is_sub = bool(user['is_subscribed']) and user['subscription_expires'] > now
    return jsonify({
        "id": user['id'],
        "email": user['email'],
        "name": user['name'],
        "is_subscribed": is_sub,
        "subscription_expires": user['subscription_expires']
    })


def _extract_token() -> str | None:
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:]
    return None


def require_auth(f):
    """Decorator: requires valid JWT. Injects user_id into kwargs."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Authentication required"}), 401
        payload = _verify_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        kwargs['user_id'] = payload['sub']
        return f(*args, **kwargs)
    return decorated


def require_subscription(f):
    """Decorator: requires active subscription."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Authentication required"}), 401
        payload = _verify_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        with _get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE id=?", (payload['sub'],)).fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404
        now = int(time.time())
        if not (user['is_subscribed'] and user['subscription_expires'] > now):
            return jsonify({"error": "Active subscription required", "code": "SUBSCRIPTION_REQUIRED"}), 403
        kwargs['user_id'] = payload['sub']
        return f(*args, **kwargs)
    return decorated


def activate_subscription(user_id: int, months: int = 1):
    """Activate subscription for user after successful payment."""
    import time
    expires = int(time.time()) + months * 30 * 24 * 3600
    with _get_db() as conn:
        conn.execute(
            "UPDATE users SET is_subscribed=1, subscription_expires=? WHERE id=?",
            (expires, user_id)
        )
    return expires
