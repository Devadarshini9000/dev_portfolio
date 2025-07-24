import os
import datetime
import smtplib
import ssl
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
import certifi

load_dotenv()  # Load environment variables from .env file
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

app = Flask(__name__, static_folder='frontend', static_url_path='')

# Enable CORS to allow your frontend to communicate with this backend.
# This configuration is more specific and secure. It allows requests from:
#  - "null": When you open the index.html file locally.
#  - "http://127.0.0.1:5500": A common port for local development servers (like VS Code's Live Server).
#  - Your live frontend URL on Render (replace the placeholder).

allowed_origins = ["null", "http://127.0.0.1:5500"]
render_frontend_url = os.getenv("RENDER_FRONTEND_URL")
if render_frontend_url:
    allowed_origins.append(render_frontend_url)

CORS(app, resources={
    r"/api/*": {
        "origins": allowed_origins
    }
})

# --- Serve Frontend ---
# This route will serve your main portfolio page (index.html)
@app.route('/')
def serve_index():
    return send_from_directory('frontend', 'index.html')

# --- MongoDB Connection ---
try:
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI not found in environment variables.")
    client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
    # Test the connection
    client.admin.command('ping')
    db = client.portfolio_db # Use a specific database name
    contact_form_collection = db.contact_form # Use the collection you created
    newsletter_collection = db.newsletter_subscribers # New collection for subscribers
    resume_requests_collection = db.resume_requests # New collection for resume requests
    print("✅ Successfully connected to MongoDB!")
except (ConnectionFailure, ValueError) as e:
    print(f"❌ Error connecting to MongoDB: {e}")
    contact_form_collection = None
    newsletter_collection = None
    resume_requests_collection = None

# --- Helper Functions ---
def is_valid_email(email):
    """A simple regex check for email format."""
    return email and re.match(r"[^@]+@[^@]+\.[^@]+", email)

def send_email(recipient, subject, body, attachment_path=None, attachment_filename=None):
    """Sends an email using Gmail's SMTP server and handles attachments."""
    if not SENDER_EMAIL or not EMAIL_PASSWORD:
        print("⚠️ Email credentials (SENDER_EMAIL, EMAIL_PASSWORD) not set. Skipping email.")
        return False, "Email credentials not configured."

    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        if attachment_path and attachment_filename:
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={attachment_filename}")
            msg.attach(part)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient, msg.as_string())
        print(f"✅ Email sent successfully to {recipient}!")
        return True, "Email sent successfully."
    except Exception as e:
        print(f"⚠️ Could not send email to {recipient}. Error: {e}")
        return False, str(e)

@app.route('/api/contact', methods=['POST'])
def handle_contact_form():
    if contact_form_collection is None:
        return jsonify({"error": "Database connection not available"}), 503

    data = request.get_json()

    # --- Enhanced Validation ---
    if not data or not data.get('name') or not data.get('email') or not data.get('message'):
        return jsonify({"error": "Missing required fields: name, email, and message are required."}), 400

    # Email format validation
    email = data.get('email')
    if not is_valid_email(email):
        return jsonify({"error": "Invalid email address format."}), 400

    message = {
        "name": data.get('name'),
        "email": email,
        "subject": data.get('subject', 'No Subject'), # Handle optional field
        "message": data.get('message'),
        "timestamp": datetime.datetime.utcnow(),
        "ip_address": request.headers.get('X-Forwarded-For', request.remote_addr)
    }

    try:
        contact_form_collection.insert_one(message)

        # --- Send Email Notification ---
        # This part sends you an email when someone submits the form.
        receiver_email = "devadarshini027@gmail.com"  # Your destination email
        email_subject = f"New Portfolio Contact: {message['subject']}"
        email_body = f"""
You have a new message from your portfolio contact form:

Name: {message['name']}
Email: {message['email']}
IP Address: {message.get('ip_address', 'N/A')}

Message:
{message['message']}
        """
        # The helper function handles logging and errors internally.
        send_email(receiver_email, email_subject, email_body)

        return jsonify({"success": True, "message": "Message received successfully!"}), 201
    except Exception as e:
        print(f"❌ Error inserting message into DB: {e}")
        return jsonify({"error": "An internal error occurred while saving the message."}), 500

@app.route('/api/subscribe', methods=['POST'])
def handle_subscription():
    if newsletter_collection is None:
        return jsonify({"error": "Database connection not available"}), 503

    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email address is required."}), 400

    if not is_valid_email(email):
        return jsonify({"error": "Invalid email address format."}), 400

    try:
        # Check if email already exists to prevent duplicates
        if newsletter_collection.find_one({"email": email}):
            return jsonify({"success": True, "message": "You are already subscribed!"}), 200

        newsletter_collection.insert_one({"email": email, "timestamp": datetime.datetime.utcnow()})
        print(f"✅ New newsletter subscriber: {email}")
        return jsonify({"success": True, "message": "Thank you for subscribing!"}), 201
    except Exception as e:
        print(f"❌ Error inserting subscriber into DB: {e}")
        return jsonify({"error": "An internal error occurred."}), 500

@app.route('/api/request-resume', methods=['POST'])
def handle_resume_request():
    if resume_requests_collection is None:
        return jsonify({"error": "Database connection not available"}), 503

    data = request.get_json()
    name = data.get('name')
    email = data.get('email')

    if not name or not email:
        return jsonify({"error": "Name and email are required."}), 400

    if not is_valid_email(email):
        return jsonify({"error": "Invalid email address format."}), 400

    # Prepare the record for the database
    request_record = {
        "name": name,
        "email": email,
        "timestamp": datetime.datetime.utcnow(),
        "email_status": "pending" # Default status
    }

    try:
        # Prepare and send the email with the resume attached
        email_subject = "Here is a copy of Devadarshini's Resume"
        email_body = f"""Hello {name},

Thank you for your interest in my profile!

Please find my resume attached to this email. I look forward to connecting with you soon.

Best regards,
Devadarshini P"""
        attachment_path = "frontend/assets/resume.pdf"
        attachment_filename = "Devadarshini_P_Resume.pdf"

        success, status_message = send_email(
            email, email_subject, email_body, attachment_path, attachment_filename
        )

        # Update the record based on email success/failure
        if success:
            request_record["email_status"] = "sent"
        else:
            request_record["email_status"] = "failed"
            request_record["email_error"] = status_message

        # Now, store the complete record with the email status in the database
        resume_requests_collection.insert_one(request_record)
        print(f"✅ DB record created for resume request from: {name} ({email}) - Status: {request_record['email_status']}")
        
        return jsonify({"success": True, "message": "Thank you! The resume has been sent to your email."}), 200
    except Exception as e:
        print(f"❌ Error inserting resume request into DB: {e}")
        return jsonify({"error": "An internal error occurred."}), 500

if __name__ == '__main__':
    # When deploying to Render, Gunicorn will be used to run the app.
    # This app.run() block is now only for very specific local execution.
    app.run(port=5000)
