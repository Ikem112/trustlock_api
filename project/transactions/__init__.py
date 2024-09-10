from flask import Blueprint

# special blueprint for the endpoints for the admin
transaction = Blueprint("transaction", __name__)

from . import transaction_api
