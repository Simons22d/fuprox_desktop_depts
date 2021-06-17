# from logging import exception
import json
import logging
import random
import secrets
import time
from datetime import datetime

import pyttsx3
import requests
import socketio
import sqlalchemy
from flask import request, jsonify, render_template
# working with voice
from pygame import mixer
from sqlalchemy.dialects import mysql
from datetime import datetime

from fuprox import app
# from fuprox.models.booking import (Payments, PaymentSchema, CustomerSchema, Customer, Booking)
from fuprox.others.payments import (authenticate, stk_push)
# noinspection PyInterpreter
from fuprox.others.utility import (create_service, get_branch_services, create_booking,
                                   generate_ticket, get_bookings, get_next_ticket_by_date, service_exists, add_teller,
                                   verify_ticket, upload,
                                   get_branch_icons, branch_activate, branch_verify, branch_is_valid, get_branch_by_key,
                                   get_company_by_id, get_allbooking, get_online_booking, get_offline_booking,
                                   send_mail, check_teller_service, get_instant_ticket,
                                   get_active_ticket, get_next_instant_service_ticket_by_date,
                                   ticket_queue, get_last_ticket, make_active, forward_ticket, close_ticket,
                                   get_active_ticket_now, get_next_ticket, get_all_tellers, get_upcoming, wait_time,
                                   branch_is_medical, user_exists, add_customer, get_branch_tellers,
                                   get_active_tickets, booking_exists, save_icon_to_service,
                                   sync_branch_data, get_active_tickets_no_limit,
                                   get_comments, teller_exists, sync_category, sync_company,
                                   get_online_by_key,
                                   ticket_data, ahead_of_you_id, upload_video, get_single_video,
                                   get_all_videos, toggle_status, get_active_videos, upload_link, validate_link,
                                   charge_, get_issue_count, delete_branch_by_key, charge, delete_video,
                                   reset_ticket_counter,
                                   create_booking_online, booking_exists_by_unique_id, log, get_sync_all_data,
                                   ack_teller_success, ack_booking_success, ack_service_success,
                                   is_this_branch, service_exists_unique, booking_exists_unique, teller_exists_unique,
                                   get_all_unsyced_bookings, branch_exists_key, booking_by_unique, branch_exists_id,
                                   sync_2_offline, forward_ticket_with_requirement, this_branch, teller_bookings,
                                   offline_verify, is_my_branch, last_five_booking_dates, avg_time)
from ..models.models import Booking, BookingSchema, ServiceOffered, Teller, TellerSchema, ServiceOfferedSchema

import webbrowser

# charge

link = "http://localhost:1000"
# online socket link
# socket_link = "http://localhost:5000/"
local_sockets = "http://localhost:5500/"
socket_link = "http://159.65.144.235:5000/"

#
# standard Python
sio = socketio.Client()
sio_local = socketio.Client()

booking_schema = BookingSchema()
bookings_schema = BookingSchema(many=True)

tellers_schema = TellerSchema(many=True)
services_schema = ServiceOfferedSchema(many=True)


@app.route("/open/portal", methods=["POST"])
def portal():
    server_addr = request.json["server_addr"]
    evt = webbrowser.open(f"http://{server_addr}:9000")
    return {"msg": evt}


@app.route("/b/s", methods=["POST"])
def bookings():
    service = request.json["service"]
    bookings = last_five_booking_dates(service)
    return jsonify({"res": bookings})


@app.route("/b/s/avg", methods=["POST"])
def avg_booking_time():
    service = request.json["service"]
    time = avg_time(service)
    return jsonify({"avg": time})


# getting booking data
@app.route("/upload", methods=["POST", "GET", "PUT"])
def upload_video__():
    return render_template("upload.html")


