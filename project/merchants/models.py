import uuid
from datetime import datetime, timedelta
from project import db, ma


def unique_id():
    return uuid.uuid4().hex


class Merchant(db.Model):
    __tablename__ = "Merchant"

    id = db.Column(
        db.String(50), primary_key=True, nullable=False, default=unique_id, index=True
    )
    send_monthly_reports = db.Column(db.Boolean, default=True)
    suspended = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    registered_business = db.Column(db.Boolean, default=False)
    confirmed_registered_business = db.Column(db.Boolean, default=False)
    merchant_details = db.relationship(
        "MerchantDetails", cascade="all,delete", backref="merchant", uselist=False
    )
    business_details = db.relationship(
        "BusinessDetails",
        cascade="all,delete",
        backref="merchant",
    )
    orders = db.relationship("Order", backref="merchant")

    def __repr__(self):
        return f"Merchant(id={self.id})"


class MerchantSchema(ma.Schema):
    merchant_details = ma.Nested("MerchantDetailsSchema")
    business_details = ma.Nested("BusinessDetailsSchema")
    order = ma.Nested("OrderSchema", many=True)

    class Meta:
        fields = (
            "id",
            "suspended",
            "merchant_details",
            "business_details",
            "orders",
        )


class MerchantDetails(db.Model):
    __tablename__ = "MerchantDetails"

    id = db.Column(
        db.String(50), primary_key=True, nullable=False, default=unique_id, index=True
    )
    legal_first_name = db.Column(db.String(30), nullable=False)
    legal_other_name = db.Column(db.String(30))
    legal_last_name = db.Column(db.String(30), nullable=False)
    residing_country = db.Column(db.String(30), nullable=False)
    residing_state = db.Column(db.String(30), nullable=False)
    residing_address = db.Column(db.String(150), nullable=False)
    email_address = db.Column(db.String(40), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False, unique=True)
    api_secret_key = db.Column(db.String(100), nullable=False, unique=True)
    api_public_key = db.Column(db.String(100), nullable=False, unique=True)
    phone_no = db.Column(db.String(15), nullable=False, unique=True)
    date_joined = db.Column(db.DateTime, nullable=False, default=datetime.utcnow())
    date_last_updated = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow()
    )
    merchant_id = db.Column(db.String(50), db.ForeignKey("Merchant.id"))

    def __repr__(self):
        return f"MerchantDetails(id={self.id}, email={self.email_address})"


class MerchantDetailsSchema(ma.Schema):
    class Meta:
        fields = (
            "id",
            "legal_first_name",
            "legal_other_name",
            "legal_last_name",
            "residing_country",
            "residing_state",
            "residing_address",
            "email_address",
            "phone_no",
        )


class BusinessDetails(db.Model):
    __tablename__ = "BusinessDetails"

    id = db.Column(
        db.String(50), primary_key=True, nullable=False, default=unique_id, index=True
    )
    name = db.Column(db.String(40), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)
    phone_no = db.Column(db.String(15), nullable=False, unique=True)
    email_address = db.Column(db.String(40), nullable=False, unique=True)
    country_of_operation = db.Column(db.String(40), nullable=False)
    state_of_operation = db.Column(db.String(40), nullable=False)
    product_sold = db.Column(db.String(30), nullable=False)
    upper_bound_product_price_range = db.Column(db.Float, nullable=False)
    lower_bound_product_price_range = db.Column(db.Float, nullable=False)
    date_joined = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    date_last_updated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    merchant_id = db.Column(db.String(50), db.ForeignKey("Merchant.id"))

    def __repr__(self):
        return f"Business Details --- {self.name}, {self.email_address}, {self.product_sold}, {self.date_joined}"


class BusinessDetailsSchema(ma.Schema):
    class Meta:
        fields = (
            "id",
            "name",
            "description",
            "phone_no",
            "email_address",
            "country_of_operation",
            "state_of_operation",
            "product_sold",
            "date_joined",
            "date_last_updated",
        )


