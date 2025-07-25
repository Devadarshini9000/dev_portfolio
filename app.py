import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- ADD THESE LINES HERE ---
from gevent import monkey
monkey.patch_all()
# --- END ADDED LINES ---

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from datetime import datetime
import logging
import certifi

import traceback
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr

# Initialize Limiter here, as it's an extension
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

def send_email_with_resume(recipient_email, recipient_name):
    """Sends an email with the resume attached."""
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD') # This should be your App Password

    # Wrap the entire logic in a try...except block to catch any errors
    # during message creation or sending.
    try:
        if not all([sender_email, sender_password]):
            logging.error("Email configuration (SENDER_EMAIL, SENDER_PASSWORD) is missing from .env file for resume.")
            return False

        # Create the email message
        msg = MIMEMultipart()
        msg['From'] = formataddr(('Devadarshini', sender_email))
        msg['To'] = recipient_email
        msg['Subject'] = "Here is the Resume You Requested"

        # Email body
        body = f"Hi {recipient_name},\n\nThank you for your interest! Please find my resume attached.\n\nBest regards,\nDevadarshini"
        msg.attach(MIMEText(body, 'plain'))

        # Construct the full path to the resume file
        resume_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'assets', 'Devadarshini_Resume.pdf')

        if not os.path.exists(resume_path):
            logging.error(f"Resume file not found at: {resume_path}")
            return False

        with open(resume_path, "rb") as attachment:
            part = MIMEApplication(attachment.read(), Name=os.path.basename(resume_path))
        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(resume_path)}"'
        msg.attach(part)

        # Send the email via Gmail's SMTP server
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()  # Secure the connection
            server.login(sender_email, sender_password)
            server.send_message(msg)
        logging.info(f"Successfully sent resume to {recipient_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        logging.error("SMTP Authentication Error for resume. Check SENDER_EMAIL and SENDER_PASSWORD (App Password).")
        return False
    except Exception as e:
        # Log the full traceback for detailed debugging
        tb_str = traceback.format_exc()
        logging.error(f"Failed to send email to {recipient_email}. Error: {e}\nTraceback:\n{tb_str}")
        return False

def send_contact_email(name, from_email, subject, message_body):
    """Sends a contact form email to the site owner."""
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')
    recipient_email = sender_email # The email is sent to myself

    # Wrap the entire logic in a try...except block to catch any errors
    # during message creation or sending.
    try:
        if not all([sender_email, sender_password]):
            logging.error("Email configuration (SENDER_EMAIL, SENDER_PASSWORD) is missing for contact.")
            return False
        
        # --- Input Sanitization ---
        # Proactively remove characters from user input that can crash email header creation.
        safe_name = name.replace('\n', ' ').replace('\r', '')
        safe_subject = subject.replace('\n', ' ').replace('\r', '')

        msg = MIMEMultipart()
        msg['From'] = formataddr((safe_name, sender_email))
        msg['To'] = recipient_email
        msg.add_header('Reply-To', from_email)
        msg['Subject'] = f"Portfolio Contact: {safe_subject}"

        # Construct the email body
        full_message = f"You have a new message from your portfolio contact form.\n\n"
        full_message += f"Name: {name}\n"
        full_message += f"Email: {from_email}\n\n"
        full_message += f"Message:\n---\n{message_body}\n---"
        msg.attach(MIMEText(full_message, 'plain'))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        logging.info(f"Successfully sent contact email from {from_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        logging.error("SMTP Authentication Error for contact. Check SENDER_EMAIL and SENDER_PASSWORD (App Password).")
        return False
    except Exception as e:
        # Log the full traceback for detailed debugging
        tb_str = traceback.format_exc()
        logging.error(f"Failed to send contact email from {from_email}. Error: {e}\nTraceback:\n{tb_str}")
        return False

def create_app():
    """Creates and configures the Flask application using the factory pattern."""
    app = Flask(__name__, static_folder=f'{os.path.dirname(os.path.abspath(__file__))}/frontend', static_url_path='')

    # --- Configuration (now loaded from .env or environment variables) ---
    app.config["MONGO_URI"] = os.environ.get('MONGO_URI') # Keep this, as resume request uses it

    # Removed: app.config["RENDER_FRONTEND_URL"] = os.environ.get('RENDER_FRONTEND_URL', '')

    # Rate Limiting configuration
    app.config["RATELIMIT_DEFAULT"] = "200 per day, 50 per hour"
    app.config["RATELIMIT_STORAGE_URI"] = "memory://" # Explicitly set for clarity, silences warning


    # --- Logging Configuration ---
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # --- CORS Configuration ---
    # Since no RENDER_FRONTEND_URL, simplify allowed_origins
    allowed_origins = ["null", "http://127.0.0.1:5500", "http://localhost:5000"]

    # In production on Render, add the service's public URL to the allowed origins.
    # This is crucial for the frontend to be able to call the API when deployed.
    if "RENDER" in os.environ:
        render_url = os.environ.get('RENDER_EXTERNAL_URL')
        if render_url:
            allowed_origins.append(render_url)

    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

    # --- Rate Limiting ---
    limiter.init_app(app)

    # --- Custom JSON Error Handlers ---
    # Ensure that common HTTP errors return JSON instead of the default HTML pages.
    # This prevents the "Unexpected end of JSON input" error on the frontend.
    @app.errorhandler(400) # Bad Request
    def bad_request_handler(e):
        return jsonify(error=f"Bad Request: {e.description}"), 400

    @app.errorhandler(429) # Rate limit exceeded
    def ratelimit_handler(e):
        return jsonify(error=f"Rate limit exceeded: {e.description}"), 429

    @app.errorhandler(500) # Internal Server Error
    def internal_server_error_handler(e):
        # Log the full traceback for unhandled exceptions
        tb_str = traceback.format_exc()
        logging.error(f"An unhandled exception occurred (500 error): {e}\nTraceback:\n{tb_str}")
        return jsonify(error="An internal server error occurred. Please try again later."), 500

    # --- MongoDB Connection ---
    try:
        # Check if MONGO_URI is set before attempting connection
        if not app.config["MONGO_URI"]:
            raise ValueError("MONGO_URI not found. Please set it in your .env file or as an environment variable.")

        client = MongoClient(app.config["MONGO_URI"], tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
        client.admin.command('ping') # Test connection
        app.db = client.portfolio_db
        logging.info("✅ Successfully connected to MongoDB!")
    except (ConnectionFailure, ValueError, ServerSelectionTimeoutError) as e:
        logging.error(f"❌ Error connecting to MongoDB: {e}")
        app.db = None
        # For production, consider re-raising or exiting if DB is absolutely critical.
        # For a portfolio, it might be acceptable to let it run without DB if that's the only issue.


    # --- API Route for Resume Request (Keeps MongoDB storage) ---
    @app.route('/api/request-resume', methods=['POST'])
    @limiter.limit("5 per day")
    def request_resume():
        # This check ensures a JSON response even if DB connection fails
        if app.db is None:
            logging.error("Database connection not established. Cannot process resume request.")
            return jsonify({'error': 'Server error: Database not available.'}), 500

        data = request.get_json()
        name = data.get('name')
        email = data.get('email')

        if not name or not email:
            return jsonify({'error': 'Name and Email are required.'}), 400

        try:
            # MongoDB storage for resume requests is kept here as per your requirement
            resume_requests_collection = app.db.resume_requests
            resume_requests_collection.insert_one({
                'name': name,
                'email': email,
                'timestamp': datetime.utcnow()
            })
            logging.info(f"Resume request saved for: {email}")

            # --- Send the resume via email ---
            if send_email_with_resume(email, name):
                return jsonify({'message': 'Your request has been received! The resume has been sent to your email.'}), 200
            else:
                logging.error(f"Failed to send resume email to {email}, but request was saved.")
                return jsonify({'message': 'Your request was saved, but there was an issue sending the email. I will follow up with you manually.'}), 202

        except Exception as e:
            tb_str = traceback.format_exc()
            logging.error(f"Error processing resume request (MongoDB or email sending): {e}\nTraceback:\n{tb_str}")
            return jsonify({'error': 'An error occurred while processing your resume request.'}), 500

    # --- API Route for Contact Form (NO MongoDB storage) ---
    @app.route('/api/contact', methods=['POST'])
    @limiter.limit("10 per hour")
    def contact_form():
        try: # Added a top-level try-except block here for robust error handling
            data = request.get_json()
            if not data: # This handles cases where the request body isn't valid JSON
                return jsonify({'error': 'Invalid JSON data in request.'}), 400

            name = data.get('name')
            email = data.get('email')
            subject = data.get('subject')
            message = data.get('message')

            if not all([name, email, subject, message]):
                return jsonify({'error': 'All fields (Name, Email, Subject, Message) are required.'}), 400

            # No MongoDB interaction here, directly send email
            if send_contact_email(name, email, subject, message):
                return jsonify({'message': 'Thank you for your message! I will get back to you soon.'}), 200
            else:
                logging.error(f"Failed to send contact email from {email}. (send_contact_email returned False)")
                return jsonify({'error': 'Sorry, there was an error sending your message. Please try again later.'}), 500
        except Exception as e: # Catch any unexpected errors that occur in this route
            tb_str = traceback.format_exc()
            logging.error(f"Critical error in contact_form route: {e}\nTraceback:\n{tb_str}")
            return jsonify({'error': 'An unexpected server error occurred while processing your message. Please try again later.'}), 500

    # --- Serve Frontend ---
    @app.route('/')
    def serve_index():
        return send_from_directory(app.static_folder, 'index.html')

    return app

# This entry point is used for local development.
# For production, Gunicorn will call create_app() directly.
if __name__ == '__main__':
    app = create_app()
    app.run(port=5000, debug=True)