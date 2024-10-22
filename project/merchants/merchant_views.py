from datetime import timedelta, datetime
import json
import os
from dotenv import load_dotenv
import uuid
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


from . import merchant
from project import db, jwt, bcrypt, r_client
from .models import (
    Merchant,
    MerchantSchema,
    MerchantDetails,
    MerchantDetailsSchema,
    Order,
    TransactionCondition,
    OrderSchema,
    TransactionConditionSchema,
    TransactionTimeline,
    BusinessDetails,
    BusinessDetailsSchema,
    Dispute,
    DisputeSchema,
)

from ..decorators import api_secret_key_required
from ..api_services.paystack_api import PaystackClient, validate_account_details
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

# this decorator and the one below are for assigning the current user from JWT
# to a user from the db when a user logs in
# I no sabi as e dey work but it sha works


load_dotenv()


@merchant.post("/register_merchant")
def register_merchant():
    try:
        data = request.get_json()

        email_regex = "^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w{2,3}$"
        password_regex = (
            "^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&/])[A-Za-z\d@$!%*?&/]{8,}$"
        )

        if not (re.search(email_regex, data["email"])):
            return jsonify({"error": "please enter a valid mail"}), 400
        if not (re.search(password_regex, data["password"])):
            return jsonify({"error": "invalid password format"}), 400

        merchant = MerchantDetails.query.filter_by(email_address=data["email"]).first()

        if merchant:
            return jsonify({"status": "error", "data": "user already exists"}), 400

        crypt_pass = bcrypt.generate_password_hash(data["password"]).decode("utf-8")

        api_secret_key = str(f"tl-sk-api-{uuid.uuid4()}")
        api_public_key = str(f"tl-pk-api{uuid.uuid4()}")

        new_merchant = Merchant()

        merchant_details = MerchantDetails(
            legal_first_name=data.get("first_name").lower(),
            legal_other_name=data.get("middle_name").lower(),
            legal_last_name=data.get("last_name").lower(),
            residing_country=data.get("country").lower(),
            residing_state=data.get("state").lower(),
            residing_address=data.get("address").lower(),
            password=crypt_pass,
            email_address=data.get("email"),
            api_secret_key=api_secret_key,
            api_public_key=api_public_key,
            phone_no=data.get("phone_no"),
            merchant=new_merchant,
        )

        db.session.add(new_merchant)
        db.session.add(merchant_details)
        db.session.commit()

        current_merchant = MerchantDetails.query.filter_by(
            email_address=data.get("email")
        ).first()

        access_token = create_access_token(identity=current_merchant)

        return (
            jsonify(
                {
                    "status": "success",
                    "data": "successfully registered merchant",
                    "access_token": access_token,
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        return f"something went wrong  {e}", 500


@merchant.post("login_merchant")
def login_merchant():

    try:
        data = request.get_json()

        email = data.get("email")
        password = data.get("password")
        merchant_check = MerchantDetails.query.filter_by(email_address=email).first()

        if merchant_check:
            pass_decode = bcrypt.check_password_hash(merchant_check.password, password)
            if pass_decode:
                current_merchant = Merchant.query.filter_by(
                    id=merchant_check.merchant_id
                ).first()
                access_token = create_access_token(identity=current_merchant)
                api_key = merchant_check.api_secret_key
                return (
                    jsonify(
                        {
                            "status": "login success",
                            "access_token": access_token,
                            "api_key": api_key,
                            "message": "please ensure to keep your api key safe at all times",
                        }
                    ),
                    200,
                )
            else:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "email or password is incorrect, please try again",
                        }
                    ),
                    401,
                )
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "email or password is incorrect, please try again",
                    }
                ),
                401,
            )
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@merchant.get("get_merchant_details")
@jwt_required()
@api_secret_key_required
def get_merchcant_details():

    try:
        merchant_schema = MerchantSchema()

        data = merchant_schema.dump(current_user)

        return jsonify({"status": "success", "data": data}), 200
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@merchant.put("update_merchant_details")
@jwt_required()
@api_secret_key_required
def update_merchant_details():

    try:
        data = request.get_json()

        merchant = Merchant.query.filter_by(id=current_user.id).first()

        if data.get("email"):
            email_regex = "^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w{2,3}$"
            if not (re.search(email_regex, data["email"])):
                return jsonify({"error": "invalid email format"}), 400

            merchant.merchant_details.email_address = data.get("email")
            merchant.email_verified = False
        if data.get("password"):
            pass_reg = "^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!#%*?&]{8,18}$"
            if not (re.search(pass_reg, data["password"])):
                return jsonify({"error": "invalid password format"}), 400

            merchant.merchant_details.password = bcrypt.generate_password_hash(
                data.get("password")
            ).decode("utf-8")

        merchant.merchant_details.legal_first_name = (
            data["first_name"]
            if data.get("first_name")
            else merchant.merchant_details.legal_first_name
        )
        merchant.merchant_details.legal_last_name = (
            data["last_name"]
            if data.get("last_name")
            else merchant.merchant_details.legal_last_name
        )
        merchant.merchant_details.legal_other_name = (
            data["other_name"]
            if data.get("other_name")
            else merchant.merchant_details.legal_other_name
        )
        merchant.merchant_details.residing_country = (
            data["country"]
            if data.get("country")
            else merchant.merchant_details.residing_country
        )
        merchant.merchant_details.residing_state = (
            data["state"]
            if data.get("state")
            else merchant.merchant_details.residing_state
        )
        merchant.merchant_details.residing_address = (
            data["address"]
            if data.get("address")
            else merchant.merchant_details.residing_address
        )
        merchant.merchant_details.phone_no = (
            data["phone_no"]
            if data.get("phone_no")
            else merchant.merchant_details.phone_no
        )
        merchant.merchant_details.date_last_updated = datetime.utcnow()

        db.session.commit()

        return (
            jsonify({"status": "success", "message": "details succesfully updated"}),
            200,
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@merchant.post("send_verification_email")
@jwt_required()
@api_secret_key_required
def send_verification_email():
    try:
        from project.api_services.sendgrid_api import Mailer

        email_address = current_user.merchant_details.email_address
        first_name = current_user.merchant_details.legal_first_name
        first_name = first_name.capitalize()

        mailer = Mailer()

        data, status = mailer.send_verification_mail(
            email=email_address, name=first_name
        )

        print("sent the mail")
        print(data)
        r_client.set(f"token-{data['token']}", current_user.id)
        print("set in redis")

        return jsonify(data), status

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@merchant.get("verify_email/<token>")
def verify_email_address(token):

    try:
        serializer = URLSafeTimedSerializer(os.environ.get("DEV_SECRET_KEY"))
        try:
            email = serializer.loads(token, salt="email-confirm-salt", max_age=3600)
        except SignatureExpired:
            return None  # Token expired
        except BadSignature:
            return None  # Invalid token

        if email:
            print("verified_email")
            user = r_client.get(f"token-{token}").decode("utf-8")
            update_merchant = Merchant.query.filter_by(id=user).first()
            if update_merchant.email_verified == True:
                return (
                    jsonify(
                        {"message": "Email has already been verified successfully."}
                    ),
                    200,
                )

            update_merchant.email_verified = True
            db.session.commit()
            print("successfully verified mail")
            return jsonify({"message": "Email verified successfully."}), 200

        else:
            return (
                jsonify({"message": "Invalid or expired token, please try again"}),
                400,
            )

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@merchant.post("register_business")
@jwt_required()
def register_business():

    try:
        data = request.get_json()

        current_merchant = Merchant.query.filter_by(id=current_user.id).first()

        existing_business_email = BusinessDetails.query.filter_by(
            email_address=data["email_address"]
        ).first()
        existing_business_no = BusinessDetails.query.filter_by(
            phone_no=data["phone_no"]
        ).first()
        existing_business_name = BusinessDetails.query.filter_by(
            name=data["name"]
        ).first()

        if existing_business_email or existing_business_no or existing_business_name:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "business name, email or phone number already in use",
                    }
                ),
                400,
            )
        print("we are here")
        valid_acc, va_stat_code = validate_account_details(
            {
                "bank_name": data.get("bank_name"),
                "account_number": data.get("bank_account_number"),
            }
        )

        if not valid_acc["status"]:
            return (
                jsonify({"status": "error", "message": valid_acc["message"]}),
                va_stat_code,
            )
        acc_name = data.get("bank_account_name")
        input_result = acc_name.replace("-", "")
        input_result = input_result.lower()
        input_result_list = input_result.split()
        derived_result = valid_acc["data"]["account_name"]
        derived_result = derived_result.lower()
        derived_result_list = derived_result.split()

        result = set(input_result_list).issubset(derived_result_list)
        print(derived_result_list)
        print(input_result_list)

        if not result:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "bank details are not corresponding, please check inputs",
                    }
                ),
                400,
            )

        p_client = PaystackClient()

        payload = {
            "type": "nuban",
            "name": valid_acc["data"]["account_name"],
            "account_number": valid_acc["data"]["account_number"],
            "bank_code": valid_acc["bank_code"],
            "currency": "NGN",
        }

        response, response_code = p_client.create_transfer_receipient(payload=payload)

        if not response["status"]:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "error creating transfer receipient for business",
                    }
                ),
                response_code,
            )

        resp_data = response["data"]

        new_business = BusinessDetails(
            name=data.get("name"),
            description=data.get("description"),
            phone_no=data.get("phone_no"),
            email_address=data.get("email_address"),
            country_of_operation=data.get("country_of_operation"),
            state_of_operation=data.get("state_of_operation"),
            product_sold=data.get("product_sold"),
            bank_name=resp_data["details"]["bank_name"],
            bank_account_number=resp_data["details"]["account_number"],
            bank_account_name=resp_data["details"]["account_name"],
            bank_account_code=resp_data["details"]["bank_code"],
            receipient_code=resp_data["recipient_code"],
            upper_bound_product_price_range=data.get("upper_price_range"),
            lower_bound_product_price_range=data.get("lower_price_range"),
            merchant=current_merchant,
        )
        current_merchant.registered_business = True

        db.session.add(new_business)
        db.session.commit()

        return (
            jsonify(
                {"status": "success", "message": "business registered successfully"}
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"status": "error", "message": "something went wrong"}), 500


@merchant.post("edit_business_details")
@jwt_required()
def edit_business_details():
    pass