# getting booking data
@app.route("/booking/make", methods=["POST"])
def make_booking():
    service_name = request.json["service_name"]
    start = datetime.now()
    branch_id = request.json["branch_id"]
    is_instant = bool(request.json["is_instant"])
    if not request.json["user_id"] == 0:
        user_ = request.json["user_id"]
        booking = create_booking(service_name, start, branch_id, is_instant, int(user_))
        if booking:
            final = generate_ticket(booking["id"])
        else:
            final = {"msg": "Error generating the ticket. UserNot Found."}
    else:
        user_ = 0
        booking = create_booking(service_name, start, branch_id, is_instant, int(user_))
        if booking:
            final = generate_ticket(booking["id"])
        else:
            final = {"msg": "Error generating the ticket. User Not Found."}
    sio.emit("online_", {"booking_data": booking})
    return final


@app.route("/service/make", methods=["POST"])
def make_service():
    name = request.json["name"]
    teller = request.json["teller"]
    branch_id = request.json["branch_id"]
    code = request.json["code"]
    icon = request.json["icon_id"]
    visible = request.json["visible"]

    # service emit service made
    final = create_service(name, teller, branch_id, code, icon, visible)
    sio.emit("sync_service", final)
    return final


@app.route("/ticket/forward", methods=["POST"])
def fward_ticket():
    teller_to = request.json["teller_to"]
    teller_from = request.json["teller_from"]
    branch_id = request.json["branch_id"]
    mandatory = request.json["mandatory"]
    comment = request.json["comment"]
    print("forward data >>", teller_to, teller_from, mandatory)
    data = forward_ticket(teller_from, teller_to, branch_id, comment, mandatory)
    if data:
        sio.emit("update_teller", data)
    return data


@app.route("/ticket/forward/withrequirements", methods=["POST"])
def fward_ticket_():
    teller_to = request.json["teller_to"]
    teller_from = request.json["teller_from"]
    branch_id = request.json["branch_id"]
    comment = request.json["comment"]
    requirement = request.json["requirement"]
    data = forward_ticket_with_requirement(teller_from, teller_to, branch_id, comment, requirement)
    if data:
        # update the booking table with the new data
        sio.emit("update_teller", data)
    return data


'''
get the branch name is javascript and add to a field
'''


@app.route('/service/icon/upload', methods=['POST'])
def upload_file():
    # print(request.data)
    return upload()


@app.route("/app/activate", methods=["GET", "POST"])
def activate_offline():
    return jsonify(this_branch())


@app.route('/service/icon', methods=['POST'])
def upload_file_():
    icon = request.json["icon"]
    name = request.json["name"]
    branch_id = request.json["branch_id"]
    current = save_icon_to_service(icon, name, branch_id)
    return current


@app.route("/services/branch/get", methods=["POST"])
def get_all():
    try:
        branch_id = request.json["branch_id"]
        data = get_branch_services(branch_id)
    except Exception:
        data= []
    return jsonify(data)


@app.route("/sync/online/branch", methods=["POST"])
def add_branch():
    name = request.json["name"]
    company = request.json["company"]
    longitude = request.json["longitude"]
    latitude = request.json["latitude"]
    opens = request.json["opens"]
    closes = request.json["closes"]
    service = request.json["service"]
    description = request.json["description"]
    key_ = request.json["key_"]
    unique_id = request.json["unique_id"]
    return sync_branch_data(name, company, longitude, latitude, opens, closes, service, description, key_, unique_id)


@app.route("/sync/online/company", methods=["POST"])
def sync_company_():
    logging.debug("Company synced.")
    name = request.json["name"]
    service = request.json["service"]
    return sync_company(name, service)


