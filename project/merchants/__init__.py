from flask import Blueprint

# special blueprint for the endpoints for the admin
merchant = Blueprint("merchant", __name__)

from . import merchant_views
