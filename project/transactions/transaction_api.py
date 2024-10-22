from datetime import timedelta, datetime

import hmac
import hashlib
import os
from dotenv import load_dotenv
import uuid
from nanoid import generate
from flask import request, jsonify, current_app

from flask_jwt_extended import (
    get_jwt_identity,
    create_access_token,
    jwt_required,
    current_user,
    get_jwt,
)
import re
import json

from project import db, jwt, bcrypt, r_client
from project.helpers import calculate_fees, signature_validation
from . import transaction
from project.api_services.paystack_api import PaystackClient
from project.api_services.kora_api import KoraClient
from ..merchants.models import (
    Merchant,
    MerchantSchema,
    MerchantDetails,
    MerchantDetailsSchema,
    OrderSchema,
    Customer,
    OrderDetails,
    OrderDetailsSchema,
    DeliveryInformation,
    DeliveryInformationSchema,
    CustomerSchema,
    TransactionCondition,
    TransactionHistorySchema,
    TransactionHistory,
    Order,
    TransactionConditionSchema,
    TransactionTimeline,
    TransactionTimelineSchema,
    BusinessDetails,
    BusinessDetailsSchema,
    Dispute,
    DisputeSchema,
)

from ..decorators import api_secret_key_required, order_exists

load_dotenv()


@transaction.post("get_amount_quote")
@jwt_required()
@api_secret_key_required
def get_amount_quote():
    try:
        data = request.get_json()
        price = data.get("price")
        price = float(price)

        escrow_fees, process_fees, escrow_percent = calculate_fees(price)
        total_fees = escrow_fees + process_fees

        return (
            jsonify(
                {
                    "status": "success",
                    "prices": {
                        "escrow_percent": escrow_percent,
                        "escrow_fees": escrow_fees,
                        "process_fees": process_fees,
                        "total_fees": total_fees,
                    },
                }
            ),
            200,
        )

    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.post("initialize_order")
@jwt_required()
@api_secret_key_required
def initialize_order():
    try:

        if not current_user.account_creation_complete:
            return (
                jsonify(status="error", message="please complete account creation"),
                400,
            )

        data = request.get_json()

        if not data.get("customer_details"):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "please ensure customer details are added",
                    }
                ),
                400,
            )

        customer_details = data.get("customer_details")

        current_merchant = Merchant.query.filter_by(id=current_user.id).first()
        ref_no = generate()
        escrow_fee, process_fee, escrow_percent = calculate_fees(
            data.get("product_amount")
        )
        total_fees = escrow_fee + process_fee
        amount_to_pay = total_fees + data.get("product_amount")

        customer_details = {
            key: value.lower()
            if isinstance(value, str) and key != "customer_address"
            else value
            for key, value in customer_details.items()
        }

        new_order = Order(
            reference_no=ref_no,
            partial_dispersals=data.get("partial_dispersals"),
            merchant=current_merchant,
        )

        new_order_details = OrderDetails(
            product_name=data.get("product_name"),
            product_category=data.get("product_category"),
            product_description=data.get("product_description"),
            product_amount=data.get("product_amount"),
            escrow_percent=escrow_percent,
            escrow_fee=escrow_fee,
            process_fee=process_fee,
            amount_to_pay=amount_to_pay,
            amount_to_balance=amount_to_pay,
            amount_to_partially_disburse=data.get("amount_to_partially_disburse"),
            amount_remaining_to_be_disbursed=data.get("product_amount"),
            product_inspection_time=data.get("product_inspection_time"),
            product_delivery_time=data.get("product_delivery_time"),
            total_amount_to_be_disbursed=data.get("product_amount"),
            current_holdings_amount=0.0,
            details_metadata=data.get("metadata"),
            order=new_order,
        )

        customer = Customer(
            first_name=customer_details.get("customer_first_name"),
            last_name=customer_details.get("customer_last_name"),
            phone_no=customer_details.get("customer_phone_no"),
            email_address=customer_details.get("customer_email_address"),
            country=customer_details.get("customer_country"),
            city=customer_details.get("customer_city"),
            address=customer_details.get("customer_address"),
            order=new_order,
        )

        timeline_update = TransactionTimeline(
            event_occurrance=f"Order Success fully created with ref_no {ref_no}",
            category="Order Creation",
            order=new_order,
        )

        order_schema = OrderSchema()
        order = order_schema.dump(new_order)
        r_client.rpush("order_ref_nos", ref_no)
        db.session.add(new_order)
        db.session.add(new_order_details)
        db.session.add(customer)
        db.session.add(timeline_update)
        db.session.commit()

        return jsonify(
            {
                "status": "success",
                "message": "successfully initiated order",
                "order": order,
                "escrow_fee": escrow_fee,
                "process_fee": process_fee,
                "amount_to_pay": amount_to_pay,
            }
        )
    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.get("get_all_orders")