@app.route("/sync/online/booking", methods=["POST"])
def sync_bookings():
    service_name = request.json["service_name"]
    start = request.json["start"]
    branch_id = request.json["branch_id"]
    is_instant = request.json["is_instant"]
    user = request.json["user"]
    ticket = request.json["ticket"]
    key = request.json["key"]
    is_synced = True if int(user) != 0 else False
    unique_id = request.json["unique_id"]
    verify = request.json["verify"]
    final = dict()
    if not booking_exists_by_unique_id(unique_id):
        final = dict()
        try:
            try:
                final = create_booking_online(service_name, start, branch_id, is_instant, user, kind=ticket, key=key,
                                              unique_id=unique_id, is_synced=is_synced, verify="")
                sio_local.emit("online_booking", "")
                if final:
                    ack_successful_entity("BOOKING", final)
                    log(f"Booking synced + {unique_id}")
                else:
                    ack_failed_entity("BOOKING", {"unique_id": unique_id})
                    log(f"Booking exists - {unique_id}")
            except ValueError as err:
                log(err)
        except sqlalchemy.exc.IntegrityError:
            ack_successful_entity("BOOKING", {"unique_id": unique_id})
    else:
        ack_successful_entity("BOOKING", {"unique_id": unique_id})
        final = {"msg": "booking exists"}
    return final


@app.route('/sync/online/category', methods=["POST"])
def sync_category_():
    logging.debug("branch sync")
    name = request.json["name"]
    service = request.json["service"]
    is_medical = request.json["is_medical"]
    return sync_category(name, service, is_medical)


@app.route("/ticket/service", methods=["POST"])
def ticket_next():
    teller = request.json["teller_id"]
    branch_id = request.json["branch_id"]
    return make_active(teller, branch_id)


@app.route("/ticket/close", methods=['POST'])
def close_ticket_():
    teller_number = request.json["teller_id"]
    comment = request.json["comment"]
    # here we are going to emit an event to close use issue
    data = close_ticket(teller_number, comment)
    if data:
        sio.emit("update_ticket", data)
    return data


@app.route("/ticket/next/get", methods=["POST"])
def next_ticket():
    service_name = request.json["service_name"]
    branch_id_ = request.json["branch_id"]
    return get_next_ticket(service_name, branch_id_)


@app.route("/ticket/last/get", methods=["POST"])
def last_booking():
    service_name = request.json["service_name"]
    return get_last_ticket(service_name)


@app.route("/ticket/next/by/date", methods=["POST"])
def next_by_date():
    service_name = request.json["service_name"]
    return get_next_ticket_by_date(service_name)


@app.route("/booking/get")
def get_booking():
    return get_bookings()


@app.route("/booking/get/active", methods=["POST"])
def active_ticket():
    service_name = request.json["service_name"]
    return get_active_ticket(service_name)


@app.route("/service/exists", methods=["POST"])
def app_exists():
    name = request.json["service_name"]
    branch_id = request.json["branch_id"]
    return service_exists(name, branch_id)


@app.route("/verify/ticket", methods=["POST"])
def verify():
    booking_id = request.json["code"]
    return verify_ticket(booking_id)


@app.route("/teller/bookings", methods=["POST"])
def teller_bookings_():
    teller = request.json["teller"]
    bookings = teller_bookings(teller)
    return jsonify(bookings)


@app.route("/teller/add", methods=["POST"])
def add_teller_():
    teller_number = request.json["teller_number"]
    branch_id = request.json["branch_id"]
    service_name = request.json["service_name"]
    try:
        branch = branch_exists_id(branch_id)
        final = add_teller(teller_number, branch_id, service_name, branch.unique_id)
        sio.emit("add_teller", {"teller_data": final})
    except mysql.connector.errors.IntegrityError:
        print("error! teller exists")
    return final


@app.route("/service/icons/get", methods=["POST"])
def get_icons():
    try:
        branch_id = request.json["branch_id"]
        data = get_branch_icons(branch_id)
    except Exception:
        data = []
    return jsonify(data)


@app.route("/verify/branch", methods=["POST"])
def verify_branch():
    # here we are going to pass a branch id and
    branch_id = request.json["branch_id"]
    branch = branch_verify(branch_id)
    if branch:
        final = {"status": True, "msg": branch}
    else:
        final = {"status": None, }
    return final


@app.route("/branch/is/valid", methods=["POST"])
def branch_valid():
    branch_id = request.json["branch_id"]
    return branch_is_valid(branch_id)


@app.route("/branch/activate", methods=["POST"])
def activate_branch():
    branch_id = request.json["branch_id"]
    expires = request.json["expires"]
    return branch_activate(branch_id, expires)


