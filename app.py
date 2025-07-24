from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
import certifi

# Import configurations and blueprints
from config import Config
from api.contact import contact_bp
from api.newsletter import newsletter_bp
from api.resume import resume_bp

def create_app():
    """Creates and configures the Flask application using the factory pattern."""
    app = Flask(__name__, static_folder=f'{Config.APP_ROOT}/frontend', static_url_path='')
    app.config.from_object(Config)

    # --- Logging Configuration ---
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # --- CORS Configuration ---
    allowed_origins = ["null", "http://127.0.0.1:5500"]
    if Config.RENDER_FRONTEND_URL:
        allowed_origins.append(Config.RENDER_FRONTEND_URL)
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

    # --- Rate Limiting ---
    # Note: Specific limits should be applied in each blueprint file.
    Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"])

    # --- MongoDB Connection ---
    try:
        if not Config.MONGO_URI:
            raise ValueError("MONGO_URI not found in environment variables.")
        client = MongoClient(Config.MONGO_URI, tlsCAFile=certifi.where())
        client.admin.command('ping')
        # Attach the database client to the app context for blueprint access
        app.db = client.portfolio_db
        logging.info("✅ Successfully connected to MongoDB!")
    except (ConnectionFailure, ValueError) as e:
        logging.error(f"❌ Error connecting to MongoDB: {e}")
        app.db = None # Ensure app.db exists even on failure

    # --- Register Blueprints ---
    app.register_blueprint(contact_bp, url_prefix='/api')
    app.register_blueprint(newsletter_bp, url_prefix='/api')
    app.register_blueprint(resume_bp, url_prefix='/api')

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
