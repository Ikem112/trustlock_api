from datetime import timedelta, datetime
import json
import os
from dotenv import load_dotenv
import uuid
from nanoid import generate
import bcrypt
from flask import request, jsonify

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
from project.helpers import calculate_fees
from . import transaction
from project.api_services.paystack_api import PaystackClient
from ..merchants.models import (
    Merchant,
    MerchantSchema,
    MerchantDetails,
    MerchantDetailsSchema,
    OrderSchema,
    Customer,
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

from ..decorators import api_secret_key_required

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

        new_order = Order(
            reference_no=ref_no,
            product_name=data.get("product_name"),
            product_description=data.get("product_description"),
            product_amount=data.get("product_amount"),
            escrow_percent=escrow_percent,
            escrow_fee=escrow_fee,
            process_fee=process_fee,
            amount_to_pay=amount_to_pay,
            amount_to_balance=amount_to_pay,
            total_amount_received=0.00,
            partial_dispersals=data.get("partial_dispersals"),
            partial_amount_to_be_dispersed=data.get("partial_amount_to_be_dispersed"),
            inspection_time=data.get("inspection_time"),
            order_initiated=True,
            merchant=current_merchant,
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
            order=new_order,
        )

        order_schema = OrderSchema()
        order = order_schema.dump(new_order)

        db.session.add(new_order)
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

        order = Order.query.filter_by(reference_no=ref_no).first()
        if not order:
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

        for new_condition in conditions:

            new_condition = TransactionCondition(
                condition_title=new_condition.get("condition_title"),
                condition_description=new_condition.get("condition_description"),
                party_to_meet_condition=new_condition.get("party_to_meet_condition"),
                order=order,
            )

            db.session.add(new_condition)

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


@transaction.post("initiate_product_payment/<order_ref_no>")
@jwt_required()
@api_secret_key_required
def initiate_product_payment(order_ref_no):
    try:

        current_merchant = Merchant.query.filter_by(id=current_user.id).first()
        target_order = Order.query.filter_by(
            merchant_id=current_merchant.id, reference_no=order_ref_no
        ).first()

        if not target_order:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "order not found. please check reference number",
                    }
                ),
                400,
            )

        if target_order.amount_verified == True:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "payment for order already completed",
                    }
                ),
                400,
            )
        customer_email = target_order.customer.email_address
        amount_to_pay = target_order.amount_to_pay
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
        ref_no = response["data"]["reference"]
        timeline_update = TransactionTimeline(
            event_occurrance=f"Transaction for payment of escrow service for order {order_ref_no} succesfully initialized with ref_no {ref_no}",
            order=target_order,
        )

        db.session.add(timeline_update)
        db.session.commit()

        r_client.set(f"ref_no_{ref_no}", order_ref_no)
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

    # modification of code needed to accomodate sending of balance moeny
    try:

        ref_no = request.args.get("reference")

        paystack_client = PaystackClient()

        response, status_code = paystack_client.paystack_verify_transaction(ref_no)

        if not response["status"]:
            return jsonify({"status": "error", "message": response["message"]}), 400

        order_ref_no = r_client.get(f"ref_no_{ref_no}").decode("utf-8")

        target_order = Order.query.filter_by(reference_no=order_ref_no).first()

        amount_to_pay = target_order.amount_to_pay

        naira_amount = response["data"]["amount"] / 100

        if naira_amount < amount_to_pay:
            balance_payment = amount_to_pay - naira_amount
            new_trans_entry = TransactionHistory(
                amount=naira_amount,
                trans_reference=f'ps_res_{response["data"]["reference"]}',
                sender="Buyer",
                receiver="TrustLock",
                trans_action="TrustLock Credit",
                description=f"Partial payment of product of order {order_ref_no}, awaiting balance payment of {balance_payment}",
                order=target_order,
            )

            new_timeline = TransactionTimeline(
                event_occurrance=f"Partial payment of {naira_amount} paid into TrustLock Holdings.",
                order=target_order,
            )

            db.session.add(new_trans_entry)
            db.session.add(new_timeline)
            db.session.commit()

            target_order.total_amount_received = naira_amount
            target_order.amount_to_balance = balance_payment
            target_order.date_updated = datetime.utcnow

            db.session.commit()

            from project.api_services.sendgrid_api import Mailer

            mailer = Mailer()

            formatted_price = "{:,.2f}".format(naira_amount)
            payload = {
                "customer_name": current_user.orders.customer.first_name,
                "amount_paid": f"N {formatted_price}.",
                "product_name": current_user.order.product_name,
                "transaction_id": response["data"]["reference"],
                "payment_date": datetime.utcnow,
            }

            data, status = mailer.send_payment_confirmation_mail(
                current_user.orders.customer.email_address, payload
            )
            print(data, status)
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "amount verified. However, full amount hasnt been paid",
                        "data": {"remaining_balance": balance_payment},
                    }
                ),
                200,
            )

        if naira_amount >= amount_to_pay:
            new_trans_entry = TransactionHistory(
                amount=naira_amount,
                trans_reference=response["data"]["reference"],
                sender="Buyer",
                receiver="TrustLock",
                trans_action="TrustLock Credit",
                description=f"Full payment of product of order {order_ref_no}",
                order=target_order,
            )

            new_timeline = TransactionTimeline(
                event_occurrance=f"Full payment of {naira_amount} paid into TrustLock Holdings. Order has been commenced",
                order=target_order,
            )

            db.session.add(new_trans_entry)
            db.session.add(new_timeline)
            db.session.commit()

            target_order.total_amount_received = naira_amount
            target_order.amount_verified = True
            target_order.order_commenced = True
            target_order.amount_to_balance = 0.00
            target_order.date_updated = datetime.utcnow
            db.session.commit()

            from project.api_services.sendgrid_api import Mailer

            mailer = Mailer()

            formatted_price = "{:,.2f}".format(naira_amount)
            payload = {
                "customer_name": (target_order.customer.first_name).capitalize(),
                "amount_paid": f"N {formatted_price}.",
                "product_name": target_order.product_name,
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


@transaction.put("confirm_product_delivery/<order_ref>")
@jwt_required()
@api_secret_key_required
def confirm_product_delivery(order_ref):

    try:
        data = request.get_json()

        is_delivered = data.get("is_delivered")

        target_order = Order.query.filter_by(reference_no=order_ref).first()

        if not target_order:
            return (
                jsonify(
                    {"status": "error", "message": f"order {order_ref} doesn't exist"}
                ),
                400,
            )

        if target_order.product_delivered:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"delivery of order {order_ref} has already been confirmed",
                    }
                ),
                400,
            )

        target_order.product_delivered = True
        target_order.date_product_delivered = datetime.utcnow
        target_order.date_updated = datetime.utcnow

        new_timeline = TransactionTimeline(
            event_occurrance=f"Order {order_ref} has just been confirmed as delivered, inspection time initiated",
            order=target_order,
        )

        db.session.add(new_timeline)
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "product status has been successfully updated",
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
def retrieve_conditions(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()
        if not target_order:
            return jsonify({"status": "failed", "message": "order not found"}), 400

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
def validate_conditions(ref_no, con_id):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()
        if not target_order:
            return jsonify({"status": "error", "message": "order doesnt exist"}), 400

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
                order=target_order,
            )
            db.session.add(new_timeline)
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
def validate_all_conditions(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()
        if not target_order:
            return jsonify({"status": "error", "message": "order doesnt exist"}), 400

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
            condition.condition_met = True
            condition.date_met = datetime.utcnow()
            new_timeline = TransactionTimeline(
                event_occurrance=f"Condition {condition.id} has been confirmed as met",
                order=target_order,
            )

            db.session.add(new_timeline)
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
def validate_all_conditions(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()
        if not target_order:
            return jsonify({"status": "error", "message": "order doesnt exist"}), 400

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
            target_order.date_updated = datetime.utcnow

            new_timeline = TransactionTimeline(
                event_occurrance=f"All conditions have been met and verified",
                order=target_order,
            )

            db.session.add(new_timeline)
            db.session.commit()

            return (
                jsonify(
                    {
                        "status": "error",
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


@transaction.post("initialize_seller_payout/<ref_no>")
@jwt_required()
@api_secret_key_required
def initialize_seller_payout(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()
        if not target_order:
            return jsonify({"status": "error", "message": "order doesnt exist"}), 400

        if not target_order.amount_verified:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "you're currently unable to proceed with disbursement",
                    }
                ),
                400,
            )

        if (
            target_order.instant_pay
            and target_order.conditions_met
            and not target_order.order_closed
        ):
            disbursement_amount = (
                target_order.partial_amount_to_be_dispersed
                if target_order.partial_dispersals
                else target_order.product_amount
            )

            # initialize disbursement of funds to seller (check to confirm account details are valid and start processing payment)
            target_order.dispursement_processing = True

            new_timeline = TransactionTimeline(
                event_occurrance=f"disbursement of funds for order {ref_no} has been successfully initialized and is waiting for verification",
                order=target_order,
            )
            db.session.add(new_timeline)
            db.session.commit()

            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "disbursement to seller has been successfully initiated",
                    }
                ),
                200,
            )
        elif not target_order.instant_pay:
            pass
    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500
