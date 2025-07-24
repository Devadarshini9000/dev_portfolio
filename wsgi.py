from api import create_app

# This is the entry point for the Gunicorn server.
# It creates the Flask app instance.
app = create_app()