from app import create_app

# The WSGI entry point. Gunicorn will look for this 'app' object.
app = create_app()