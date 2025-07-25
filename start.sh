#!/usr/bin/env bash
# This command tells Gunicorn to run your Flask app.
# 'app:create_app()' means:
#   - import 'app.py' module
#   - call the 'create_app()' function within it
#   - this function is expected to return your Flask application instance.
# --workers 4 is a good starting point for concurrency.
# --bind 0.0.0.0:$PORT tells Gunicorn to listen on the port Render provides.
gunicorn --worker-class gevent --workers 4 --bind 0.0.0.0:$PORT 'app:create_app()'