@app.route("/branch/by/key", methods=["POST"])
def branch_by_key():
    key = request.json["key"]
    branch = get_branch_by_key(key)
    """
    We need a trigger for verify key for the application
    """
    if branch:
        final = {"status": True, "msg": branch}
    else:
        final = {"status": False, "msg": None}
    return final


@app.route("/company/by/id", methods=["POST"])
def company_from_branchid():
    company_id = request.json["id"]
    return get_company_by_id(company_id)


@app.route("/customer/online/booking", methods=["POST"])
def online_bookings():
    branch_id = request.json["branch_id"]
    service_name = request.json['service_name']
    return jsonify(get_online_booking(branch_id, service_name))


@app.route("/customer/local/booking", methods=["POST"])
def local_booking():
    branch_id = request.json["branch_id"]
    service_name = request.json['service_name']
    return jsonify(get_offline_booking(branch_id, service_name))


@app.route("/booking/get/all", methods=["POST"])
def get_all_bookings():
    branch_id = request.json['branch_id']
    service_name = request.json['service_name']
    return jsonify(get_allbooking(branch_id, service_name))


@app.route("/sendemail", methods=["POST"])
def send_email():
    to = request.json["to"]
    subject = request.json["subject"]
    body = request.json["body"]
    return send_mail(to, subject, body)


@app.route("/get/last/booking", methods=["POST"])
def get_last_booking():
    service_name = request.json["service_name"]
    return jsonify(get_last_ticket(service_name))


@app.route("/check/teller/service", methods=["POST"])
def check_service():
    teller = request.json["teller"]
    service_name = request.json["service"]
    return jsonify(check_teller_service(teller, service_name))


@app.route("/check/instant/status", methods=["POST"])
def check_instant():
    service = request.json["service"]
    free_teller = request.json["teller"]
    return jsonify(get_instant_ticket(service, free_teller))


@app.route("/get/services", methods=["POST"])
def get_services():
    teller = request.json["teller"]
    return jsonify(get_last_ticket(teller))


@app.route("/get/next/instant", methods=["POST"])
def get_next_instant():
    service_name = request.json["service_name"]
    return jsonify(get_next_instant_service_ticket_by_date(service_name))


@app.route("/get/last/ticket", methods=["POST"])
def lst_ticket():
    teller_number = request.json["teller_number"]
    return jsonify(get_last_ticket(teller_number))


@app.route("/last/ticket/queue", methods=["POST"])
def lst_queur():
    branch_id = request.json["branch_id"]
    service_name = request.json["service_name"]
    return jsonify(ticket_queue(service_name, branch_id))


'''
teller app
'''


@app.route("/get/active/ticket", methods=["POST"])
def get_active_tckt():
    try:
       teller_number = request.json["teller_id"]
       branch_id = request.json["branch_id"]
       data = get_active_ticket_now(teller_number, branch_id)
    except Exception:
       data = {}
    return jsonify(data)


@app.route("/callout", methods=["POST"])
def caller():
    try:
        mixer.init()
        mixer.music.load('sounds/notification.mp3')
        mixer.music.play()
        time.sleep(0.5)
        phrase = request.json["phrase"]
        log(phrase)
        engine = pyttsx3.init()
        import platform
        platform = platform.system()
        if platform == "Windows":
            engine.setProperty('rate', 130)
        else:
            engine.setProperty('rate', 180)
        engine.setProperty('volume', 1.0)
        engine.say(phrase)
        engine.runAndWait()
    except RuntimeError:
        pass
    return {"code": secrets.token_hex()}


@app.route("/get/next/ticket", methods={"POST"})
def get_next_ticket_():
    try:
        teller_id = request.json["teller_id"]
        branch_id = request.json["branch_id"]
        data = get_next_ticket(teller_id, branch_id)
    except Exception:
        data = {}
    return jsonify(data)


