from fuprox import db, ma
from datetime import datetime
import secrets
from fuprox import app
from dateutil import parser
import random


def unique_code() -> int:
    return secrets.token_hex(32)


def verify_token():
    return int(str(random.getrandbits(32))[:6])


def default_preq_date():
    return parser.parse("01/01/1970")


def midnight():
    return parser.parse("00:00")


# working with flask migrate
class ServiceOffered(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.ForeignKey("branch.id"), nullable=False)
    name = db.Column(db.String(length=250), unique=True)
    teller = db.Column(db.String(100), nullable=True)
    date_added = db.Column(db.DateTime, default=datetime.now)
    code = db.Column(db.String(length=10), nullable=False, unique=True)
    icon = db.Column(db.String(length=20))
    is_synced = db.Column(db.Boolean, default=False)
    unique_id = db.Column(db.String(250), default=unique_code, unique=True)
    medical_active = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)

    def __init__(self, name, branch_id, teller, code, icon):
        self.name = name
        self.branch_id = branch_id
        self.teller = teller
        self.code = code
        self.icon = icon
        self.is_synced = False


class ServiceOfferedSchema(ma.Schema):
    class Meta:
        fields = ("id", "branch_id", "name", "teller", "date_added", "code", "icon", "unique_id", "medical_active",
                  "active")


# creating a booking ID
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(length=250), nullable=True)
    start = db.Column(db.String(length=200))
    branch_id = db.Column(db.ForeignKey("branch.id"), nullable=False)
    ticket = db.Column(db.String(length=6), nullable=False)
    date_added = db.Column(db.DateTime, default=datetime.now, unique=True)
    active = db.Column(db.Boolean, default=False, nullable=False)
    nxt = db.Column(db.Integer, nullable=False, default=1001)
    serviced = db.Column(db.Boolean, nullable=False, default=False)
    teller = db.Column(db.String(250), default=0, nullable=False)
    kind = db.Column(db.Integer, nullable=False)
    user = db.Column(db.Integer, default=0, nullable=False)
    is_instant = db.Column(db.Boolean, default=False)
    forwarded = db.Column(db.Boolean, default=False)
    is_synced = db.Column(db.Boolean, default=False)
    unique_id = db.Column(db.String(250), default=unique_code, unique=True)
    unique_teller = db.Column(db.String(250), default=000)
    verify = db.Column(db.Integer, default=verify_token)

    def __init__(self, service_name, start, branch_id, ticket, active, nxt, serviced, teller, kind, user, instant,
                 fowarded):
        self.service_name = service_name
        self.start = start
        self.branch_id = branch_id
        self.ticket = ticket
        self.active = active
        self.nxt = nxt
        self.serviced = serviced
        self.teller = teller
        self.kind = kind
        self.user = user
        self.is_instant = instant
        self.forwarded = fowarded
        self.nxt = 1001


class BookingSchema(ma.Schema):
    class Meta:
        fields = ("id", "service_name", "start", "branch_id", "ticket", "active", "nxt", "serviced", "teller", \
                  "kind", "user", "is_instant", "forwarded", "is_synced", "unique_id", "unique_teller", "date_added",
                  "verify")


# creating a booking ID
class BookingMpesa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phoneNumber = db.Column(db.String(250), default=000)
    token = db.Column(db.String(250), default=000)
    date_added = db.Column(db.DateTime, default=datetime.now, unique=True)

    def __init__(self, phonenumber, token):
        self.phoneNumber = phonenumber
        self.token = token


class BookingMpesaSchema(ma.Schema):
    class Meta:
        fields = ("id", "phonenumber", "token", "date_added")


# user DB model
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(48), unique=True, nullable=False)
    phoneNumber = db.Column(db.String(12), unique=True, nullable=False)
    image_file = db.Column(db.String(200), nullable=False, default="default.jpg")
    password = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f"User (' {self.id} '{self.email}' )"

    def __init__(self, email, phone, password):
        self.email = email
        self.phoneNumber = phone
        self.password = password


