import os
from flask import Flask
from flask_cors import CORS
from .config import Config
from .extensions import limiter, mongo

def create_app(config_class=Config):
    """
    Application factory function to create and configure the Flask app.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    mongo.init_app(app)
    limiter.init_app(app)

    # Set up CORS
    frontend_url = os.environ.get('RENDER_FRONTEND_URL', 'http://127.0.0.1:5500')
    CORS(app, resources={r"/api/*": {"origins": frontend_url}})

    # Make the db connection available on the app context
    with app.app_context():
        app.db = mongo.db

    # Import and register blueprints
    from .contact import contact_bp
    from .resume import resume_bp
    from .newsletter import newsletter_bp

    app.register_blueprint(contact_bp, url_prefix='/api')
    app.register_blueprint(resume_bp, url_prefix='/api')
    app.register_blueprint(newsletter_bp, url_prefix='/api')

    return app