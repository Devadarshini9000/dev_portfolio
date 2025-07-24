import datetime
import logging
from flask import Blueprint, request, jsonify, current_app
from ..utils import is_valid_email, send_email
from pymongo.errors import PyMongoError
from ..extensions import limiter
from ..config import Config

contact_bp = Blueprint('contact', __name__)

@contact_bp.route('/contact', methods=['POST'])
@limiter.limit("10 per hour; 1 per minute") # Stricter limit for this sensitive endpoint
def handle_contact_form():
    db = current_app.db
    # First, check if the database connection itself exists
    if db is None:
        return jsonify({"error": "Database connection not available"}), 503

    # --- Granular Validation ---
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON in request body"}), 400

    errors = {}
    name = data.get('name')
    email = data.get('email')
    message_text = data.get('message')

    if not name:
        errors['name'] = 'Name is a required field.'
    if not email:
        errors['email'] = 'Email is a required field.'
    elif not is_valid_email(email):
        errors['email'] = 'A valid email address format is required.'
    if not message_text:
        errors['message'] = 'Message is a required field.'

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    message = {
        "name": data.get('name'),
        "email": email,
        "subject": data.get('subject', 'No Subject'),
        "message": data.get('message'),
        "timestamp": datetime.datetime.utcnow(),
        "ip_address": request.headers.get('X-Forwarded-For', request.remote_addr)
    }

    try:
        db.contact_form.insert_one(message)

        if not Config.RECIPIENT_EMAIL:
            logging.warning("RECIPIENT_EMAIL not set. Skipping contact form notification.")
        else:
            email_subject = f"New Portfolio Contact: {message['subject']}"
            email_body = f"""
You have a new message from your portfolio contact form:
Name: {message['name']}
Email: {message['email']}
IP Address: {message.get('ip_address', 'N/A')}
Message:
{message['message']}"""
            send_email(Config.RECIPIENT_EMAIL, email_subject, email_body)

        return jsonify({"success": True, "message": "Message received successfully!"}), 201
    except PyMongoError as e:
        logging.error(f"Error inserting contact message into DB: {e}")
        return jsonify({"error": "An internal error occurred while saving the message."}), 500