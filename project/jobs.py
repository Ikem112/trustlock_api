from project.merchants.models import (
    Merchant,
    MerchantDetails,
    Order,
    Customer,
    TransactionTimeline,
)
from project import db
from datetime import datetime, timedelta, time, date


def check_inspection_dates():
    orders = Order.query.filter_by(product_inspected=False).all()

    for order in orders():
        inspection_time = order.inspection_time
        date_of_delivery = order.date_product_delivered

        day_of_final_inspection = date_of_delivery + timedelta(days=inspection_time)

        if order.extra_time_elapsed:
            # send email to inform them that transaction has been closed

            new_timeline = TransactionTimeline(
                event_occurrance=f"Inspection time elapsed, money has been sent out to the seller in full",
                order=order,
            )

        if datetime.utcnow() >= day_of_final_inspection:
            # send email to remind them to inspect product or money will be paid in full

            new_timeline = TransactionTimeline(
                event_occurrance=f"Email sent for a reminder to inspect order product {order.reference_no} and extra time of 1 day was added",
                order=order,
            )

            order.extra_time_initiated = True