@app.route("/get/upcoming/tickets", methods=["POST"])
def get_nxt_tckt():
    try:
        teller_id = request.json["teller_id"]
        branch_id = request.json["branch_id"]
        data = get_upcoming(teller_id, branch_id)
    except Exception:
        data = {}
    return jsonify(data)


@app.route("/tellers/get/all", methods=["POST"])
def all_tellers():
    try :
        branch_id = request.json["branch_id"]
        data = get_all_tellers(branch_id)
    except Exception:
        data = []
    return jsonify(data)


''' payments for quick integration'''


@app.route("/service/pay", methods=["POST"])
def payments():
    phonenumber = request.json["phone"]
    token_data = authenticate()
    token = json.loads(token_data)["access_token"]
    business_shortcode = "174379"
    lipa_na_mpesapasskey = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
    amount = 10
    party_b = business_shortcode
    callback_url = "http://68.183.89.127:8080/mpesa/b2c/v1"
    response = stk_push(token, business_shortcode, lipa_na_mpesapasskey, amount, phonenumber, party_b, phonenumber,
                        callback_url)
    if response:
        final = {"msg": "Success. Request pushed to customer"}
    else:
        final = {"msg": None}
    return jsonify(final)


# @app.route("/payments/status", methods=["POST"])
# def payment_res():
#     data = request.json["payment_info"]
#     lookup = Payments(data)
#     db.session.add(lookup)
#     db.session.commit()
#     
#     return payment_schema.jsonify(lookup)
#

# @app.route("/payments/user/status", methods=["POST"])
# def payment_user_status():
#     data = request.json["phone"]
#     lookup = Payments(data)
#     db.session.add(lookup)
#     db.session.commit()
#     
#     return payment_schema.jsonify(lookup)


@app.route("/validate/link", methods=["POST"])
def validate():
    link = request.json["link"]
    return validate_link(link)


@app.route("/people/ahead", methods=["POST"])
def ahead():
    booking_id = request.json["booking_id"]
    return ahead_of_you_id(booking_id)


@app.route("/time/to/wait", methods=["POST"])
def time_to_wait():
    service_name = request.json["service_name"]
    branch_id = request.json["branch_id"]
    return jsonify(wait_time(service_name, branch_id))


@app.route("/ismed", methods=["POST"])
def is_med():
    branch_id = request.json["branch_id"]
    return jsonify(branch_is_medical(branch_id))


@app.route("/user/exists", methods=["POST"])
def is_user():
    user = request.json["user_id"]
    return user_exists(user)


@app.route("/add/customer", methods=["POST"])
def user():
    email = request.json["email"]
    return add_customer(email)


@app.route("/card/payment", methods=["POST"])
def card_payment_():
    card_number = request.json["card_number"]
    expiration_date = request.json["expiration_date"]
    amount = request.json["amount"]
    merchant_id = "Fuprox-noqueue"
    return charge(card_number, expiration_date, amount, merchant_id)


@app.route("/card/payment/2", methods=["POST"])
def card_payment_2():
    return charge_()


# we are going to get the ticket data
@app.route("/get/ticket/data", methods=['POST'])
def get_ticket_data():
    try:
        booking_id = request.json["booking_id"]
        key = request.json["key"]
    except KeyError:
        pass
    return ticket_data(key, booking_id)


@app.route("/get/branch/tellers/", methods=["POST"])
def branch_tellers():
    branch_id = request.json["branch_id"]
    return jsonify(get_branch_tellers(branch_id))


@app.route('/get/active/tickets', methods=["POST"])
def active_booking():
    branch_id = request.json["branch_id"]
    tickets = get_active_tickets(branch_id)
    return jsonify(tickets)


@app.route("/get/active/tickets/side", methods=["POST"])
def active_booking_side():
    branch_id = request.json["branch_id"]
    tickets = get_active_tickets_no_limit(branch_id)
    return jsonify(tickets)


'''method to sync bookings, tellers and service offered '''
''' compare off line and online data a update on either side >> socket s updating '''