@jwt_required()
@api_secret_key_required
def get_all_orders():
    try:
        orders = Order.query.filter_by(merchant_id=current_user.id)

        order_schema = OrderSchema(many=True)

        schema = order_schema.dump(orders)

        return (
            jsonify(
                {"status": "success", "message": "retrieved all orders", "data": schema}
            ),
            200,
        )

    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.get("get_order/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def get_order(ref_no):
    try:
        order = Order.query.filter_by(reference_no=ref_no).first()

        order_schema = OrderSchema()

        schema = order_schema.dump(order)

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"retrieved order with ref_no {ref_no}",
                    "data": schema,
                }
            ),
            200,
        )

    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.post("set_conditions/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def set_conditions(ref_no):
    try:
        data = request.get_json()

        if not ref_no:
            return (
                jsonify(
                    {"status": "error", "message": "please pass ref no into the URL"}
                ),
                400,
            )

        target_order = Order.query.filter_by(reference_no=ref_no).first()
        if not target_order:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"order with ref no {ref_no} was not found",
                    }
                ),
                400,
            )

        conditions = data.get("conditions")

        for condition in conditions:

            new_condition = TransactionCondition(
                condition_title=condition.get("condition_title"),
                condition_description=condition.get("condition_description"),
                partial_disburse_requisite=condition.get(
                    "partial_disburse_requisite", False
                )
                if target_order.partial_disbursements
                else None,
                order=target_order,
            )

            new_timeline = TransactionTimeline(
                event_occurrance=f"Condition '{condition.get('condition_title')}' has been set",
                category="Conditions",
                order=target_order,
            )

            db.session.add_all([new_condition, new_timeline])

        target_order.conditions_set = True
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "sucess",
                    "message": "added order conditions",
                    "order_ref_no": ref_no,
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.post("initiate_product_payment/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def initiate_product_payment(ref_no):
    try:

        current_merchant = Merchant.query.filter_by(id=current_user.id).first()
        target_order = Order.query.filter_by(
            merchant_id=current_merchant.id, reference_no=ref_no
        ).first()

        if target_order.full_payment_verified:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "payment for order already completed",
                    }
                ),
                400,
            )

        if not target_order.conditions_set:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "please ensure conditions are set before proceeding with payment",
                    }
                ),
                400,
            )

        customer_email = target_order.customer.email_address
        amount_to_pay = (
            target_order.order_details.amount_to_pay
            if not target_order.need_to_balance
            else target_order.order_details.amount_to_balance
        )
        amount_to_pay = amount_to_pay * 100

        paystack_client = PaystackClient()

        payload = {
            "amount": amount_to_pay,
            "email": customer_email,
            "first_name": target_order.customer.first_name,
            "last_name": target_order.customer.last_name,
            "currency": "NGN",
            "callback_url": "https://elegant-buck-deciding.ngrok-free.app/api/dev/v1/verify_payment",
        }

        response, status_code = paystack_client.initialize_transaction(payload)

        if not response["status"]:
            return (
                jsonify(
                    {"status": "error", "message": "something went wrong, please hold"}
                ),
                400,
            )
        trans_ref_no = response["data"]["reference"]
        filler1 = "completion"
        filler2 = "full"
        timeline_update = TransactionTimeline(
            event_occurrance=f"Transaction for {(filler1 if target_order.need_to_balance else filler2)} payment of escrow service for order {ref_no} succesfully initialized with ref_no {trans_ref_no}",
            category="Deposit Initiation",
            order=target_order,
        )

        db.session.add(timeline_update)
        target_order.payment_initiated = True
        target_order.date_updated = datetime.utcnow()
        db.session.commit()

        info_dict = {
            "order_refno": ref_no,
            "need_to_balance": True if target_order.need_to_balance else False,
        }
        r_client.set(f"ref_no_{trans_ref_no}", json.dumps(info_dict))

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "payment initialized successfully",
                    "data": response["data"],
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.get("verify_payment")
@jwt_required()
@api_secret_key_required
def verify_payment():
    try:

        ref_no = request.args.get("reference")

        paystack_client = PaystackClient()

        response, status_code = paystack_client.paystack_verify_transaction(ref_no)

        if not response["status"]:
            return jsonify({"status": "error", "message": response["message"]}), 400

        info_dict = r_client.get(f"ref_no_{ref_no}")
        info_dict = json.loads(info_dict)
        order_ref_no = info_dict["order_refno"]

        target_order = Order.query.filter_by(reference_no=order_ref_no).first()

        if target_order.full_payment_verified:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "payment for order already completed",
                    }
                ),
                400,
            )

        amount_to_pay = target_order.order_details.amount_to_pay

        naira_amount = response["data"]["amount"] / 100

        if info_dict["need_to_balance"]:
            amount_to_balance = target_order.order_details.amount_to_balance
            if naira_amount < amount_to_balance:
                balance_payment = amount_to_balance - naira_amount

                new_trans_entry = TransactionHistory(
                    amount=naira_amount,
                    trans_reference=f'ps_res_{response["data"]["reference"]}',
                    sender=f"{target_order.customer.first_name} {target_order.customer.last_name}",
                    status="Success",
                    remark=f"Paystack Services to TrustLock Holdings for user {current_user.id}",
                    receiver="TrustLock Holdings",
                    description=f"Partial payment of product of order {order_ref_no}, awaiting balance payment of {balance_payment}",
                    order=target_order,
                )

                new_timeline = TransactionTimeline(
                    event_occurrance=f"Partial payment of {naira_amount} paid into TrustLock Holdings.",
                    category="Order Deposit",
                    order=target_order,
                )

                db.session.add(new_trans_entry)
                db.session.add(new_timeline)

                target_order.order_details.current_holdings_amount += naira_amount
                target_order.order_details.amount_paid += naira_amount
                target_order.order_details.amount_to_balance = balance_payment
                target_order.order_details.date_updated = datetime.utcnow()

                db.session.commit()

                from project.api_services.sendgrid_api import Mailer

                mailer = Mailer()

                formatted_price = "{:,.2f}".format(naira_amount)
                payload = {
                    "customer_name": current_user.orders.customer.first_name,
                    "amount_paid": f"N {formatted_price}.",
                    "product_name": target_order.order_details.product_name,
                    "transaction_id": response["data"]["reference"],
                    "payment_date": datetime.utcnow(),
                }

                data, status = mailer.send_payment_confirmation_mail(
                    current_user.orders.customer.email_address, payload
                )
                print(data, status)
                return (
                    jsonify(
                        {
                            "status": "success",
                            "message": "amount verified. However, full amount hasn't been paid. See advise for completing payment for order commencement",
                            "data": {"remaining_balance": balance_payment},
                        }
                    ),
                    200,
                )

            if naira_amount >= amount_to_balance:
                new_trans_entry = TransactionHistory(
                    amount=naira_amount,
                    trans_reference=f'ps_res_{response["data"]["reference"]}',
                    sender=f"{target_order.customer.first_name} {target_order.customer.last_name}",
                    receiver="TrustLock Holdings",
                    status="Success",
                    remark=f"Paystack Services to TrustLock Holdings for user {current_user.id}",
                    description=f"Full balance payment of product of order {order_ref_no}",
                    order=target_order,
                )

                new_timeline = TransactionTimeline(
                    event_occurrance=f"Full balance payment of {naira_amount} paid into TrustLock Holdings. Order has been commenced",
                    category="Order Deposit",
                    order=target_order,
                )

                db.session.add(new_trans_entry)
                db.session.add(new_timeline)

                target_order.order_details.amount_paid += naira_amount
                target_order.order_details.current_holdings_amount += naira_amount
                target_order.order_details.amount_to_balance = 0.0
                target_order.product_overpay = (
                    True if naira_amount > amount_to_balance else False
                )
                target_order.order_details.amount_overflow = (
                    (naira_amount - amount_to_balance)
                    if naira_amount > amount_to_balance
                    else 0.0
                )
                target_order.full_payment_verified = True
                target_order.order_commenced = True
                target_order.delivery_time_triggered = True
                target_order.date_commenced = datetime.utcnow()
                target_order.need_to_balance = False
                target_order.date_updated = datetime.utcnow()
                db.session.commit()

                from project.api_services.sendgrid_api import Mailer

                mailer = Mailer()

                formatted_price = "{:,.2f}".format(naira_amount)
                payload = {
                    "customer_name": (target_order.customer.first_name).capitalize(),
                    "amount_paid": f"N {formatted_price}.",
                    "product_name": target_order.order_details.product_name,
                    "transaction_id": response["data"]["reference"],
                    "payment_date": datetime.utcnow(),
                }

                data, status = mailer.send_payment_confirmation_mail(
                    target_order.customer.email_address, payload
                )

                return (
                    jsonify(
                        {
                            "status": "success",
                            "message": "amount verified, Full amount paid",
                        }
                    ),
                    200,
                )

        if naira_amount < amount_to_pay:
            balance_payment = amount_to_pay - naira_amount
            new_trans_entry = TransactionHistory(
                amount=naira_amount,
                trans_reference=f'ps_res_{response["data"]["reference"]}',
                sender=f"{target_order.customer.first_name} {target_order.customer.last_name}",
                status="Success",
                remark=f"Paystack Services to TrustLock Holdings for user {current_user.id}",
                receiver="TrustLock Holdings",
                description=f"Partial payment of product of order {order_ref_no}, awaiting balance payment of {balance_payment}",
                order=target_order,
            )

            new_timeline = TransactionTimeline(
                event_occurrance=f"Partial payment of {naira_amount} paid into TrustLock Holdings.",
                category="Order Deposit",
                order=target_order,
            )

            db.session.add(new_trans_entry)
            db.session.add(new_timeline)

            target_order.order_details.current_holdings_amount = naira_amount
            target_order.order_details.amount_paid = naira_amount
            target_order.order_details.amount_to_balance = balance_payment
            target_order.order_details.date_updated = datetime.utcnow()
            target_order.need_to_balance = True

            db.session.commit()

            from project.api_services.sendgrid_api import Mailer

            mailer = Mailer()

            formatted_price = "{:,.2f}".format(naira_amount)
            payload = {
                "customer_name": current_user.orders.customer.first_name,
                "amount_paid": f"N {formatted_price}.",
                "product_name": target_order.order_details.product_name,
                "transaction_id": response["data"]["reference"],
                "payment_date": datetime.utcnow(),
            }

            data, status = mailer.send_payment_confirmation_mail(
                current_user.orders.customer.email_address, payload
            )
            print(data, status)
            # MAKE THIS A THREAD!!!!!
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "amount verified. However, full amount hasn't been paid. See advise for completing payment for order commencement",
                        "data": {"remaining_balance": balance_payment},
                    }
                ),
                200,
            )

        if naira_amount >= amount_to_pay:
            new_trans_entry = TransactionHistory(
                amount=naira_amount,
                trans_reference=f'ps_res_{response["data"]["reference"]}',
                sender=f"{target_order.customer.first_name} {target_order.customer.last_name}",
                receiver="TrustLock Holdings",
                status="Success",
                remark=f"Paystack Services to TrustLock Holdings for user {current_user.id}",
                description=f"Full payment of product of order {order_ref_no}",
                order=target_order,
            )

            new_timeline = TransactionTimeline(
                event_occurrance=f"Full payment of {naira_amount} paid into TrustLock Holdings. Order has been commenced",
                category="Order Deposit",
                order=target_order,
            )

            db.session.add(new_trans_entry)
            db.session.add(new_timeline)

            target_order.order_details.amount_paid = naira_amount
            target_order.order_details.current_holdings_amount = naira_amount
            target_order.product_overpay = (
                True if naira_amount > amount_to_pay else False
            )
            target_order.order_details.amount_overflow = (
                (naira_amount - amount_to_pay) if naira_amount > amount_to_pay else 0.0
            )
            target_order.order_details.amount_to_balance = 0.00
            target_order.full_payment_verified = True
            target_order.delivery_time_triggered = True
            target_order.order_commenced = True
            target_order.date_commenced = datetime.utcnow()
            target_order.date_updated = datetime.utcnow()
            db.session.commit()

            from project.api_services.sendgrid_api import Mailer

            mailer = Mailer()

            formatted_price = "{:,.2f}".format(naira_amount)
            payload = {
                "customer_name": (target_order.customer.first_name).capitalize(),
                "amount_paid": f"N {formatted_price}.",
                "product_name": target_order.order_details.product_name,
                "transaction_id": response["data"]["reference"],
                "payment_date": datetime.utcnow(),
            }

            data, status = mailer.send_payment_confirmation_mail(
                target_order.customer.email_address, payload
            )

            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "amount verified, Full amount paid",
                    }
                ),
                200,
            )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.put("confirm_product_sentout/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def confirm_product_sentout(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if not (target_order.full_payment_verified and target_order.order_commenced):
            return (
                jsonify({"status": "error", "message": "payment hasnt been made"}),
                400,
            )

        if target_order.product_sent_out:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"order {ref_no} has already been sent out for delivery",
                    }
                ),
                200,
            )

        target_order.product_sent_out = True
        target_order.date_updated = datetime.utcnow()

        new_timeline = TransactionTimeline(
            event_occurrance=f"Order {ref_no} has just been sent out for delivey",
            category="Delivery Sendout",
            order=target_order,
        )

        db.session.add(new_timeline)
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "seller successfully sent out product",
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.put("seller_confirm_delivery/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def seller_confirm_delivery(ref_no):
    try:

        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if not target_order.product_sent_out:
            return (
                jsonify({"status": "error", "message": "product hasnt been sentout"}),
                400,
            )

        if target_order.seller_confirm_delivery:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"delivery of order {ref_no} has already been confirmed by seller",
                    }
                ),
                400,
            )

        # send a mail to buyer that product has beeen successfully delivered

        target_order.seller_confirm_delivery = True
        target_order.date_seller_confirm_delivery = datetime.utcnow()
        target_order.date_updated = datetime.utcnow()

        new_timeline = TransactionTimeline(
            event_occurrance=f"Order {ref_no} has just been confirmed by seller as delivered, awaiting buyer confirmation",
            category="Delivery Verification",
            order=target_order,
        )

        db.session.add(new_timeline)
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "seller successfully comnfirmed delivery",
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.put("buyer_confirm_delivery/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def buyer_confirm_delivery(ref_no):

    try:

        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if not target_order.product_sent_out:
            return (
                jsonify({"status": "error", "message": "product hasnt been sentout"}),
                400,
            )

        if target_order.buyer_confirm_delivery:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"delivery of order {ref_no} has already been confirmed by buyer",
                    }
                ),
                400,
            )

        target_order.seller_confirm_delivery = True
        target_order.buyer_confirm_delivery = True
        target_order.inspection_time_triggered = True
        target_order.date_buyer_confirm_delivery = datetime.utcnow()
        target_order.date_updated = datetime.utcnow()

        new_timeline = TransactionTimeline(
            event_occurrance=f"Order {ref_no} has just been confirmed by buyer as delivered, inspection time triggered",
            category="Delivery Verification",
            order=target_order,
        )

        db.session.add(new_timeline)
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "buyer successfully comnfirmed delivery",
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.get("retrieve_conditions/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def retrieve_conditions(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        target_conditions = target_order.transaction_condition

        conditions_schema = TransactionConditionSchema(many=True)

        conditions = conditions_schema.dump(target_conditions)

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "conditions retrieved successfully",
                    "data": conditions,
                }
            ),
            200,
        )

    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.put("validate_conditions/<ref_no>/<con_id>")
