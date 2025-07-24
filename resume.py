import os
import datetime
import logging
from flask import Blueprint, request, jsonify, current_app
from ..utils import is_valid_email, send_email
from ..extensions import limiter
from ..config import Config

resume_bp = Blueprint('resume', __name__)

@resume_bp.route('/request-resume', methods=['POST'])
@limiter.limit("5 per hour; 20 per day")
def handle_resume_request():
    db = current_app.db
    if db is None:
        return jsonify({"error": "Database connection not available"}), 503

    data = request.get_json()
    name = data.get('name')
    email = data.get('email')

    if not data:
        return jsonify({"error": "Missing JSON in request body"}), 400

    errors = {}
    if not name:
        errors['name'] = 'Name is a required field.'
    if not email:
        errors['email'] = 'Email is a required field.'
    elif not is_valid_email(email):
        errors['email'] = 'A valid email address format is required.'

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    request_record = {
        "name": name, "email": email, "timestamp": datetime.datetime.utcnow(), "email_status": "pending"
    }

    try:
        email_subject = "Here is a copy of Devadarshini's Resume"
        email_body = f"""Hello {name},

Thank you for your interest in my profile! Please find my resume attached.

Best regards,
Devadarshini P"""
        attachment_path = os.path.join(Config.APP_ROOT, "frontend", "assets", "resume.pdf")
        attachment_filename = "Devadarshini_P_Resume.pdf"

        success, status_message = send_email(email, email_subject, email_body, attachment_path, attachment_filename)

        request_record["email_status"] = "sent" if success else "failed"
        if not success:
            request_record["email_error"] = status_message

        db.resume_requests.insert_one(request_record)
        logging.info(f"DB record for resume request from: {name} ({email}) - Status: {request_record['email_status']}")

        if success:
            return jsonify({"success": True, "message": "Thank you! The resume has been sent to your email."}), 200
        else:
            return jsonify({"success": False, "message": "Your request was received, but we couldn't send the email. Please try again later."}), 500

    except Exception as e:
        logging.error(f"Error processing resume request: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500