class CustomerSchema(ma.Schema):
    class Meta:
        fields = ("id", "email", "phoneNumber", "password")


# creating a company class
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(length=50), unique=True)
    service = db.Column(db.String(length=250))
    is_synced = db.Column(db.Boolean, default=False)

    def __init__(self, name, service):
        self.name = name
        self.service = service

    def __repr__(self):
        return f"Company {self.name} -> {self.service}"


class CompanySchema(ma.Schema):
    class Meta:
        fields = ("id", "name", "service", "is_synced")


# creating a branch class

class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(length=250), unique=True)
    company = db.Column(db.String(length=100), db.ForeignKey("company.name"), nullable=False)
    longitude = db.Column(db.String(length=50))
    latitude = db.Column(db.String(length=50))
    opens = db.Column(db.String(length=50))
    closes = db.Column(db.String(length=50))
    service = db.Column(db.String(length=100), db.ForeignKey("service.name"))
    description = db.Column(db.String(length=50))
    key_ = db.Column(db.Text)
    valid_till = db.Column(db.DateTime)
    is_synced = db.Column(db.Boolean, default=False)
    unique_id = db.Column(db.String(250), nullable=False, unique=True)

    def __init__(self, name, company, longitude, latitude, opens, closes, service, description, key_, unique_id):
        self.name = name
        self.company = company
        self.longitude = longitude
        self.latitude = latitude
        self.opens = opens
        self.closes = closes
        self.service = service
        self.description = description
        self.key_ = key_
        self.unique_id = unique_id


# creating branch Schema
class BranchSchema(ma.Schema):
    class Meta:
        fields = (
            'id', 'name', 'company', 'address', 'longitude', 'latitude', 'opens', 'closes', 'service', 'description',
            "key_", "valid_till", "is_synced", "unique_id")


class Help(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(length=100), nullable=False)
    title = db.Column(db.String(length=250), nullable=False)
    solution = db.Column(db.Text, nullable=False)
    date_added = db.Column(db.DateTime, default=datetime.now, nullable=False)
    is_synced = db.Column(db.Boolean, default=False)

    def __init__(self, topic, title, solution):
        self.topic = topic
        self.title = title
        self.solution = solution


class HelpSchema(ma.Schema):
    class Meta:
        fields = ("id", "topic", "title", "solution", "date_added", "is_synced")


