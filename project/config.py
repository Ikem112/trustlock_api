import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()
# classes to get app config keys from the environment
class DevelopmentConfig:
    DEBUG = True  # ensures debugger is on during testing and development
    SECRET_KEY = os.environ.get("DEV_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = (
        "postgresql://postgres:OmoLewa223@localhost/trustlock_test_db"
    )
    JWT_SECRET_KEY = "dev_jwt_secret_key"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)


class ProductionConfig:
    DEBUG = False
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")


configuration = {"production": ProductionConfig, "development": DevelopmentConfig}
