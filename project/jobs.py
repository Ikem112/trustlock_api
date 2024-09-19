from project import create_app

app = create_app()


def check_inspection_dates():
    with app.app_context():

        from project.merchants.models import (
            Merchant,
            MerchantDetails,
            Order,
            Customer,
            TransactionHistory,
            TransactionTimeline,
        )
        from project import db
        from datetime import datetime, timedelta, time, date
        import uuid

        orders = Order.query.filter_by(product_inspected=False).all()

        for order in orders:
            print(order.id)
            if order.product_delivered:
                inspection_time = order.inspection_time
                date_of_delivery = order.date_product_delivered
                day_of_final_inspection = date_of_delivery + timedelta(
                    days=inspection_time
                )

                timeline = TransactionTimeline.query.filter(
                    TransactionTimeline.event_occurrance.like(
                        "Email sent for a reminder to inspect order product%"
                    )
                ).first()
                if not timeline:
                    print(f"something went wrong with order {order.id} records")

                if (order.extra_time_elapsed and not order.order_closed) or (
                    datetime.utcnow >= timeline.date + timedelta(days=1)
                ):
                    order.extra_time_elapsed = True
                    db.session.commit()
                    if not order.amount_verified:
                        new_timeline = TransactionTimeline(
                            event_occurrance=f"Auto payout failed due to data inconsisteny",
                            order=order,
                        )
                        print(
                            f"Auto payout failed due to data inconsisteny for order {order.id}"
                        )

                    # send email to inform them that transaction has been closed
                    # transfer money to seller using paystack

                    order.order_closed = True
                    order.date_closed = datetime.utcnow

                    new_timeline = TransactionTimeline(
                        event_occurrance=f"Inspection time elapsed, money has been sent out to the seller in full, order has been closed",
                        order=order,
                    )

                    new_transaction = TransactionHistory(
                        amount=order.product_amount,
                        trans_reference=f"auto_credit_{uuid.uuid4().hex()}",
                        sender="TrustLock",
                        receiver="Seller",
                        trans_action="TrustLock Debit",
                        description="Automatic credit of seller due to failed buyer inspection confirmation within set period",
                        order=order,
                    )

                    db.session.add(new_timeline)
                    db.session.add(new_transaction)

                    db.session.commit()

                    print(f"order {order.id} has been closed and money has been sent.")

                if datetime.utcnow() >= day_of_final_inspection:
                    # send email to remind them to inspect product or money will be paid in full

                    new_timeline = TransactionTimeline(
                        event_occurrance=f"Email sent for a reminder to inspect order product {order.reference_no} and extra time of 1 day was added",
                        order=order,
                    )

                    order.extra_time_initiated = True

                    print(f"extra time initiated for order {order.id}")
            else:
                pass
        print("task completed successfully", datetime.utcnow())
        return "task completed succcssfully"