@jwt_required()
@api_secret_key_required
@order_exists
def validate_conditions(ref_no, con_id):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if not target_order.buyer_confirm_delivery:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "please ensure product has been delivered before proceeding to validate conditions",
                    }
                ),
                400,
            )

        target_condition = TransactionCondition.query.filter_by(
            id=con_id, order=target_order
        ).first()
        if not target_condition:
            return (
                jsonify({"status": "error", "message": "condition doesnt exist"}),
                400,
            )

        if not target_condition.condition_met:
            target_condition.condition_met = True
            target_condition.date_met = datetime.utcnow()
            new_timeline = TransactionTimeline(
                event_occurrance=f"Condition {target_condition.id} has been confirmed as met",
                category="Condition Confirmation",
                order=target_order,
            )
            target_order.date_updated = datetime.utcnow()
            db.session.add(new_timeline)
            db.session.commit()

            all_valid = all(
                con.condition_met == True for con in target_order.transaction_condition
            )
            target_order.conditions_met = True if all_valid else False
            target_order.date_updated = (
                datetime.utcnow() if all_valid else target_order.date_updated
            )
            db.session.commit()

            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "condition succcesfully marked as met",
                    }
                ),
                200,
            )

        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "condition has already been marked as met",
                    }
                ),
                400,
            )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.put("validate_all_conditions/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def validate_all_conditions(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if not target_order.buyer_confirm_delivery:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "please ensure product has been delivered before proceeding to validate conditions",
                    }
                ),
                400,
            )

        all_conditions_met = all(
            condition.condition_met == True
            for condition in target_order.transaction_condition
        )

        if all_conditions_met:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "all conditions have already been marked as met",
                    }
                ),
                400,
            )

        for condition in target_order.transaction_condition:
            if condition.condition_met == True:
                pass
            else:
                condition.condition_met = True
                condition.date_met = datetime.utcnow()
                new_timeline = TransactionTimeline(
                    event_occurrance=f"Condition {condition.id} has been confirmed as met",
                    category="Condition Confirmation",
                    order=target_order,
                )

                db.session.add(new_timeline)

        target_order.conditions_met = True
        target_order.date_updated = datetime.utcnow()
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "conditions succcesfully marked as met",
                }
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.put("verify_conditions_met/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def verify_conditions(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        all_conditions_met = all(
            condition.condition_met == True
            for condition in target_order.transaction_condition
        )
        if target_order.conditions_met:
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "conditions have been succesfully verified already",
                    }
                ),
                200,
            )

        if all_conditions_met:
            target_order.conditions_met = True
            target_order.date_updated = datetime.utcnow()

            new_timeline = TransactionTimeline(
                event_occurrance=f"All conditions have been met and verified",
                category="Condition Confirmation",
                order=target_order,
            )

            db.session.add(new_timeline)
            db.session.commit()

            return (
                jsonify(
                    {
                        "status": "success ",
                        "message": "successfully verified all conditions, amount ready to be paid out to seller",
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "all conditions havent been met, validate conditions first",
                    }
                ),
                400,
            )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.put("approve_partial_disbursements/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def approve_partial_disbursement(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if target_order.partial_disbursement_approved:
            return (
                jsonify(
                    status="error",
                    message="partial disbursement for order already approved",
                ),
                400,
            )

        if target_order.partial_disbursements:
            target_conditions = TransactionCondition.query.filter_by(
                order=target_order
            ).first()

            if not target_conditions:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "conditions havent been set. Please set conditions",
                        }
                    ),
                    400,
                )

            partial_conditions = [
                con for con in target_conditions if con.partial_disburse_requisite
            ]
            partial_conditions_met = all(
                con.condition_met == True for con in partial_conditions
            )

            if not partial_conditions_met:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "conditions to approve partial disbursement haven't been met",
                        }
                    ),
                    400,
                )

            if not (
                target_order.full_payment_verified
                and not target_order.need_to_balance
                and target_order.seller_confirm_delivery
                and target_order.buyer_confirm_delveiry
                and partial_conditions_met
            ):
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "unable to process approval, please confirm that all requirements are met",
                        }
                    ),
                    400,
                )

            target_order.partial_disbursement_approved = True
            new_timeline = TransactionTimeline(
                event_occurrance=f"Partial Disbursements for order {ref_no} ready for initiation",
                category="Disbursement Approval",
                order=target_order,
            )

            db.session.add(new_timeline)
            db.session.commit()

            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "partial disbursement successfully approved. Proceed to initiate payout",
                    }
                ),
                200,
            )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.put("initiate_partial_disbursements/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def initiate_partial_disbursement(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()
        nec_details = current_user.business_details

        if target_order.partial_disbursement_initiated:
            return (
                jsonify(
                    {"status": "error", "message": "order payout already initiated"}
                ),
                400,
            )

        if not target_order.partial_disbursement_approved:
            return (
                jsonify(
                    {"status": "error", "message": "disbursement not yet approved"}
                ),
                400,
            )

        target_order_details = OrderDetails.query.filter_by(order=target_order).first()

        amount = target_order_details.amount_to_partially_disburse
        amount = amount * 100
        pk_reference = f"pk_trans_partial_{uuid.uuid1()}"
        reason = f"Payout to {nec_details.name} for partial payment of order {ref_no}"

        p_client = PaystackClient()

        payload = {
            "source": "balance",
            "reason": reason,
            "curreny": "NGN",
            "recipient": nec_details.receipient_code,
            "amount": amount,
            "reference": pk_reference,
        }

        response, stat_code = p_client.initiate_payout(payload=payload)

        if stat_code == 401:
            # USING KORAPAY TO IMMEDIATELY SEND OUT MONEY IF PAYSTACK DOESNT WORK
            k_client = KoraClient()
            k_ref = f"k_trans_partial_{uuid.uuid1()}"
            k_payload = {
                "reference": k_ref,
                "destination": {
                    "type": "bank_account",
                    "amount": target_order_details.amount_to_partially_disburse,
                    "currency": "NGN",
                    "narration": reason,
                    "bank_account": {
                        "bank": nec_details.bank_account_code,
                        "account": nec_details.bank_account_number,
                    },
                    "customer": {
                        "name": nec_details.bank_account_name,
                        "email": nec_details.email_address,
                    },
                },
            }

            k_response, k_stat_code = k_client.single_payout(k_payload)

            if k_response["status"] and k_stat_code == 200:

                r_client.set(k_ref, ref_no)
                new_timeline = TransactionTimeline(
                    event_occurrance=f"Partial Disbursements have been successfully initiated with ref_no {k_ref}",
                    category="Disbursement Initiation",
                    order=target_order,
                )
                db.session.add(new_timeline)
                target_order.partial_disbursement_initiated = True
                target_order.partial_disbursement_processing = True
                db.session.commit()

                return (
                    jsonify(
                        {
                            "status": "success",
                            "message": "disbursement has been initiated successfully with Korapay, hold for verification",
                        }
                    ),
                    200,
                )

            else:
                print(k_response, k_stat_code)
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "unable to initiate funds disbursement with Korapay",
                        }
                    ),
                    200,
                )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.post("verify_kora_transaction_callback")