# @app.route("/sync/online/add/users", methods=["POST"])
# def sync_online_users():
#     data = request.json["user_data"]
#     email = data["email"]
#     password = data["password"]
#     # get user data
#     lookup = Customer.query.filter_by(email=email).first()
#     user_data = user_schema.dump(lookup)
#     if not user_data:
#         # hashing the password
#         try:
#             hashed_password = bcrypt.generate_password_hash(password)
#             user = Customer(email, hashed_password)
#             db.session.add(user)
#             db.session.commit()
#             
#             data = user_schema.dump(user)
#         except sqlalchemy.exc.IntegrityError:
#             print("Error! Could not add Users.")
#     else:
#         data = {
#             "user": None,
#             "msg": "User with that email Exists."
#         }
#     return data
@app.route("/booking/exists", methods=["POST"])
def book_exists_():
    branch_id = request.json["branch_id"]
    service_name = request.json["service_name"]
    ticket = request.json["ticket"]
    if booking_exists(branch_id, service_name, ticket):
        final = {"msg": "booking Exists"}
    else:
        final = {"msg": None}
    return final


@app.route("/get/comments", methods=["POST"])
def get_comments_():
    issue_id = request.json["issue_id"]
    return jsonify(get_comments(issue_id))


@app.route("/teller/exists", methods=["POST"])
def teller_exists_():
    teller = request.json["teller"]
    return teller_exists(teller)


'''working with ticket reset'''


@app.route("/reset/ticket/counter", methods=["POST"])
def reset_ticket():
    final = reset_ticket_counter()
    return final


@app.route("/ticket/reset", methods=["POST"])
def reset():
    code = {"code": random.getrandbits(69)}
    sio.emit("reset_tickets", code)
    return jsonify(code)


# :: uploading video
@app.route("/video/upload", methods=["POST"])
def upload_video_():
    return upload_video()


@app.route("/video/link", methods=["POST"])
def upload_link_():
    link_ = request.json["link"]
    type_ = request.json["type"]
    return upload_link(link_, type_)


# get single video
@app.route("/video/get/one", methods=["POST"])
def get_one_video_():
    id = request.json["id"]
    return get_single_video(id)


@app.route("/video/active", methods=["POST"])
def get_active():
    return get_active_videos()


@app.route("/video/get/all", methods=["POST"])
def get_all_videos_():
    return get_all_videos()


@app.route("/video/toggle", methods=["POST"])
def activate_video():
    id = request.json["id"]
    return toggle_status(id)


@app.route("/video/delete", methods=["POST"])
def video_delete():
    vid_id = request.json["id"]
    return jsonify(delete_video(vid_id))


@app.route("/issue/count", methods=["POST"])
def get_issue_count_():
    return get_issue_count()


@app.route("/socket", methods=["POST"])
def test_skt():
    sio_local.emit("hello", {})
    return jsonify({})


'''
------------------------------------------
SOCKETS
create-payment-intent >>> /card/payment
'''


@sio.event
def connect():
    log('online connection established')


@sio.event
def disconnect():
    log('online disconnected from server')


@sio.on('sync_online_user_data')
def on_message(data):
    requests.post(f"{link}/sync/online/add/users", json=data)


@sio.on('online_data')
def on_message(data):
    if data:
        requests.post(f"{link}/sync/online/booking", json=data)


# current booking status
@sio.on('offline_booking_status_to_online')
def on_message(data):
    if data:
        requests.post(f"{link}/sync/online/booking", json=data)


@sio.on("branch_data")
def branch_data(data):
    if data:
        final = {
            "name": data['name'],
            "company": data["company"],
            "longitude": data["longitude"],
            "latitude": data["latitude"],
            "opens": data["opens"],
            "closes": data["closes"],
            "service": data["service"],
            "description": data["description"],
            "key_": data["key_"],
            "unique_id": data["unique_id"]
        }
    requests.post(f"{link}/sync/online/branch", json=final)


@sio.on("branch_data_edit")
def branch_data_edit(data):
    requests.post(f"{link}/branch/online/edit", json=data)


"""
::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
:::::::::::::: working sync of online_offline data :::::::::::::::::
::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
"""


