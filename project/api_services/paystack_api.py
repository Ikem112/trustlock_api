import requests
import json
import os
import dotenv


class PaystackClient:
    def __init__(self):
        try:
            self.BASE_URL = os.environ.get("PAYSTACK_BASEURL")
            self.SECRET_KEY = os.environ.get("PAYSTACK_SECRETKEY")
            self.headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.SECRET_KEY}",
            }

        except Exception as e:
            print(e)

    def initialize_transaction(self, payload: dict):
        try:
            url = f"{self.BASE_URL}/transaction/initialize"
            response = requests.post(
                url, data=json.dumps(payload), headers=self.headers
            )

            return response.json(), response.status_code

        except Exception as e:
            print(e)
            return (e), 400

    def paystack_verify_transaction(self, reference):
        try:
            url = f"{self.BASE_URL}/transaction/verify/{reference}"
            response = requests.get(url, headers=self.headers)
            return response.json(), response.status_code

        except Exception as e:
            print(e)
            return (e), 400

    def get_supported_banks(self):
        try:
            url = f"{self.BASE_URL}/bank"
            params = {"country": "nigeria"}
            response = requests.get(url, headers=self.headers, params=params)
            return response.json(), response.status_code
        except Exception as e:
            print(e)
            return (e), 400

    def create_transfer_receipient(self, payload: dict):
        try:
            url = f"{self.BASE_URL}/transferrecipient"
            body = json.dumps(payload)
            print(body)
            response = requests.post(url, data=body, headers=self.headers)
            print(response.json())
            print("successful")
            return response.json(), response.status_code
        except Exception as e:
            print("not successfull")
            print(e)
            return (e), 400

    def resolve_account_number(self, payload: dict):
        try:
            url = f"{self.BASE_URL}/bank/resolve"
            params = {
                "account_number": payload["account_number"],
                "bank_code": payload["bank_code"],
            }
            response = requests.get(url, params=params, headers=self.headers)
            return response.json(), response.status_code
        except Exception as e:
            print(e)
            return (e), 400

    def initiate_tranfer_to_people(self, payload: dict):
        # try:
        #     url = f"{self.BASE_URL}/transfer"
        #     body = json.dumps(payload)
        #     response = requests.post(url, data=body, headers=self.headers)
        #     return response.json(), response.status_code
        # except Exception as e:
        #     print(e)
        #     return (e), 400
        pass


# !!! FUNCTIONS TO STREAMLINE PAYSTACK SERVICES !!!


def validate_account_details(payload: dict):
    try:
        p_client = PaystackClient()

        bank_response, br_stat_code = p_client.get_supported_banks()

        if bank_response["status"] == False:
            return {"status": False, "message": "failed to get bank"}, br_stat_code

        bank = next(
            (
                bank
                for bank in bank_response["data"]
                if bank["name"] == payload["bank_name"]
            ),
            None,
        )

        if bank and bank["active"]:
            bank_code = bank.get("code")
            req_payload = {
                "account_number": payload["account_number"],
                "bank_code": bank_code,
            }
            validate_response, v_stat_code = p_client.resolve_account_number(
                payload=req_payload
            )

            if validate_response["status"]:
                return {
                    "status": True,
                    "message": "account validated successfully",
                    "bank_code": bank_code,
                    "data": validate_response["data"],
                }, v_stat_code
            else:
                return {
                    "status": False,
                    "message": "account not valid",
                    "data": validate_response.get("data"),
                }, v_stat_code
        else:
            return {
                "status": False,
                "message": "bank not found",
            }, 400
    except Exception as e:
        print("soemthing went wrong with function")
        print(e)
        print(e.args)
        return {
            "status": True,
            "message": "something went wrong, refer to code",
        }, 400
