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
