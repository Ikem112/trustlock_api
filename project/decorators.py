from datetime import datetime

from flask_jwt_extended import current_user, get_jwt
from functools import wraps
from flask import jsonify
from flask import request
from project import r_client, db
from project.helpers import redis_confirmation


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
        confirmed = redis_confirmation()
        if not confirmed:
            target_order = Order.query.filter_by(reference_no=ref_no).first()

            if not target_order:
                return (
                    jsonify(
                        {"status": "error", "message": f"order {ref_no} doesn't exist"}
                    ),
                    400,
                )
            return f(*args, **kwargs)

        orders = r_client.lrange("order_ref_nos", 0, -1)
        if ref_no not in orders:
            return (
                jsonify(
                    {"status": "error", "message": f"order {ref_no} doesn't exist"}
                ),
                400,
            )
        return f(*args, **kwargs)

    return decorated_function


def to_be_returned(f):
    from project.merchants.models import Order

    @wraps(f)
    def decorated_function(*args, **kwargs):
        ref_no = kwargs.get("ref_no")
        confirmed = redis_confirmation()
        if not confirmed:
            target_order = Order.query.filter_by(reference_no=ref_no).first()
            if not target_order.product_to_be_returned:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": f"order {ref_no} is not set to be returned",
                        }
                    ),
                    400,
                )
            return f(*args, **kwargs)

        to_return = r_client.get(f"return_{ref_no}")
        if not to_return or to_return == None:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"order {ref_no} is not set to be returned",
                    }
                ),
                400,
            )
        return f(*args, **kwargs)

    return decorated_function
