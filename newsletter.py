import datetime
import logging
from flask import Blueprint, request, jsonify, current_app
from ..utils import is_valid_email

newsletter_bp = Blueprint('newsletter', __name__)

@newsletter_bp.route('/subscribe', methods=['POST'])
def handle_subscription():
    db = current_app.db
    if db.newsletter_subscribers is None:
        return jsonify({"error": "Database connection not available"}), 503

    data = request.get_json()
    email = data.get('email')

    if not email or not is_valid_email(email):
        return jsonify({"error": "A valid email address is required."}), 400

    try:
        if db.newsletter_subscribers.find_one({"email": email}):
            return jsonify({"success": True, "message": "You are already subscribed!"}), 200

        db.newsletter_subscribers.insert_one({"email": email, "timestamp": datetime.datetime.utcnow()})
        logging.info(f"New newsletter subscriber: {email}")
        return jsonify({"success": True, "message": "Thank you for subscribing!"}), 201
    except Exception as e:
        logging.error(f"Error inserting subscriber into DB: {e}")
        return jsonify({"error": "An internal error occurred."}), 500