@sio.on("booking_resync_new_data")
def bookings_from_online(data):
    if is_my_branch(data["key"]):
        sycn_online_bookings(data["bookings"], data["key"])


@app.route("/branch/exists", methods=["POST"])
def mths():
    key = request.json["key"]
    branch = branch_exists_key(key)
    print(branch.key_)
    return dict()


# offline_online
@app.route("/sync/offline/services", methods=["POST"])
def sync_services():
    name = request.json["name"]
    teller = request.json["teller"]
    branch_id = request.json["branch_id"]
    code = request.json["code"]
    icon_id = request.json["icon"]
    key = request.json["key"]
    service = None
    try:
        key_data = get_online_by_key(key)
        if key_data:
            service = create_service(name, teller, key_data["id"], code, icon_id)
    except sqlalchemy.exc.IntegrityError:
        print("Error! Could not create service.")
    return service_schema.jsonify(service)


"""
this is the __init__ method that glues that start the sync
"""

"""
we need a mulitprocessing capabiilty to trigger thin on give time in seconds
"""


@app.route("/unsynced/bookings", methods=['POST'])
def get_all_unsyced_bookings_():
    return jsonify(get_all_unsyced_bookings())


def bookings_info():
    bookings = Booking.query.all()
    serviced = 0
    synced = 0;
    forwarded = 0
    all = len(bookings)
    for booking in bookings:
        if booking.serviced:
            serviced = serviced + 1
        if booking.is_synced:
            synced = synced + 1
        if booking.forwarded:
            forwarded = forwarded + 1
    return {"serviced": serviced, "synced": synced, "forwarded": forwarded, "all": all, "bookings":
        bookings_schema.dump(bookings)}


def tellers_info():
    tellers = Teller.query.all()
    synced = 0
    all = len(tellers)
    for teller in tellers:
        if teller.is_synced:
            synced = synced + 1
    return {"synced": synced, "all": all, "tellers": tellers_schema.dump(tellers)}


def services_info():
    services = ServiceOffered.query.all()
    synced = 0
    all = len(services)

    for service in services:
        if service.is_synced:
            synced = synced + 1
    return {'all': all, "synced": synced, "services": services_schema.dump(services)}


@app.route("/sync/init", methods=["POST"])
def sync_all_():
    key = request.json["key"]
    # get booking counts
    bookings = bookings_info()
    tellers = tellers_info()
    services = services_info()
    final = {
        "bookings": bookings,
        "tellers": tellers,
        "services": services,
        "key": key
    }
    sio.emit("all_sync_offline", final)
    return jsonify(final)

    # old data
    # # make sure the branch exists
    # if get_branch_by_key(key):
    #     data = get_sync_all_data(key)
    #     sio.emit("all_sync_offline", data)
    # else:
    #     data = {
    #         "Error": "Branch Key error."
    #     }
    # # we have been hit
    # return data


# socket connections
@sio_local.event
def connect():
    log('Local Socket Connected')


@sio_local.event
def disconnect():
    log('Local Socket connected')


@app.route('/booking/to/sync', methods=["POST"])
def to_post():
    return jsonify(get_all_unsyced_bookings())


# --------------------
# data from online
# --------------------
# :::::::::::::::: END

@sio.on("category_data")
def category_data(data):
    requests.post(f"{link}/sync/online/category", json=data)


@sio.on("company_data")
def company_data(data):
    requests.post(f"{link}/sync/online/company", json=data)


@sio.on("key_response_data")
def key_response_data_(data):
    # delete the current entry and sync the new entry
    if delete_branch_by_key(data["key_"]):
        # create a new branch
        requests.post(f"{link}/sync/online/branch", json=data)


# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


def ack_teller_fail(data):
    # check if it exists -> if true -> flag as synced if not { inform user of synced }  -> else trigger a sync
    teller = teller_exists_unique(data["data"]["unique_id"])
    if teller:
        if teller["is_synced"]:
            # teller is synced
            log("Teller Already Synced")
        else:
            # teller does not exists
            # trigger async
            sio.emit("add_teller", {"teller_data": data["data"]})


