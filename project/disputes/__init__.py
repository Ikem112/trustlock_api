from flask import Blueprint

# special blueprint for the endpoints for the admin
dispute = Blueprint("dispute", __name__)

from . import dispute_api
