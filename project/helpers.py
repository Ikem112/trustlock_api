from jinja2 import Environment, FileSystemLoader
import redis
import math


def get_email_html_template(file_name, name, verification_url):
    env = Environment(
        loader=FileSystemLoader(
            "C:\\Users\\VP\\OneDrive\\Desktop\\trustLock_api\\project\\html_templates"
        )
    )

    template = env.get_template(file_name)

    html_content = template.render(
        {"first_name": name, "verification_url": verification_url}
    )

    return html_content


def get_payment_verification_template(file_name, payload: dict):
    env = Environment(
        loader=FileSystemLoader(
            "C:\\Users\\VP\\OneDrive\\Desktop\\trustLock_api\\project\\html_templates"
        )
    )

    template = env.get_template(file_name)

    html_content = template.render(
        {
            "customer_name": payload["customer_name"],
            "amount_paid": payload["amount_paid"],
            "product_name": payload["product_name"],
            "transaction_id": payload["transaction_id"],
            "payment_date": payload["payment_date"],
            "year": "2024",
        }
    )

    return html_content


r_client = redis.Redis(host="localhost", port=6379, db=0)


def calculate_fees(price: float) -> tuple:
    """
    a function to calculate the fees to be paid given the price a customer wants to pay for a product or service
    """

    def round_up(value, decimal_places):
        factor = 10**decimal_places
        return math.ceil(value * factor) / factor

    if 0 <= price <= 100_000.00:
        escrow_percent = 2.6
        escrow_fee = (escrow_percent / 100) * price
        escrow_fee = 2_000.00 if escrow_fee <= 2_000.00 else escrow_fee
        escrow_fee = round_up(escrow_fee, 2)
        process_fee = 1_000.00
        return escrow_fee, process_fee, escrow_percent
    elif 100_000.01 <= price <= 500_000.00:
        escrow_percent = 1.7
        escrow_fee = (escrow_percent / 100) * price
        escrow_fee = 3_000.00 if escrow_fee <= 3_000.00 else escrow_fee
        escrow_fee = round_up(escrow_fee, 2)
        process_fee = 1_000.00
        return escrow_fee, process_fee, escrow_percent
    elif 500_000.01 <= price <= 1_000_000.00:
        escrow_percent = 1.2
        escrow_fee = (escrow_percent / 100) * price
        escrow_fee = 9_000.00 if escrow_fee <= 9_000.00 else escrow_fee
        escrow_fee = round_up(escrow_fee, 2)
        process_fee = 2_500.00
        return escrow_fee, process_fee, escrow_percent
    elif 1_000_000.01 <= price <= 5_000_000.00:
        escrow_percent = 1.0
        escrow_fee = (escrow_percent / 100) * price
        escrow_fee = 13_000.00 if escrow_fee <= 13_000.00 else escrow_fee
        escrow_fee = round_up(escrow_fee, 2)
        process_fee = 2_500.00
        return escrow_fee, process_fee, escrow_percent
    elif 5_000_000.01 <= price <= 10_000_000.00:
        escrow_percent = 0.8
        escrow_fee = (escrow_percent / 100) * price
        escrow_fee = 50_000.00 if escrow_fee <= 50_000.00 else escrow_fee
        escrow_fee = round_up(escrow_fee, 2)
        process_fee = 5_000.00
        return escrow_fee, process_fee, escrow_percent
    else:
        escrow_percent = 0.6
        escrow_fee = (escrow_percent / 100) * price
        escrow_fee = 80_000.00 if escrow_fee <= 80_000.00 else escrow_fee
        escrow_fee = round_up(escrow_fee, 2)
        process_fee = 5_000.00
        return escrow_fee, process_fee, escrow_percent