def ack_booking_fail(data):
    # check if it exists -> if true -> flag as synced if not { inform user of synced }  -> else trigger a sync
    booking = booking_exists_unique(data["data"]["unique_id"])
    if booking:
        if booking["is_synced"]:
            # booking is synced
            log("Booking Already Synced")
        else:
            # booking is not synced
            # trigger async
            sio.emit("online_", {"booking_data": data["data"]})


def ack_service_fail(data):
    # check if it exists -> if true -> flag as synced if not { inform user of synced }  -> else trigger a sync

    service = service_exists_unique(data["data"]["unique_id"])
    if service:
        if service["is_synced"]:
            log("Service Already Synced")
        else:
            sio.emit("sync_service", data["data"])


# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# ack_successful_enitity_data
# get the category
# flag as synced 202

ack_mapper_success = {
    "SERVICE": ack_service_success,
    "TELLER": ack_teller_success,
    "BOOKING": ack_booking_success
}

ack_mapper_fail = {
    "SERVICE": ack_service_fail,
    "TELLER": ack_teller_fail,
    "BOOKING": ack_booking_fail
}


@sio.on("ack_successful_enitity_data")
def ack_successful_enitity_data_(data):
    ack_mapper_success[data["category"]](data["data"])


# ack_failed_enitity_data
@sio.on("ack_failed_enitity_data")
def ack_failed_enitity_data_(data):
    log(f"ack_failed_enitity {data}")
    ack_mapper_fail[data["category"]](data["data"])


def ack_successful_entity(name, data):
    sio.emit("ack_successful_enitity_online", {"category": name, "data": data})
    return data


def ack_failed_entity(name, data):
    log(f"ack failed hit {data['unique_id']}")
    sio.emit("ack_failed_enitity_online", {"category": name, "data": data})
    return data


def sycn_online_bookings(data, key):
    # data = data["bookings"]
    for item in data:
        service_name = item["service_name"]
        start = item["start"]
        branch_id = item["branch_id"]
        is_instant = item["is_instant"]
        user = item["user"]
        ticket = item["ticket"]
        is_synced = True if int(user) != 0 else False
        unique_id = item["unique_id"]
        verify = item["verify"]
        final = dict()
        if not booking_exists_by_unique_id(unique_id):
            final = dict()
            try:
                try:
                    final = create_booking_online(service_name, start, branch_id, is_instant, user,
                                                  kind=ticket, key=key,
                                                  unique_id=unique_id, is_synced=is_synced, verify="")
                    sio_local.emit("online_booking", "")
                    # needs proper ref
                    if final:
                        ack_successful_entity("BOOKING", final)
                        log(f"Booking synced + {unique_id}")
                    else:
                        ack_failed_entity("BOOKING", {"unique_id": unique_id})
                        log(f"Booking exists - {unique_id}")
                except ValueError as err:
                    log(err)
            except sqlalchemy.exc.IntegrityError:
                ack_successful_entity("BOOKING", {"unique_id": unique_id})
        else:
            #  we cannot copy  existing booking from online as these  should already be updated from
            # the local setup
            ack_successful_entity("BOOKING", {"unique_id": unique_id})
            final = {"msg": "booking exists"}
        return final


@sio.on("reset_ticket_request")
def reset_tickets_listener(data):
    return requests.post(f"{link}/reset/ticket/counter", json=data)


# booking_update_data
@sio.on("booking_update_data")
def reset_tickets_listener(data):
    #  here we are going to get a unique id
    if data:
        booking = booking_by_unique(data)
        sio.emit("booking_resync", booking)
        log(f"Booking Resync Hit -> {data}")


@sio.event
def disconnect():
    log('disconnected from online server')


try:
    sio.connect(socket_link)
except socketio.exceptions.ConnectionError as a:
    log(f"[online] -> {a}")

try:
    sio_local.connect(local_sockets)
except socketio.exceptions.ConnectionError as a:
    log(f"[offline] -> {a}")