class Order(db.Model):
    __tablename__ = "Order"

    id = db.Column(
        db.String(50), primary_key=True, nullable=False, default=unique_id, index=True
    )
    reference_no = db.Column(db.String(50), nullable=False, index=True)
    product_name = db.Column(db.String(20), nullable=False)
    product_description = db.Column(db.Text)
    product_amount = db.Column(db.Float, nullable=False)
    escrow_percent = db.Column(db.Float, nullable=False)
    escrow_fee = db.Column(db.Float, nullable=False)
    process_fee = db.Column(db.Float, nullable=False)
    amount_to_pay = db.Column(db.Float, nullable=False)
    amount_to_balance = db.Column(db.Float)
    total_amount_received = db.Column(db.Float, nullable=False)
    amount_verified = db.Column(db.Boolean, default=False, nullable=False)
    partial_dispersals = db.Column(db.Boolean, default=False, nullable=False)
    partial_amount_dispersed = db.Column(db.Float, nullable=False, default=0)
    partial_amount_to_be_dispersed = db.Column(db.Float, nullable=False, default=0)
    product_delivered = db.Column(db.Boolean, nullable=False, default=False)
    product_inspected = db.Column(db.Boolean, nullable=False, default=False)
    product_inspection_time = db.Column(db.String(20), nullable=False)
    conditions_met = db.Column(db.Boolean, default=False, nullable=False)
    dispute_raised = db.Column(db.Boolean, default=False)
    dispute_resolved = db.Column(db.Boolean, default=False)
    amount_to_be_refunded = db.Column(db.Float, nullable=False, default=0)
    amount_refunded = db.Column(db.Boolean, default=False)
    full_amount_dispersed = db.Column(db.Boolean, nullable=False, default=False)
    order_initiated = db.Column(db.Boolean, default=False, nullable=False)
    order_commenced = db.Column(db.Boolean, default=False, nullable=False)
    order_closed = db.Column(db.Boolean, default=False, nullable=False)
    date_initiated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    date_updated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    date_closed = db.Column(db.DateTime, default=None)
    special_attention = db.Column(db.Boolean, default=False, nullable=False)
    merchant_id = db.Column(db.String(50), db.ForeignKey("Merchant.id"))
    transaction_history = db.relationship(
        "TransactionHistory", cascade="all,delete", backref="order"
    )
    transaction_condition = db.relationship(
        "TransactionCondition", cascade="all,delete", backref="order"
    )
    transaction_timeline = db.relationship(
        "TransactionTimeline", cascade="all,delete", backref="order"
    )
    dispute = db.relationship("Dispute", cascade="all,delete", backref="order")
    customer = db.relationship(
        "Customer", cascade="all,delete", backref="order", uselist=False
    )

    def __repr__(self):
        return f"Transaction --- {self.product_name}, {self.amount_verified}---{self.initial_amount_received}, product deliverd: {self.product_delivered}, escrow percent: {self.escrow_percent}, {self.transaction_closed}"


class OrderSchema(ma.Schema):
    transaction_history = ma.Nested("TransactionHistorySchema", many=True)
    transaction_condition = ma.Nested("TransactionConditionSchema", many=True)
    transaction_timeline = ma.Nested("TransactionTimelineSchema", many=True)
    dispute = ma.Nested("DisputeSchema", many=True)
    customer = ma.Nested("CustomerSchema")

    class Meta:
        fields = (
            "id",
            "reference_no",
            "product_name",
            "product_description",
            "amount_verified",
            "initial_amount_received",
            "product_delivered",
            "product_inspected",
            "product_inspection_time" "partial_dispersals",
            "conditions_met",
            "escrow_percent",
            "balance_refunded",
            "full_amount_dispersed",
            "dispute_raised",
            "transaction_closed",
            "date_initiated",
            "date_updated",
            "transaction_history",
            "transaction_condition",
            "transaction_timeline",
            "dispute",
            "customer",
        )


