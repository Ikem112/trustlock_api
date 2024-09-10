from datetime import datetime

from flask_jwt_extended import current_user, get_jwt
from functools import wraps
from flask import jsonify
from flask import request


def api_secret_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        api_private_key = request.headers.get("X-API-Key")

        if not api_private_key == current_user.merchant_details.api_secret_key:
            return jsonify({"status": "error", "data": "unauthorized access"}), 401

        return f(*args, **kwargs)

    return decorated_function