class Teller(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    date_added = db.Column(db.DateTime, default=datetime.now)
    branch = db.Column(db.Integer)
    service = db.Column(db.String(200))
    unique_id = db.Column(db.String(250), default=unique_code, unique=True)
    is_synced = db.Column(db.Boolean, default=False)
    branch_unique_id = db.Column(db.String(length=250), nullable=False, default=1234)
    active = db.Column(db.Boolean, default=True)

    def __init__(self, number, branch, service, branch_unique_id):
        self.number = number
        self.branch = branch
        self.service = service
        self.branch_unique_id = branch_unique_id


class TellerSchema(ma.Schema):
    class Meta:
        fields = (
        "id", "number", "date_added", "branch", "service", "is_synced", "unique_id", "branch_unique_id", "active")


'''
    teller/booking Model
'''


class TellerBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teller_to = db.Column(db.Integer, nullable=False)
    booking_id = db.Column(db.Integer, nullable=False)
    teller_from = db.Column(db.Integer)
    remarks = db.Column(db.Text, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    date_added = db.Column(db.DateTime, default=datetime.now)
    is_synced = db.Column(db.Boolean, default=False)
    pre_req = db.Column(db.Integer, default=0)
    preq_date_servived = db.Column(db.DateTime, default=default_preq_date)

    def __init__(self, teller_to, booking_id, teller_from, remarks, active):
        self.teller_to = teller_to
        self.teller_from = teller_from
        self.booking_id = booking_id
        self.remarks = remarks
        self.active = active


class TellerBookingSchema(ma.Schema):
    class Meta:
        fields = (
        "id", "teller_to", "booking_id", "teller_from", "remarks", "active", "date_added", "pre_req", "is_synced",
        "preq_date_servived")


# booking model
# creating a booking ID
class OnlineBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    service_name = db.Column(db.String(length=100), nullable=True)
    start = db.Column(db.String(length=200))
    branch_id = db.Column(db.Integer)
    ticket = db.Column(db.String(length=6), nullable=False)
    date_added = db.Column(db.DateTime, default=datetime.now)
    active = db.Column(db.Boolean, default=False, nullable=False)
    next = db.Column(db.Boolean, nullable=False, default=False)
    serviced = db.Column(db.Boolean, nullable=False, default=False)
    teller = db.Column(db.String(200), nullable=False, default=000000)

    def __init__(self, service_name, user_id, start, branch_id, ticket, active, next, serviced, teller):
        self.user_id = user_id
        self.service_name = service_name
        self.start = start
        self.branch_id = branch_id
        self.ticket = ticket
        self.active = active
        self.next = next
        self.serviced = serviced
        self.teller = teller


class OnlineBookingSchema(ma.Schema):
    class Meta:
        fields = (
        "id", "user_id", "service_name", "start", "branch_id", "ticket", "active", "next", "serviced", "date_added")


class Icon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(length=50), nullable=False, unique=True)
    date_added = db.Column(db.DateTime, default=datetime.now)
    branch = db.Column(db.Integer, nullable=False)
    icon = db.Column(db.Text)

    def __init__(self, name, branch, icon):
        self.name = name
        self.branch = branch
        self.icon = icon


class IconSchema(ma.Schema):
    class Meta:
        fields = ("id", "name", "date_added", "branch", "icon")


"""
>>>> MPESA PAYMENTS >>
"""


class Mpesa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=True)
    receipt_number = db.Column(db.String(250), nullable=True)
    transaction_date = db.Column(db.String(250), nullable=True)
    phone_number = db.Column(db.String(250), nullable=True)
    checkout_request_id = db.Column(db.String(250), nullable=True)
    merchant_request_id = db.Column(db.String(250), nullable=True)
    result_code = db.Column(db.Integer, nullable=False)
    result_desc = db.Column(db.Text, nullable=True)
    date_added = db.Column(db.DateTime(), default=datetime.now)
    local_transactional_key = db.Column(db.String(250), nullable=False)
    booking_id = db.Column(db.Integer, nullable=True, default=0)

    def __init__(self, MerchantRequestID, CheckoutRequestID, ResultCode, ResultDesc):
        self.merchant_request_id = MerchantRequestID
        self.checkout_request_id = CheckoutRequestID
        self.result_code = ResultCode
        self.result_desc = ResultDesc


class MpesaSchema(ma.Schema):
    class Meta:
        fields = ("id", "amount", "receipt_number", "transaction_data", "phone_number", "checkout_request_id",
                  "merchant_request_id", "result_code", "result_desc", "date_added", "local_transactional_key",
                  "booking_id")


class Payments(db.Model):
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    body = db.Column(db.Text, nullable=False)
    token = db.Column(db.String(length=250))
    date_added = db.Column(db.DateTime, default=datetime.now)
    used = db.Column(db.Boolean, default=False)

    def __init__(self, body, token):
        self.body = body
        self.token = token


class PaymentSchema(ma.Schema):
    class Meta:
        fields = ("id", "message", "token", "used")


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(length=50), unique=True)
    service = db.Column(db.String(length=250))
    is_medical = db.Column(db.Boolean, default=False)

    def __init__(self, name, service, is_medical):
        self.name = name
        self.service = service
        self.is_medical = is_medical


