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


def order_exists(f):
    from project.merchants.models import Order

    @wraps(f)
    def decorated_function(*args, **kwargs):

        ref_no = kwargs.get("ref_no")
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if not target_order:
            return (
                jsonify(
                    {"status": "error", "message": f"order {ref_no} doesn't exist"}
                ),
                400,
            )
        return f(*args, **kwargs)

    return decorated_function