class TransactionHistory(db.Model):
    __tablename__ = "TransactionHistory"

    id = db.Column(
        db.String(50), primary_key=True, nullable=False, default=unique_id, index=True
    )
    amount = db.Column(db.Float, nullable=False)
    trans_reference = db.Column(db.String(50), nullable=False, unique=True)
    sender = db.Column(db.String(20), nullable=False)
    receiver = db.Column(db.String(20), nullable=False)
    trans_action = db.Column(db.String(70), nullable=False)
    description = db.Column(db.Text, nullable=False)
    order_id = db.Column(db.String(50), db.ForeignKey("Order.id"))


class TransactionHistorySchema(ma.Schema):
    class Meta:
        fields = (
            "id",
            "amount",
            "trans_reference",
            "sender",
            "receiver",
            "trans_action",
            "description",
        )


class Customer(db.Model):
    __tablename__ = "Customer"

    id = db.Column(
        db.String(50), primary_key=True, nullable=False, default=unique_id, index=True
    )
    first_name = db.Column(db.String(20), nullable=False)
    last_name = db.Column(db.String(20), nullable=False)
    phone_no = db.Column(db.String(30), nullable=False, unique=True)
    email_address = db.Column(db.String(50), nullable=False, unique=True)
    country = db.Column(db.String(20), nullable=False)
    city = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=False)
    order_id = db.Column(db.String(50), db.ForeignKey("Order.id"))


class CustomerSchema(ma.Schema):
    class Meta:
        fields = (
            "id",
            "first_name",
            "last_name",
            "phone_no",
            "email_address",
            "country",
            "city",
            "address",
        )


class TransactionCondition(db.Model):
    __tablename__ = "TransactionCondition"
    id = db.Column(
        db.String(50), primary_key=True, nullable=False, default=unique_id, index=True
    )
    condition_title = db.Column(db.String(20), nullable=False)
    condition_description = db.Column(db.Text, nullable=False)
    party_to_meet_condition = db.Column(db.String(10), nullable=False)
    condition_met = db.Column(db.Boolean, default=False, nullable=False)
    date_added = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    date_met = db.Column(db.DateTime)
    order_id = db.Column(db.String(50), db.ForeignKey("Order.id"))

    def __repr__(self):
        return f" trans condition --- {self.condition_title},  party_conditioner --- {self.party_to_meet_condition}, condition met -- {self.condition_met}, date -- {self.date_added}"


class TransactionConditionSchema(ma.Schema):
    class Meta:
        fields = (
            "id",
            "condition_title",
            "condition_description",
            "party_to_meet_condition",
            "condition_met",
            "date_added",
            "date_met",
        )


class Dispute(db.Model):
    __tablename__ = "Dispute"

    id = db.Column(
        db.String(50), primary_key=True, nullable=False, default=unique_id, index=True
    )
    dispute_title = db.Column(db.String(20), nullable=False)
    dispute_description = db.Column(db.Text, nullable=False)
    dispute_resolved = db.Column(db.Boolean, default=False, nullable=False)
    dispute_raised_date = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )
    dispute_resolved_date = db.Column(db.DateTime)
    order_id = db.Column(db.String(50), db.ForeignKey("Order.id"))

    def __repr__(self):
        return f"dispute -- {self.dispute_title}, dispute resolution -- {self.dispute_resolved}, date raised -- {self.dispute_raised_date}, settle date -- {self.dispute_resolved_date}"


class DisputeSchema(ma.Schema):
    class Meta:
        fields = (
            "id",
            "dispute_title",
            "dispute_description",
            "dispute_resolved",
            "dispute_raised_date",
            "dispute_resolved_date",
        )


class TransactionTimeline(db.Model):
    __tablename__ = "TransactionTimeline"

    id = db.Column(
        db.String(50), primary_key=True, nullable=False, default=unique_id, index=True
    )
    event_occurrance = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    order_id = db.Column(db.String(50), db.ForeignKey("Order.id"))

    def __repr__(self):
        return f"Timeline event -- {self.event_occurrance} --, date -- {self.date}"


class TransactionTimelineSchema(ma.Schema):
    class Meta:
        fields = ("event_occurrance", "date")
