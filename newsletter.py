import datetime
import logging
from flask import Blueprint, request, jsonify, current_app
from ..utils import is_valid_email
from ..extensions import limiter

newsletter_bp = Blueprint('newsletter', __name__)

@newsletter_bp.route('/subscribe', methods=['POST'])
@limiter.limit("20 per hour")
def handle_subscription():
    db = current_app.db
    if db is None:
        return jsonify({"error": "Database connection not available"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON in request body"}), 400

    errors = {}
    email = data.get('email')
    if not email:
        errors['email'] = 'Email is a required field.'
    elif not is_valid_email(email):
        errors['email'] = 'A valid email address format is required.'
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    try:
        if db.newsletter_subscribers.find_one({"email": email}):
            return jsonify({"success": True, "message": "You are already subscribed!"}), 200
        db.newsletter_subscribers.insert_one({"email": email, "timestamp": datetime.datetime.utcnow()})
        logging.info(f"New newsletter subscriber: {email}")
        return jsonify({"success": True, "message": "Thank you for subscribing!"}), 201
    except Exception as e:
        logging.error(f"Error inserting subscriber into DB: {e}")
        return jsonify({"error": "An internal error occurred."}), 500