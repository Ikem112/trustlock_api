import os
from celery import Celery
from flask import jsonify
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail,
    Email,
    Personalization,
    From,
    To,
    TemplateId,
    Substitution,
)
from itsdangerous import URLSafeTimedSerializer
from project.helpers import get_email_html_template, get_payment_verification_template


load_dotenv()

celery = Celery(
    "tasks", broker="redis://localhost:6379/0", backend="redis://localhost:6379/0"
)


class Mailer:
    def __init__(self):
        try:
            self.SENDGRID_API_KEY_2 = os.environ.get("SENDGRID_API_KEY_2")
            self.TEMPLATE_ID = os.environ.get("SENDGRID_TEMPLATE_ID")
            self.SENDER_EMAIL_ADDRESS = os.environ.get("SENDER_EMAIL_ADDRESS")
            self.SERIALIZER = URLSafeTimedSerializer(os.environ.get("DEV_SECRET_KEY"))

        except Exception as e:
            print(e)

    @celery.task
    def send_verification_mail(self, email, name):
        try:
            token = self.SERIALIZER.dumps(email, salt="email-confirm-salt")
            verification_url = f"https://elegant-buck-deciding.ngrok-free.app/api/dev/v1/verify_email/{token}"

            message = Mail(
                from_email=self.SENDER_EMAIL_ADDRESS,
                to_emails=email,
                subject="Verify your email with TrustLock",
                html_content=get_email_html_template(
                    "emailVerifyTemplate.html", name, verification_url
                ),
            )

            try:
                sg = SendGridAPIClient(self.SENDGRID_API_KEY_2)
                response = sg.send(message)
                print("we got a response")
                print(f"Email sent with status code {response.status_code}")
                print(response.headers, response.body)
                return (
                    {"data": "successfully sent email", "token": token},
                    response.status_code,
                )
            except Exception as e:
                print("we got an error")
                print(f"Error sending email: {e}")
                print(response)
                return (
                    jsonify({"data": f"error sending mail -- {e}"}),
                    500,
                )

        except Exception as e:
            print(e)
            return (e), 400

    @celery.task
    def send_payment_confirmation_mail(self, email, payload):
        try:
            message = Mail(
                from_email=self.SENDER_EMAIL_ADDRESS,
                to_emails=email,
                subject="Payment Receipt",
                html_content=get_payment_verification_template(
                    "emailPaymentConfirmation.html", payload=payload
                ),
            )
            try:
                sg = SendGridAPIClient(self.SENDGRID_API_KEY_2)
                response = sg.send(message)
                print("we got a response")
                print(f"Email sent with status code {response.status_code}")
                print(response.headers, response.body)
                return (
                    {"data": "successfully sent email"},
                    response.status_code,
                )
            except Exception as e:
                print("we got an error")
                print(f"Error sending email: {e}")
                print(response)
                return (
                    jsonify({"data": f"error sending mail -- {e}"}),
                    500,
                )
        except Exception as e:
            print(e)
            return (e), 400
