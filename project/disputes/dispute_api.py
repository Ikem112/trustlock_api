from datetime import timedelta, datetime
import json
import os
from dotenv import load_dotenv
import uuid
from nanoid import generate
import bcrypt
from flask import request, jsonify, current_app

from flask_jwt_extended import (
    get_jwt_identity,
    jwt_required,
    current_user,
    get_jwt,
)
from . import dispute
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
    ProductReturn,
)
from ..decorators import api_secret_key_required, order_exists, to_be_returned
from ..api_services.paystack_api import PaystackClient
from ..api_services.kora_api import KoraClient
from project import db, jwt, bcrypt, r_client

load_dotenv()


@dispute.post("raise_issue/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def raise_issue(ref_no):
    try:

        data = request.get_json()
        con_id = data.get("condition_disputed")

        target_order = Order.query.filter_by(reference_no=ref_no).first()
        target_condition = TransactionCondition.query.filter_by(id=con_id).first()

        if target_order.conditions_met:
            return (
                jsonify(
                    status="error",
                    message="all conditions have been met already",
                ),
                400,
            )
        if target_condition:
            if target_condition.dispute_raised:
                return (
                    jsonify(
                        status="error",
                        message="dispute already rasied on chosen condition",
                    ),
                    400,
                )
            target_condition.dispute_raised = True

            new_timeline_con = TransactionTimeline(
                event_occurrance=f"Dispute raised on condition {con_id}",
                category="Dispute",
                order=target_order,
            )
            db.session.add(new_timeline_con)

        if target_order.dispute_resloved:
            return (
                jsonify(
                    status="error", message="disputes arleady successfully resolved"
                ),
                400,
            )

        new_dispute = Dispute(
            dispute_title=data.get("dispute_title"),
            dispute_reason=data.get("dispute_reason"),
            condition_disputed=con_id,
            order=target_order,
        )

        new_timeline = TransactionTimeline(
            event_occurrance=f"Dispute raised on product {ref_no}"
            if not target_order.dispute_raised
            else f"Dispute issue added on product {ref_no}",
            category="Dispute",
            order=target_order,
        )

        target_order.date_updated = datetime.utcnow()
        target_order.dispute_raised = True
        target_order.dispute_raised_date = (
            datetime.utcnow()
            if not target_order.dispute_raised
            else target_order.dispute_raised_date
        )
        target_order.dispute_time_triggered = True
        target_order.dispute_ongoing = True

        db.session.add_all([new_dispute, new_timeline])
        db.session.commit()

        # notify merchant that an issue has been raised concerning the product
        # ensure to include logic to pause the inspection time as a dispute will verify inspection

        return jsonify(status="success", message="Successfully raised issue"), 200

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@dispute.get("get_dispute/<ref_no>/<id>")
@jwt_required()
@api_secret_key_required
@order_exists
def get_dispute(ref_no, id):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        target_dispute = Dispute.query.filter_by(order=target_order, id=id).first()

        if not target_dispute:
            return (
                jsonify(
                    status="error",
                    message="dispute doesnt exist",
                ),
                400,
            )

        d_schema = DisputeSchema()
        dispute = d_schema.dump(target_dispute)

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "dispute retrieved successfully",
                    "data": dispute,
                }
            ),
            200,
        )
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@dispute.get("get_disputes/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def get_disputes(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        target_disputes = Dispute.query.filter_by(order=target_order).all()

        if not target_disputes or len(target_disputes) == 0:
            return (
                jsonify(
                    status="error",
                    message="there are no current disputes",
                ),
                400,
            )

        d_schema = DisputeSchema(many=True)
        disputes = d_schema.dump(target_disputes)

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "disputes retrieved successfully",
                    "data": disputes,
                }
            ),
            200,
        )
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@dispute.put("resolve_dispute/<ref_no>/<id>")
@jwt_required()
@api_secret_key_required
@order_exists
def resolve_dispute(ref_no, id):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if target_order.dispute_resloved:
            return (
                jsonify(
                    status="error", message="disputes arleady successfully resolved"
                ),
                400,
            )

        target_dispute = Dispute.query.filter_by(id=id, order=target_order).first()

        if target_dispute.dispute_resolved:
            return (
                jsonify(
                    status="error",
                    message="dispute has arleady been marked as resolved",
                ),
                400,
            )

        if target_dispute.condition_disputed is not None:
            target_con = TransactionCondition.query.filter_by(
                id=target_dispute.condition_disputed
            ).first()
            if target_con.dispute_settled:
                return (
                    jsonify(
                        status="error",
                        message="dispute on condition has already been met",
                    ),
                    400,
                )
            target_con.dispute_settled = True
            new_timeline_con = TransactionTimeline(
                event_occurrance=f"Dispute on condition {target_con.id} has been successfuly settled for dispute {target_dispute.id}",
                category="Dispute",
                order=target_order,
            )

            db.session.add(new_timeline_con)
            db.session.commit()

        target_dispute.dispute_resolved = True
        target_dispute.dispute_resolved_date = datetime.utcnow()

        new_timeline = TransactionTimeline(
            event_occurrance=f"Dispute '{target_dispute.dispute_title}' on product {ref_no} successfully resolved",
            category="Dispute",
            order=target_order,
        )

        all_verified = all(
            dispute.dispute_resolved == True for dispute in target_order.dispute
        )

        if all_verified:
            target_order.dispute_resloved = True
            target_order.date_updated = datetime.utcnow()
            new_timeline1 = TransactionTimeline(
                event_occurrance=f"All disputes for order {ref_no} have successfully been resolved... awaiting dispute conclusion",
                category="Dispute",
                order=target_order,
            )
            db.session.add(new_timeline1)
            db.session.commit()

        db.session.add(new_timeline)
        db.session.commit()
        return (
            jsonify(status="success", message=f"successfully resolved disute {id}"),
            200,
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@dispute.put("resolve_all_disputes/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def resolve_all_disputes(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if target_order.dispute_resloved:
            return (
                jsonify(
                    status="error", message="disputes arleady successfully resolved"
                ),
                400,
            )

        for dispute in target_order.dispute:
            if dispute.dispute_resolved == False:
                target_con = (
                    TransactionCondition.query.filter_by(
                        id=dispute.condition_disputed
                    ).first()
                    if dispute.condition_disputed is not None
                    else None
                )
                if target_con is not None:
                    if target_con.dispute_settled:
                        pass
                    else:
                        target_con.dispute_settled = True
                        new_timeline_con = TransactionTimeline(
                            event_occurrance=f"Dispute on condition {target_con.id} has been successfuly settled for dispute {dispute.id}",
                            category="Dispute",
                            order=target_order,
                        )
                        db.session.add(new_timeline_con)

                dispute.dispute_resolved = True
                dispute.dispute_resolved_date = datetime.utcnow()
                new_timeline1 = TransactionTimeline(
                    event_occurrance=f"Dispute '{dispute.dispute_title}' on product {ref_no} successfully resolved",
                    category="Dispute",
                    order=target_order,
                )

                db.session.add(new_timeline1)

        target_order.dispute_resloved = True
        target_order.date_updated = datetime.utcnow()
        new_timeline = TransactionTimeline(
            event_occurrance=f"All disputes for order {ref_no} have successfully been resolved... awaiting dispute conclusion",
            category="Dispute",
            order=target_order,
        )
        db.session.add(new_timeline)
        db.session.commit()

        return (
            jsonify(status="success", message="successfully resolved all disputes"),
            200,
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@dispute.post("add_dispute_conclusion/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
def add_dispute_conclusion(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if not target_order.dispute_resloved:
            return (
                jsonify(
                    status="error",
                    message="disputes havent been resolved yet, please resolve disputes",
                ),
                400,
            )

        data = request.get_json()
        conclusion = data.get("dispute_conclusion").lower()

        if conclusion == "accepted":

            for condition in target_order.transaction_condition:
                if condition.condition_met == True:
                    pass
                else:
                    condition.condition_met = True
                    condition.date_met = datetime.utcnow()
                    new_timeline_con = TransactionTimeline(
                        event_occurrance=f"Condition {condition.id} has been confirmed as met via resolved dispute",
                        category="Dispute Conclusion",
                        order=target_order,
                    )

                    db.session.add(new_timeline_con)

            new_timeline_accept = TransactionTimeline(
                event_occurrance=f"Dsipute was concluded and product was accepted",
                category="Dispute Conclusion",
                order=target_order,
            )

            db.session.add(new_timeline_accept)
            target_order.conditions_met = True
            target_order.dispute_conclusion = "accepted"
            target_order.date_updated = datetime.utcnow()
            db.session.commit()
            return (
                jsonify(
                    status="success",
                    message="product has been accepted due to resolved resolution. Proceed to approve payout",
                ),
                200,
            )

        if conclusion == "rejected":
            time = data.get("return_time")
            if not time:
                return (
                    jsonify(
                        status="error",
                        message="please ensure to include time for product to be returned in days",
                    ),
                    400,
                )

            new_product_return = ProductReturn(
                time_for_return=int(time),
                amount_to_refund=target_order.order_details.amount_remaining_to_be_disbursed,
                order=target_order,
            )
            target_order.dispute_conclusion = "rejected"
            target_order.product_to_be_returned = True
            target_order.product_return_commenced = True
            target_order.date_updated = datetime.utcnow()

            r_client.set(f"return_{ref_no}", True)
            new_timeline_return = TransactionTimeline(
                event_occurrance=f"Product {ref_no} was rejected and product return has commenced",
                category="Dispute Conclusion",
                order=target_order,
            )

            db.session.add_all([new_product_return, new_timeline_return])
            db.session.commit()
            return (
                jsonify(
                    status="success",
                    message="product has been rejected due to resolved resolution. Proceed to refund customer",
                ),
                200,
            )

        if conclusion == "unresolved":
            new_timeline_unresolved = TransactionTimeline(
                event_occurrance=f"Dispute on order {ref_no} was unresolved and arbitration required",
                category="Dispute Conclusion",
                order=target_order,
            )

            target_order.dispute_conclusion = "unresolved"
            target_order.arbitation_required = True
            target_order.date_updated = datetime.utcnow()
            db.session.add(new_timeline_unresolved)
            db.session.commit()
            return (
                jsonify(
                    status="success",
                    message="dispute has been unresolved, arbitrate body required",
                ),
                200,
            )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@dispute.post("confirm_return_sendout/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
@to_be_returned
def confirm_return_sendout(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()
        if target_order.product_return.product_sent_out:
            return (
                jsonify(status="error", message="product has already been sent out"),
                400,
            )

        data = request.get_json()
        del_info = data.get("delivery_info")

        new_delivery = DeliveryInformation(
            event="Product Return",
            delivery_description=f"Return of order {ref_no} to seller {current_user.business_details.name}",
            delivery_courier=del_info.get("courier", None),
            source_location=del_info.get(
                "source_address", target_order.customer.address
            ),
            destination_location=del_info.get(
                "delivery_address", current_user.merchant_details.residing_address
            ),
            delivery_means=del_info.get("delivery_means", None),
            tracking_number=del_info.get("tracking_number", None),
            special_instructions=del_info.get("special_instructions", None),
            delivery_metadata=del_info.get("delivery_metadata", None),
            order=target_order,
        )

        target_order.product_return.product_sent_out = True
        target_order.product_return.product_in_transit = True
        target_order.product_return.date_product_sent_out = datetime.utcnow()

        new_timeline = TransactionTimeline(
            event_occurrance=f"Product {ref_no} has been sent out for return",
            category="Product Return",
            order=target_order,
        )

        db.session.add_all([new_delivery, new_timeline])
        db.session.commit()

        return (
            jsonify(
                status="success",
                message="Product return has successfully been marked as sent out",
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@dispute.put("buyer_confirm_return/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
@to_be_returned
def buyer_confirm_return(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if target_order.product_return_confirm_buyer:
            return (
                jsonify(
                    status="error",
                    message="delivery has already been confirmed by buyer",
                ),
                400,
            )

        target_order.product_return_confirm_buyer = True
        target_order.product_return.buyer_confirm_delivery = True
        target_order.product_return.date_buyer_confirm_return = datetime.utcnow()
        target_order.date_updated = datetime.utcnow()

        new_timeline = TransactionTimeline(
            event_occurrance=f"Return of product {ref_no} has been successfully marked as delivered by the buyer",
            category="Product Return",
            order=target_order,
        )

        db.session.add(new_timeline)
        db.session.commit()

        return (
            jsonify(
                status="success",
                message="Product return has successfully been marked as delivered by buyer",
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@dispute.put("seller_confirm_return/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
@to_be_returned
def seller_confirm_return(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if target_order.product_return_confirm_seller:
            return (
                jsonify(
                    status="error",
                    message="delivery has already been confirmed by seller",
                ),
                400,
            )

        target_order.product_return_confirm_buyer = True
        target_order.product_return.buyer_confirm_delivery = True
        target_order.product_return.date_buyer_confirm_return = datetime.utcnow()
        target_order.product_return_confirm_seller = True
        target_order.product_return.seller_confirm_delivery = True
        target_order.product_return.date_seller_confirm_return = datetime.utcnow()
        target_order.product_return.returned_product_inspection_time_triggered = True
        target_order.product_return.date_returned_product_inspection_time_triggered = (
            datetime.utcnow()
        )
        target_order.date_updated = datetime.utcnow()

        new_timeline = TransactionTimeline(
            event_occurrance=f"Return of product {ref_no} has been successfully marked as delivered by the seller",
            category="Product Return",
            order=target_order,
        )

        db.session.add(new_timeline)
        db.session.commit()

        return (
            jsonify(
                status="success",
                message="Product return has successfully been marked as delivered by seller",
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@dispute.put("accept_return_conditions/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
@to_be_returned
def accept_return_conditions(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if not target_order.product_return_confirm_seller:
            return (
                jsonify(
                    status="error",
                    message="please ensure return delivery has been confirmed",
                ),
                400,
            )

        if target_order.seller_accept_return_condition:
            return (
                jsonify(
                    status="error",
                    message="condition of return has already been confirmed",
                ),
                400,
            )

        target_order.product_return.seller_accept_return_condition = True
        target_order.product_return_complete.product_return_complete = True
        target_order.product_return.date_of_completion = datetime.utcnow()
        new_timelin_acc = TransactionTimeline(
            event_occurrance=f"Conditions of the return of product {ref_no} has been successfully accepted",
            category="Product Return",
            order=target_order,
        )

        target_order.refund_approved = True
        target_order.date_updated = datetime.utcnow()
        new_timeline_ref = TransactionTimeline(
            event_occurrance=f"Refund of funds for product {ref_no} has been successfully approved",
            category="Refund",
            order=target_order,
        )
        db.session.add_all([new_timelin_acc, new_timeline_ref])
        db.session.commit()

        return (
            jsonify(
                status="success",
                message="Product return has successfully been marked as accepted",
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@dispute.put("initiate_refund/<ref_no>")
@jwt_required()
@api_secret_key_required
@order_exists
@to_be_returned
def initiate_refund(ref_no):
    try:
        target_order = Order.query.filter_by(reference_no=ref_no).first()

        if not target_order.refund_approved:
            return (
                jsonify(
                    status="error", message="refund of funds have not been approved"
                ),
                400,
            )

        if target_order.refund_initiated:
            return (
                jsonify(
                    status="error",
                    message="refund of funds have already been initiated",
                ),
                400,
            )

        amount_to_refund = target_order.product_return.amount_to_refund
        customer = target_order.customer
        p_amount_to_refund = amount_to_refund * 100
        customer_name = (
            f"{target_order.customer.last_name} {target_order.customer.first_name}"
        )
        pk_ref = f"pk_refund_{uuid.uuid1()}"
        reason = f"Refund payout to {customer_name} for order {ref_no}"

        p_client = PaystackClient()

        payload = {
            "source": "balance",
            "reason": reason,
            "curreny": "NGN",
            "recipient": customer.receipient_code,
            "amount": p_amount_to_refund,
            "reference": pk_ref,
        }

        response, stat_code = p_client.initiate_payout(payload=payload)
        if stat_code == 400:
            # USING KORAPAY TO IMMEDIATELY SEND OUT MONEY IF PAYSTACK DOESNT WORK
            k_client = KoraClient()
            k_ref = f"k_refund_{uuid.uuid1()}"
            k_payload = {
                "reference": k_ref,
                "destination": {
                    "type": "bank_account",
                    "amount": amount_to_refund,
                    "currency": "NGN",
                    "narration": reason,
                    "bank_account": {
                        "bank": customer.bank_account_code,
                        "account": customer.bank_account_number,
                    },
                    "customer": {
                        "name": customer.bank_account_name,
                        "email": customer.email_address,
                    },
                },
            }

            k_response, k_stat_code = k_client.single_payout(k_payload)

            if k_response["status"] and k_stat_code == 200:
                r_client.set(k_ref, ref_no)

                target_order.refund_initiated = True
                target_order.refund_processing = True
                target_order.date_updated = datetime.utcnow()
                new_timeline = TransactionTimeline(
                    event_occurrance=f"Refund have been successfully initiated with ref_no {k_ref}",
                    category="Refund",
                    order=target_order,
                )
                db.session.add(new_timeline)
                db.session.commit()

                return (
                    jsonify(
                        {
                            "status": "success",
                            "message": "refund has been initiated successfully with Korapay, hold for verification",
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
                            "message": "unable to initiate refund with Korapay",
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
            target_order.refund_initiated = True
            target_order.refund_processing = True
            target_order.date_updated = datetime.utcnow()
            new_timeline = TransactionTimeline(
                event_occurrance=f"Refund have been successfully initiated with ref_no {pk_ref}",
                category="Refund",
                order=target_order,
            )
            db.session.add(new_timeline)
            db.session.commit()

            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "refund has been initiated successfully with Paystack, hold for verification",
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
                        "message": "unable to initiate refund with Paystack",
                    }
                ),
                400,
            )
    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


"""
ARBITRATE SECTION FOR UNRESOLVED DISPUTES
- TRIGGER ARBITRATION REQUIRED
- REFER THEM TO SUPPORTED ARBITRATE BODIES
- COLLECT INFORMATION AND AWAIT RESULT
- REMIT REMAINING MONEY TO THEM **
- HOLD MONEY FOR RESULT OF ARBITRATE **
- RECEIVE CONLCUSION OF ARBITRATION AND ACT ACCORDINGLY

"""


# @dispute.put("get_arbitrate_information/<ref_no>")
# @jwt_required()
# @api_secret_key_required
# @order_exists
# def get_arbitrate_information(ref_no):
#     try:


# @dispute.put("initiate_arbitration/<ref_no>")
# @jwt_required()
# @api_secret_key_required
# @order_exists
# def initiate_arbitration(ref_no):
#     try:
#         target_order = Order.query.filter_by(reference_no=ref_no).first()

#         if not target_order.arbitration_required:
#             return (
#                 jsonify(
#                     status="error", message="arbitration doesnt appear to be needed"
#                 ),
#                 400,
#             )

#         if target_order.arbitration_ongoing:
#             return (
#                 jsonify(
#                     status="error", message="arbitration is currently ongoing already"
#                 ),
#                 400,
#             )
