from flask import Flask
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_apscheduler import APScheduler
from .config import configuration
import redis
import multiprocessing


# instantiating flask modules

db = SQLAlchemy()
ma = Marshmallow()
jwt = JWTManager()
bcrypt = Bcrypt()
migrate = Migrate()
scheduler = APScheduler()
r_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)


# function that initialises the modules, blueprints and config keys with the app object
# ALWAYS CHANGE CONFIG KEY TO PRODUCTION WHEN PUSHING !!!


def create_app(config_type=configuration["development"]):
    app = Flask(__name__)
    app.config.from_object(config_type)
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    scheduler.init_app(app)
    migrate.init_app(app, db)
    app.lock = multiprocessing.Lock()

    status = "dev"

    with app.app_context():

        from .merchants import merchant as merchant_views

        app.register_blueprint(merchant_views, url_prefix=f"/api/{status}/v1")

        from .transactions import transaction as transaction

        app.register_blueprint(transaction, url_prefix=f"/api/{status}/v1")

        from .disputes import dispute as dispute

        app.register_blueprint(dispute, url_prefix=f"/api/{status}/v1")

    return app


from .merchants.models import (
    Merchant,
    MerchantDetails,
    Order,
    TransactionCondition,
    TransactionTimeline,
    Dispute,
    BusinessDetails,
)


@jwt.user_identity_loader
def user_identity_lookup(user):
    """
    Automatically fetch authenticated
    user id from the database
    """

    return user.id


@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_payload):
    """
    Automatically load authenticated user object
    from database, making current_user available
    for route wrapped with the @jwt_required() decorator
    """

    identity = jwt_payload["sub"]
    return Merchant.query.filter_by(id=identity).one_or_none()
