import requests
import json
import os
import dotenv


class KoraClient:
    def __init__(self):
        try:
            self.BASE_URL = os.environ.get("KORA_BASEURL")
            self.SECRET_KEY = os.environ.get("KORA_SECRETKEY")
            self.headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.SECRET_KEY}",
            }

        except Exception as e:
            print(e)

    def single_payout(self, payload: dict):
        try:
            url = f"{self.BASE_URL}/transactions/disburse"
            response = requests.post(
                url, data=json.dumps(payload), headers=self.headers
            )

            return response.json(), response.status_code

        except Exception as e:
            print(e)
            return (e), 400