def verify_kora_transaction_callback():
    response = {}
    try:
        current_app.lock.acquire()
        response["status"] = "Lock acquired. Processing task..."
        validated_request = signature_validation(request=request, service="kora")
        if validated_request:
            print("successfully validated signature")
            data = request.get_json()
            if data["event"] == "transfer.success":
                trans_data = data.get("data")
                trans_ref = trans_data["reference"]
                order_refno = r_client.get(trans_ref)
                target_order = Order.query.filter_by(reference_no=order_refno).first()
                merchant = Merchant.query.filter_by(id=target_order.merchant_id).first()

                if trans_ref.startswith("k_trans_partial"):
                    if target_order.partial_disbursement_dispatched:
                        response["result"] = "Task completed successfully."
                        return (
                            jsonify(
                                {
                                    "status": "success",
                                    "message": "successfully verified already",
                                }
                            ),
                            200,
                        )

                    target_order.order_details.amount_partially_disbursed += trans_data[
                        "amount"
                    ]
                    target_order.order_details.amount_remaining_to_be_disbursed -= (
                        trans_data["amount"]
                    )
                    target_order.order_details.total_amount_disbursed = trans_data[
                        "amount"
                    ]
                    target_order.order_details.current_holdings_amount -= trans_data[
                        "amount"
                    ]
                    target_order.partial_disbursement_processing = False
                    target_order.partial_disbursement_dispatched = True

                    new_transaction = TransactionHistory(
                        amount=trans_data["amount"],
                        status="Success",
                        trans_reference=trans_ref,
                        sender="TrustLock Holdings",
                        receiver=merchant.busines_details.name,
                        description=f"Partial disbursement of funds from TrustLock to {merchant.busines_details.name} with referernce {trans_ref}",
                        remark=f"Korapay Limited payout to TrustLock merchant {merchant.busines_details.name}",
                        order=target_order,
                    )

                    new_timeline = TransactionTimeline(
                        event_occurrance=f"Partial disbursement of {trans_data['amount']} to {merchant.busines_details.name} successfully verified.",
                        category="Disbursement Verification",
                        order=target_order,
                    )

                    db.session.add_all([new_transaction, new_timeline])
                    db.session.commit()

                    response["result"] = "Task completed successfully."
                    return (
                        jsonify(
                            {
                                "status": "success",
                                "message": "successfully verified partial payout",
                            }
                        ),
                        200,
                    )

                if trans_ref.startswith("k_trans_full"):
                    print("initiation of full fund begun")
                    print(data)
                    if target_order.seller_disbursement_dispatched:
                        response["result"] = "Task completed successfully."
                        return (
                            jsonify(
                                {
                                    "status": "success",
                                    "message": "successfully verified already",
                                }
                            ),
                            200,
                        )

                    if (
                        target_order.seller_disbursement_approved
                        and target_order.seller_disbursement_processing
                    ):
                        print("successfully asserted prerequisites")
                        target_order.order_details.amount_remaining_to_be_disbursed -= (
                            trans_data["amount"]
                        )
                        target_order.order_details.total_amount_disbursed += trans_data[
                            "amount"
                        ]
                        target_order.order_details.current_holdings_amount -= (
                            trans_data["amount"]
                        )
                        target_order.seller_disbursement_processing = False
                        target_order.seller_disbursement_dispatched = True
                        target_order.order_closed = True
                        target_order.order_details.date_updated = datetime.utcnow()
                        target_order.date_updated = datetime.utcnow()
                        target_order.date_closed = datetime.utcnow()

                        new_transaction = TransactionHistory(
                            amount=trans_data["amount"],
                            status="Success",
                            trans_reference=trans_ref,
                            sender="TrustLock Holdings",
                            receiver=merchant.business_details.name,
                            description=f"Full disbursement of funds from TrustLock to {merchant.business_details.name} with referernce {trans_ref}",
                            remark=f"Korapay Limited payout to TrustLock merchant {merchant.business_details.name}",
                            order=target_order,
                        )

                        new_timeline = TransactionTimeline(
                            event_occurrance=f"Full disbursement of {trans_data['amount']} to {merchant.business_details.name} successfully verified.",
                            category="Disbursement Verification",
                            order=target_order,
                        )

                        new_timeline1 = TransactionTimeline(
                            event_occurrance=f"Order {order_refno} has been successfully closed",
                            category="Order Close",
                            order=target_order,
                        )

                        db.session.add_all([new_transaction, new_timeline])
                        db.session.add(new_timeline1)
                        db.session.commit()

                        response["result"] = "Task completed successfully."
                        print("added to db successfully")
                        return (
                            jsonify(
                                {
                                    "status": "success",
                                    "message": "successfully verified partial payout",
                                }
                            ),
                            200,
                        )
                    else:
                        print("order not approved")
                        print(target_order.seller_disbursement_approved)
                        print(target_order.seller_disbursement_processing)
                        response["result"] = "Task completed successfully."
                        return (
                            jsonify(
                                {"status": "failed", "message": "order not approved"}
                            ),
                            400,
                        )

                if trans_ref.startswith("k_refund"):
                    if target_order.refund_dispatched:
                        return (
                            jsonify(
                                status="success",
                                message="transaction has already been verified",
                            ),
                            200,
                        )
                    customer_name = f"{target_order.customer.first_name} {target_order.customer.last_name}"
                    target_order.full_amount_refunded = (
                        True
                        if not target_order.partial_disbursement_dispatched
                        else False
                    )
                    target_order.order_details.amount_refunded = trans_data["amount"]
                    target_order.order_details.current_holdings_amount -= trans_data[
                        "amount"
                    ]
                    target_order.order_details.date_updated = datetime.utcnow()
                    target_order.refund_processing = False
                    target_order.refund_dispatched = True
                    target_order.date_updated = datetime.utcnow()
                    target_order.order_closed = True
                    target_order.date_closed = datetime.utcnow()

                    new_transaction = TransactionHistory(
                        amount=trans_data["amount"],
                        status="Success",
                        trans_reference=trans_ref,
                        sender="TrustLock Holdings",
                        receiver=customer_name,
                        description=f"Refund of funds to {customer_name} due to return of order {order_refno}",
                        remark=f"Korapay Limited refund to TrustLock customer {customer_name}",
                        order=target_order,
                    )

                    new_timeline = TransactionTimeline(
                        event_occurrance=f"Refund of {trans_data['amount']} to {customer_name} successfully verified.",
                        category="Refund",
                        order=target_order,
                    )

                    new_timeline1 = TransactionTimeline(
                        event_occurrance=f"Order {order_refno} has been successfully closed",
                        category="Order Close",
                        order=target_order,
                    )

                    db.session.add_all([new_transaction, new_timeline, new_timeline1])
                    db.session.commit()
                    # SEND EMAIL TO INFORM PARTIES THAT REFUND WAS SUCCESSFUL AND ORDER HAS BEEN CLOSED

                    response["result"] = "Task completed successfully."
                    return (
                        jsonify(
                            {
                                "status": "success",
                                "message": "successfully verified refund",
                            }
                        ),
                        200,
                    )

            elif data["event"] == "transfer.failed":
                # ADD LOGIC TO PROCESS TRANSACTION WHEN THE ATTEMPT FAILED
                return (
                    jsonify(
                        {
                            "status": "success",
                            "message": "transfer status received successfully",
                        }
                    ),
                    200,
                )
            else:
                # ADD LOGIC TO PROCESS TRANSACTION WHEN THE ATTEMPT FAILED
                return (
                    jsonify(
                        {
                            "status": "success",
                            "message": "transfer status received successfully",
                        }
                    ),
                    200,
                )

        else:
            response["result"] = "Task completed successfully."
            return (
                jsonify({"status": "error", "message": "enable to initiate handshake"}),
                400,
            )

    except Exception as e:
        db.session.rollback()
        print(e)
        response["error"] = str(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500

    finally:
        current_app.lock.release()
        response["status"] = "Lock released."
        print(response)


@transaction.post("verify_paystack_transaction_callback")
def verify_paystack_transaction_callback():
    response = {}
    try:
        current_app.lock.acquire()
        response["status"] = "Lock acquired. Processing task..."
        validated_request = signature_validation(request=request, service="paystack")
        if validated_request:
            data = request.get_json()
            if data["event"] == "transfer.success":
                trans_data = data.get("data")
                amount = trans_data["amount"] / 100
                trans_ref = trans_data["reference"]
                info_dict = r_client.get(trans_ref).decode("utf-8")
                info_dict = json.loads(info_dict)
                order_refno = info_dict["order_ref"]
                target_order = Order.query.filter_by(reference_no=order_refno).first()
                merchant = Merchant.query.filter_by(id=target_order.merchant_id).first()

                if trans_ref.startswith("pk_trans_full"):
                    if target_order.seller_disbursement_dispatched:
                        response["result"] = "Task completed successfully."
                        return (
                            jsonify(
                                {
                                    "status": "success",
                                    "message": "successfully verified already",
                                }
                            ),
                            200,
                        )

                    if (
                        target_order.seller_disbursement_approved
                        and target_order.seller_disbursement_processing
                    ):
                        target_order.order_details.amount_remaining_to_be_disbursed -= (
                            amount
                        )
                        target_order.order_details.total_amount_disbursed += amount
                        target_order.order_details.current_holdings_amount -= amount
                        target_order.seller_disbursement_processing = False
                        target_order.seller_disbursement_dispatched = True
                        target_order.order_closed = True
                        target_order.order_details.date_updated = datetime.utcnow
                        target_order.date_updated = datetime.utcnow
                        target_order.date_closed = datetime.utcnow

                        new_transaction = TransactionHistory(
                            amount=amount,
                            status="Success",
                            trans_reference=trans_ref,
                            sender="TrustLock Holdings",
                            receiver=merchant.busines_details.name,
                            description=f"Full disbursement of funds from TrustLock to {merchant.busines_details.name} with referernce {trans_ref}",
                            remark=f"Paystack Limited payout to TrustLock merchant {merchant.busines_details.name}",
                            order=target_order,
                        )

                        new_timeline = TransactionTimeline(
                            event_occurrance=f"Full disbursement of {amount} to {merchant.busines_details.name} successfully verified.",
                            category="Disbursement Verification",
                            order=target_order,
                        )

                        new_timeline1 = TransactionTimeline(
                            event_occurrance=f"Order {order_refno} has been successfully closed",
                            category="Order Close",
                            order=target_order,
                        )

                        db.session.add_all(new_transaction, new_timeline)
                        db.session.add(new_timeline1)
                        db.session.commit()

                        response["result"] = "Task completed successfully."
                        return (
                            jsonify(
                                {
                                    "status": "success",
                                    "message": "successfully verified partial payout",
                                }
                            ),
                            200,
                        )
                    else:
                        response["result"] = "Task completed successfully."
                        return (
                            jsonify(
                                {"status": "failed", "message": "order not approved"}
                            ),
                            400,
                        )

                if trans_ref.startswith("pk_trans_partial"):
                    if target_order.partial_disbursement_dispatched:
                        response["result"] = "Task completed successfully."
                        return (
                            jsonify(
                                {
                                    "status": "success",
                                    "message": "successfully verified already",
                                }
                            ),
                            200,
                        )

                    target_order.order_details.amount_partially_disbursed += amount
                    target_order.order_details.amount_remaining_to_be_disbursed -= (
                        amount
                    )
                    target_order.order_details.total_amount_disbursed = amount
                    target_order.order_details.current_holdings_amount -= amount
                    target_order.partial_disbursement_processing = False
                    target_order.partial_disbursement_dispatched = True

                    new_transaction = TransactionHistory(
                        amount=amount,
                        status="Success",
                        trans_reference=trans_ref,
                        sender="TrustLock Holdings",
                        receiver=merchant.busines_details.name,
                        description=f"Partial disbursement of funds from TrustLock to {merchant.busines_details.name} with referernce {trans_ref}",
                        remark=f"Paystack Limited payout to TrustLock merchant {merchant.busines_details.name}",
                        order=target_order,
                    )

                    new_timeline = TransactionTimeline(
                        event_occurrance=f"Partial disbursement of {amount} to {merchant.busines_details.name} successfully verified.",
                        category="Disbursement Verification",
                        order=target_order,
                    )

                    db.session.add_all(new_transaction, new_timeline)
                    db.session.commit()

                    response["result"] = "Task completed successfully."
                    return (
                        jsonify(
                            {
                                "status": "success",
                                "message": "successfully verified partial payout",
                            }
                        ),
                        200,
                    )

            if data["event"] == "transfer.failed":
                # ADD LOGIC TO PROCESS TRANSACTION WHEN THE ATTEMPT FAILED
                return (
                    jsonify(
                        {
                            "status": "success",
                            "message": "transfer status received successfully",
                        }
                    ),
                    200,
                )

            if data["event"] == "transfer.reveresed":
                # ADD LOGIC TO PROCESS TRANSACTION WHEN THE ATTEMPT WAS REVERESED
                return (
                    jsonify(
                        {
                            "status": "success",
                            "message": "transfer status received successfully",
                        }
                    ),
                    200,
                )

            if data["event"] == "charge.success":
                print(json.dumps(data["data"], indent=4))
                return jsonify({"status": True, "message": "callback successful"}), 200
        else:
            response["result"] = "Task completed successfully."
            print("unable to verify handshake")
            return (
                jsonify({"status": "error", "message": "enable to initiate handshake"}),
                400,
            )

    except Exception as e:
        db.session.rollback()
        print(e)
        response["error"] = str(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500

    finally:
        current_app.lock.release()
        response["status"] = "Lock released."
        print(response)


@transaction.put("approve_seller_disbursement/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def approve_seller_disbursement(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if target_order.seller_disbursement_approved:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "order disbursement already aprroved, proceed to initiate payout",
                    }
                ),
                400,
            )

        if not (
            target_order.full_payment_verified
            and not target_order.need_to_balance
            and target_order.seller_confirm_delivery
            and target_order.buyer_confirm_delivery
            and target_order.conditions_met
            and not target_order.dispute_ongoing
            and not target_order.product_to_be_returned
            and not target_order.refund_initiated
            and not target_order.special_attention
        ):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "unable to process approval, please confirm that all requirements are met",
                    }
                ),
                400,
            )

        print("all conditions passed")
        target_order.seller_disbursement_approved = True

        new_timeline = TransactionTimeline(
            event_occurrance=f"Full Disbursements of funds for order {ref_no} ready for initiation",
            category="Disbursement Approval",
            order=target_order,
        )

        db.session.add(new_timeline)
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "full disbursement successfully approved. Proceed to request dispacth",
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.put("initiate_seller_payout/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def initialize_seller_payout(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()
        nec_details = BusinessDetails.query.filter_by(
            merchant_id=target_order.merchant_id
        ).one()

        if target_order.seller_disbursement_initiated:
            return (
                jsonify(
                    {"status": "error", "message": "order payout already initiated"}
                ),
                400,
            )

        if not target_order.seller_disbursement_approved:
            return (
                jsonify(
                    {"status": "error", "message": "disbursement not yet approved"}
                ),
                400,
            )

        target_order_details = target_order.order_details

        amount = target_order_details.amount_remaining_to_be_disbursed
        amount = amount * 100
        pk_ref = f"pk_trans_full_{uuid.uuid1()}"
        reason = f"Payout to {nec_details.name} for full payment of order {ref_no}"

        p_client = PaystackClient()

        payload = {
            "source": "balance",
            "reason": reason,
            "curreny": "NGN",
            "recipient": nec_details.receipient_code,
            "amount": amount,
            "reference": pk_ref,
        }

        response, stat_code = p_client.initiate_payout(payload=payload)
        if stat_code == 400:
            # USING KORAPAY TO IMMEDIATELY SEND OUT MONEY IF PAYSTACK DOESNT WORK
            k_client = KoraClient()
            k_ref = f"k_trans_full_{uuid.uuid1()}"
            k_payload = {
                "reference": k_ref,
                "destination": {
                    "type": "bank_account",
                    "amount": target_order_details.amount_remaining_to_be_disbursed,
                    "currency": "NGN",
                    "narration": reason,
                    "bank_account": {
                        "bank": nec_details.bank_account_code,
                        "account": nec_details.bank_account_number,
                    },
                    "customer": {
                        "name": nec_details.bank_account_name,
                        "email": nec_details.email_address,
                    },
                },
            }

            k_response, k_stat_code = k_client.single_payout(k_payload)

            if k_response["status"] and k_stat_code == 200:

                r_client.set(k_ref, ref_no)
                target_order.seller_disbursement_initiated = True
                target_order.seller_disbursement_processing = True
                target_order.date_updated = datetime.utcnow()
                new_timeline = TransactionTimeline(
                    event_occurrance=f"Full Disbursements have been successfully initiated with ref_no {k_ref}",
                    category="Disbursement Initiation",
                    order=target_order,
                )
                db.session.add(new_timeline)
                db.session.commit()

                return (
                    jsonify(
                        {
                            "status": "success",
                            "message": "disbursement has been initiated successfully with Korapay, hold for verification",
                        }
                    ),
                    200,
                )

            else:
                print(k_response, k_stat_code)
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "unable to initiate funds disbursement with Korapay",
                        }
                    ),
                    400,
                )

        if stat_code == 200 and response["status"]:
            info_dict = {
                "order_ref": ref_no,
                "transfer_code": response["data"]["transfer_code"],
            }
            r_client.set(pk_ref, json.dumps(info_dict))
            target_order.seller_disbursement_initiated = True
            target_order.seller_disbursement_processing = True
            target_order.date_updated = datetime.utcnow()
            new_timeline = TransactionTimeline(
                event_occurrance=f"Full Disbursements have been successfully initiated with ref_no {pk_ref}",
                category="Disbursement Initiation",
                order=target_order,
            )
            db.session.add(new_timeline)
            db.session.commit()

            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "disbursement has been initiated successfully with Paystack, hold for verification",
                    }
                ),
                200,
            )

        else:
            print(response, stat_code)
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "unable to initiate funds disbursement with Paystack",
                    }
                ),
                400,
            )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.get("get_transaction_history/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def get_transaction_history(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        transaction_history = TransactionHistory.query.filter_by(
            order=target_order
        ).all()

        schema = TransactionHistorySchema(many=True)

        trans_schemas = schema.dump(transaction_history)

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "retrieved order transacctions",
                    "data": trans_schemas,
                }
            ),
            200,
        )

    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.get("get_transaction_timeline/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def get_transaction_timeline(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        transaction_timeline = TransactionTimeline.query.filter_by(
            order=target_order
        ).all()

        schema = TransactionTimelineSchema(many=True)

        trans_schemas = schema.dump(transaction_timeline)

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "retrieved order timeline",
                    "data": trans_schemas,
                }
            ),
            200,
        )

    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@transaction.post("rate_order/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def rate_order(ref_no):
    try:
        data = request.get_json()

        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if not target_order.order_closed:
            return (
                jsonify(
                    status="error",
                    message="please ensure order is concluded before leaving a rating",
                ),
                400,
            )

        if target_order.order_rated:
            return jsonify(status="error", message="order has already been rated"), 400

        rating = int(data["order_rating"])

        if rating < 0 or rating > 5:
            return (
                jsonify(
                    status="error",
                    message="please only give a rating between 0 and 5. 0 being worst and 5 being the best",
                ),
                400,
            )

        target_order.order_details.order_rating = rating
        target_order.order_details = data["order_feedback"]
        target_order.order_rated = True

        new_timeline = TransactionTimeline(
            event_occurrance=f"Order {ref_no} was given a rating of {rating}",
            category="Order Rating",
            order=target_order,
        )

        db.session.add(new_timeline)
        db.session.commit()

        # send mail to thank customer for feedback
        return jsonify(
            status="success",
            message="successfully rated order, thank you for using our services. Hope to see you soon!",
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500