class ServiceSchema(ma.Schema):
    class Meta:
        fields = ("id", "name", "service", "is_medical")


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(12), unique=True, nullable=False)
    email = db.Column(db.String(48), unique=True, nullable=False)
    image_file = db.Column(db.String(20), nullable=False, default="default.jpg")
    password = db.Column(db.String(60), nullable=False)

    def __repr__(self):
        return f"User (' {self.id} ',' {self.username} ', '{self.email}', '{self.image_file}' )"

    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.password = password


class BookingTimes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, nullable=False, unique=True)
    date_added = db.Column(db.DateTime, default=datetime.now())
    service = db.Column(db.ForeignKey("service_offered.unique_id"), nullable=False)
    start = db.Column(db.DateTime, default=datetime.now)
    end = db.Column(db.DateTime, default=None)
    is_synced = db.Column(db.Boolean, default=False)

    def __init__(self, booking_id, service):
        self.booking_id = booking_id
        self.service = service


class BookingTimesSchema(ma.Schema):
    class Meta:
        fields = ("id", "booking_id", "start", "end", "service", "date_added", "is_synced")


class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(length=250), unique=True)
    active = db.Column(db.Integer, default=0)
    type = db.Column(db.Integer, default=0)

    def __init__(self, name, type):
        self.name = name
        self.type = type


class VideoSchema(ma.Schema):
    class Meta:
        fields = ("id", "name", "active", "type")


class Recovery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.ForeignKey("customer.id"), nullable=False)
    code = db.Column(db.String(length=50), nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)

    def __init__(self, user, code):
        self.user = user
        self.code = code


class RecoverySchema(ma.Schema):
    class Meta:
        fields = ("id", "user", "code")


class ImageCompany(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.ForeignKey("company.id"), nullable=False)
    image = db.Column(db.String(length=250), nullable=False)

    def __init__(self, company, image):
        self.company = company
        self.image = image


class ImageCompanySchema(ma.Schema):
    class Meta:
        fields = ("id", "company", "image")


class Utils:
    def random_numbers(self):
        return random.getrandbits(24)


class AccountStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.ForeignKey("customer.id"), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=False)
    code = db.Column(db.String(length=100), nullable=False, default=Utils.random_numbers)

    def __init__(self, user):
        self.user = user


class AccountStatusSchema(ma.Schema):
    class Meta:
        fields = ("id", "user", "active", "code")


class Phrase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phrase = db.Column(db.String(length=250), unique=True)
    use_teller = db.Column(db.Boolean, default=True)
    date_added = db.Column(db.DateTime, default=datetime.now)
    active = db.Column(db.Boolean, default=True)

    def __init__(self, phrase, use_teller):
        self.phrase = phrase
        self.use_teller = use_teller


class PhraseSchema(ma.Schema):
    class Meta:
        fields = ("id", "name", "phrase", "date_added", "active", "use_teller")


class ResetOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String(length=250), unique=midnight)
    branch = db.ForeignKey("branch.key_", nullable=False, unique=True)
    date_added = db.Column(db.DateTime, default=datetime.now)
    active = db.Column(db.Boolean, default=True)

    def __init__(self, time, option):
        self.time = time
        self.active = option


class ResetOptionSchema(ma.Schema):
    class Meta:
        fields = ("id", "time", "branch", "date_added", "active")


class Department(db.Model):
    """
    FOR Teller, ServiceOffered, Icon
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(length=250), unique=midnight)
    branch = db.ForeignKey("branch.key_", nullable=False, unique=True)
    date_added = db.Column(db.DateTime, default=datetime.now)
    active = db.Column(db.Boolean, default=True)
    unique_id = db.Column(db.String(250), default=unique_code, unique=True)


    def __init__(self, name, branch):
        self.name = name
        self.branch = branch


class DepartmentSchema(ma.Schema):
    class Meta:
        fields = ("id", "name", "branch", "date_added", "active", "unique_id")

