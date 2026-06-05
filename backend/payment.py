"""
Payment Service — Razorpay integration for subscription payments.
Uses Razorpay test mode (no real money in test).
To go live: swap test keys for live keys in .env.
"""
import os
import hmac
import hashlib
import logging
import time
from flask import request, jsonify
from auth import require_auth, activate_subscription, _get_db, _extract_token, _verify_token

logger = logging.getLogger(__name__)

PLAN_INR = 100  # ₹1 = 100 paise  (Razorpay uses paise)
PLAN_MONTHS = 1


def _razorpay_client():
    try:
        import razorpay
        key_id = os.getenv("RAZORPAY_KEY_ID", "")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
        if not key_id or not key_secret or "your_key" in key_id:
            return None
        return razorpay.Client(auth=(key_id, key_secret))
    except Exception as e:
        logger.warning(f"Razorpay not available: {e}")
        return None


@require_auth
def create_order(user_id=None):
    """Create a Razorpay order for ₹1 subscription."""
    client = _razorpay_client()

    if not client:
        # Demo mode: return a fake order for testing UI without real Razorpay keys
        fake_order_id = f"order_demo_{int(time.time())}"
        with _get_db() as conn:
            conn.execute(
                "INSERT INTO payments (user_id, razorpay_order_id, amount, status, created_at) VALUES (?,?,?,?,?)",
                (user_id, fake_order_id, PLAN_INR, 'created', int(time.time()))
            )
        return jsonify({
            "order_id": fake_order_id,
            "amount": PLAN_INR,
            "currency": "INR",
            "key_id": "demo_mode",
            "demo_mode": True,
            "message": "Demo mode: Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to .env for real payments"
        })

    try:
        order = client.order.create({
            "amount": PLAN_INR,
            "currency": "INR",
            "receipt": f"medcode_sub_{user_id}_{int(time.time())}",
            "notes": {"user_id": str(user_id), "plan": "monthly_subscription"}
        })
        with _get_db() as conn:
            conn.execute(
                "INSERT INTO payments (user_id, razorpay_order_id, amount, status, created_at) VALUES (?,?,?,?,?)",
                (user_id, order['id'], PLAN_INR, 'created', int(time.time()))
            )
        return jsonify({
            "order_id": order['id'],
            "amount": PLAN_INR,
            "currency": "INR",
            "key_id": os.getenv("RAZORPAY_KEY_ID"),
        })
    except Exception as e:
        logger.error(f"Order creation failed: {e}")
        return jsonify({"error": str(e)}), 500


@require_auth
def verify_payment(user_id=None):
    """
    Verify Razorpay payment signature and activate subscription.
    Called after successful payment on frontend.
    """
    data = request.get_json()
    order_id = data.get('razorpay_order_id', '')
    payment_id = data.get('razorpay_payment_id', '')
    signature = data.get('razorpay_signature', '')

    # Demo mode: order_id starts with "order_demo_"
    if order_id.startswith('order_demo_'):
        expires = activate_subscription(user_id, PLAN_MONTHS)
        with _get_db() as conn:
            conn.execute(
                "UPDATE payments SET status='paid', razorpay_payment_id=? WHERE razorpay_order_id=? AND user_id=?",
                ('demo_payment', order_id, user_id)
            )
        return jsonify({
            "success": True,
            "message": "Demo subscription activated!",
            "expires": expires
        })

    # Real Razorpay: verify HMAC-SHA256 signature
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    expected = hmac.new(
        key_secret.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        return jsonify({"error": "Payment signature verification failed"}), 400

    expires = activate_subscription(user_id, PLAN_MONTHS)
    with _get_db() as conn:
        conn.execute(
            "UPDATE payments SET status='paid', razorpay_payment_id=? WHERE razorpay_order_id=? AND user_id=?",
            (payment_id, order_id, user_id)
        )
    logger.info(f"Subscription activated for user {user_id}")
    return jsonify({"success": True, "expires": expires})


def get_subscription_status():
    """Return current subscription status for logged-in user."""
    token = _extract_token()
    if not token:
        return jsonify({"is_subscribed": False})
    payload = _verify_token(token)
    if not payload:
        return jsonify({"is_subscribed": False})
    with _get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id=?", (payload['sub'],)).fetchone()
    if not user:
        return jsonify({"is_subscribed": False})
    now = int(time.time())
    is_sub = bool(user['is_subscribed']) and user['subscription_expires'] > now
    return jsonify({
        "is_subscribed": is_sub,
        "expires": user['subscription_expires'] if is_sub else None
    })
