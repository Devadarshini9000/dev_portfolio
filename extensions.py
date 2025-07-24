from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize extensions here to avoid circular imports and make them globally available.
limiter = Limiter(key_func=get_remote_address)