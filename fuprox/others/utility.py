import base64
import logging
import os
import re
import secrets
import smtplib
import ssl
from datetime import datetime
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from operator import itemgetter

import requests
import sqlalchemy
from flask import jsonify, request, flash
# exceptions
from globalpayments.api import ServicesConfig, ServicesContainer
from globalpayments.api.entities import (Customer)
from globalpayments.api.entities.exceptions import (ApiException)
from globalpayments.api.payment_methods import (CreditCardData)
from requests.auth import HTTPBasicAuth
from sqlalchemy import desc, asc
from werkzeug.utils import secure_filename
from dateutil import parser

from fuprox import app
from fuprox import db
from fuprox.models.models import (Booking, BookingSchema, ServiceOffered, ServiceOfferedSchema,
                                  Branch, BranchSchema, Teller, TellerSchema, TellerBooking, TellerBookingSchema,
                                  OnlineBooking, OnlineBookingSchema, Icon, IconSchema, Company, CompanySchema,
                                  Service, ServiceSchema, Customer, CustomerSchema, BookingTimes,
                                  BookingTimesSchema, Video, VideoSchema, Phrase, PhraseSchema, DepartmentServiceSchema,
                                  Department, DepartmentService, DepartmentSchema)

# end

logger = logging.getLogger('authorizenet.sdk')
handler = logging.FileHandler('anetSdk.log')
formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
logger.debug('Logger set up for Authorizenet Python SDK complete')

# logging.basicConfig(filename='fuprox_desktop.log', filemode='a', format='%(name)s - %(levelname)s - %(message)s')

# from authorizenet.apicontrollers import *


# ---------------------
# :::::::: MPESA ::::::
# ---------------------

consumer_key = "vK3FkmwDOHAcX8UPt1Ek0njU9iE5plHG"
consumer_secret = "vqB3jnDyqP1umewH"

# from  fuprox.others.voice import speech

booking_schema = BookingSchema()
bookings_schema = BookingSchema(many=True)

service_ = ServiceSchema()
service_s = ServiceSchema(many=True)

service_schema = ServiceOfferedSchema()
services_schema = ServiceOfferedSchema(many=True)

branch_schema = BranchSchema()
branches_schema = BranchSchema(many=True)

teller_schema = TellerSchema()
tellers_schema = TellerSchema(many=True)

teller_booking_schema = TellerBookingSchema()
teller_bookings_schema = TellerBookingSchema(many=True)

online_booking_schema = OnlineBookingSchema()
online_bookings_schema = OnlineBookingSchema(many=True)

icon_schema = IconSchema()
icons_schema = IconSchema(many=True)

company_schema = CompanySchema()
companies_schema = CompanySchema(many=True)

user_schema = CustomerSchema()
users_schema = CustomerSchema(many=True)

booking_time = BookingTimesSchema()
booking_times = BookingTimesSchema(many=True)

video_schema = VideoSchema()
videos_schema = VideoSchema(many=True)

department_schema = DepartmentSchema()
departments_schema = DepartmentSchema(many=True)

department_service_schema = DepartmentServiceSchema()
departments_service_schema = DepartmentServiceSchema(many=True)


def is_my_branch(key):
    branch = Branch.query.filter_by(key_=key).first()
    return branch


# @manage_session
def generate_ticket(booking_id):
    # get_ticket code
    booking = get_booking(booking_id)
    if booking:
        branch = branch_exist(booking['branch_id'])
        service = service_exists(booking["service_name"], booking["branch_id"])
        if branch and service:
            code = service["code"] + booking["ticket"]
            branch_name = branch["name"]
            company = branch["company"]
            service_name = service["name"]
            date_added = booking["start"]
            final = {"code": code, "branch": branch_name, "company": company, "service": service_name,
                     "date": date_added, "booking_id": booking_id}
        else:
            final = {"msg": "Details not Found"}
    else:
        final = {"msg": "Booking not Found"}
        # HERE WE ARE GOING TO ADD BOOKING INFO TO THE DATABASE bookingtimes
    return jsonify(final)


def get_next_instant_service_ticket_by_date(service_name):
    lookup = Booking.query.filter_by(service_name=service_name).filter_by(is_instant=True).filter_by(
        nxt=1001).filter_by(serviced=False). \
        order_by(Booking.date_added.asc()).first()
    booking_data = booking_schema.dump(lookup)
    return booking_data


def get_next_ticket_by_date(service_name):
    lookup = Booking.query.filter_by(service_name=service_name).order_by(asc(Booking.date_added)) \
        .filter(Booking.is_instant.isnot(True)).filter_by(nxt=1001).filter(Booking.serviced.isnot(True)).first()
    booking_data = booking_schema.dump(lookup)
    return booking_data


def teller_has_many_services(teller_number):
    """
    :param teller_number:
    :return:
    """
    teller_lookup = Teller.query.filter_by(number=teller_number).first()
    teller_data = teller_schema.dump(teller_lookup)
    final = ""
    if teller_data:
        # check if teller has more than one service
        services = teller_data["service"].split(",")
        if len(services) > 1:
            # teller has many services
            final = True
        else:
            final = False
    return final


def get_teller_services(teller_number):
    teller_lookup = Teller.query.filter_by(number=teller_number).first()
    teller_data = teller_schema.dump(teller_lookup)
    final = ""
    if teller_data:
        # check if teller has more than one service
        services = teller_data['service'].split(",")
        if len(services) > 1:
            # teller has many services
            final = services
        else:
            final = services
    return final


def ticket_queue(service_name, branch_id):
    lookup = Booking.query.filter_by(service_name=service_name).filter_by(branch_id=branch_id).order_by(
        desc(Booking.date_added)).filter_by(nxt=1001).first()
    booking_data = booking_schema.dump(lookup)
    return booking_data


'''NEEDS FIXED FOR MULITPLE COUNTER SINGLE SERVICE'''


def get_last_ticket(teller_number):
    """
    :param teller_number:
    :return:
    """
    # get the services offered by that teller
    # get all the services that are not active
    # order by date in a descending manner and get the last one
    inst_service = list()
    normal_service = list()
    if teller_has_many_services(teller_number):
        # get teller services
        teller_services = get_teller_services(teller_number)
        # make a query that get the serviecs with both the services defined
        for service in teller_services:
            inst_service.append(get_next_instant_service_ticket_by_date(service)) if \
                get_next_instant_service_ticket_by_date(service) else ""
            normal_service.append(get_next_ticket_by_date(service)) if get_next_ticket_by_date(service) else ""
    else:
        teller_services = get_teller_services(teller_number)
        if teller_services:
            inst_service = get_next_instant_service_ticket_by_date(teller_services[0])
            normal_service = get_next_ticket_by_date(teller_services[0])
    final = inst_service if inst_service else normal_service
    return final


'''
    # booking does not exist
    # table -> [booking status]
    # teller -> number which it is serveing_it
    # if closed the serviced -> true
    # if not clsed then it should be fowarded

    # table -> [teller booking]
    # any entry forwarding entries shall have an empty entry
    # if not closed and active then it should be unser service
'''


def is_kickback(this_teller, teller_to):
    print(this_teller, teller_to)
    return int(this_teller) == int(teller_to)


def unique_teller_code(id):
    teller = Teller.query.filter_by(number=id).first()
    log(teller)
    return teller.unique_id


def forward_ticket(this_teller, teller_to, branch_id, remarks, mandatory):
    # booking exists
    # get this tellers data current teller
    # update with and is
    # on checking how many in queue get he current forwarded and the has tellet assigned to a service
    booking_lookup = Booking.query.filter_by(teller=this_teller).filter_by(active=True).filter_by(
        serviced=False).filter_by(branch_id=branch_id).first()
    booking_data = booking_schema.dump(booking_lookup)
    final = dict()

    # get teller data
    # for mapping the teller unique to the forwarded ticket of online counting
    #  checking if there is an active ticket in that teller
    teller_lookup = Teller.query.filter_by(number=teller_to).first()
    if booking_data and teller_lookup:
        current_teller = booking_data["teller"]
        if booking_data["forwarded"]:
            '''ticket that has been forwareded before'''
            if mandatory:
                log("111111")
                # get the current booking info [prev ticket booking]
                current_booking_info = TellerBooking.query.filter_by(booking_id=booking_data["id"]).order_by(
                    TellerBooking.date_added.desc()).first()
                current_booking_data = teller_booking_schema.dump(current_booking_info)

                if current_booking_data and mandatory:
                    current_booking_info.active = True
                    current_booking_info.pre_req = mandatory
                    db.session.commit()
                elif current_booking_data:
                    current_booking_info.active = False
                    db.session.commit()

                # updating the main booking table
                booking_lookup_update = Booking.query.get(booking_data["id"])
                booking_lookup_update.teller = mandatory
                booking_lookup_update.unique_teller = unique_teller_code(mandatory)
                booking_lookup_update.active = False

                if was_kick_back(booking_lookup_update):
                    booking_lookup_update.is_instant = False
                    booking_lookup_update.user = 0
                    booking_lookup_update.start = 99999998

                if is_kickback(this_teller, teller_to):
                    booking_lookup_update.start = 99999999
                else:
                    booking_lookup_update.start = 99999998
                # the forwading beleow igit s not required but is there to make sure as the ticket had been forwarded 
                # before
                booking_lookup_update.forwarded = True
                booking_lookup_update.unique_teller = teller_lookup.unique_id
                db.session.commit()

                # create new booking [basically fowarding the ticket]
                booking_teller = TellerBooking(teller_to, booking_data["id"], current_teller, remarks, True)
                if mandatory:
                    booking_teller.pre_req = mandatory

                db.session.add(booking_teller)
                db.session.commit()

                final = booking_schema.dump(booking_lookup_update)
            else:
                log("2222")
                # get the current booking info [prev ticket booking]
                current_booking_info = TellerBooking.query.filter_by(booking_id=booking_data["id"]).order_by(
                    TellerBooking.date_added.desc()).first()
                current_booking_data = teller_booking_schema.dump(current_booking_info)
                if current_booking_data and mandatory:
                    current_booking_info.active = True
                    current_booking_info.pre_req = 0
                    db.session.commit()
                elif current_booking_data:
                    current_booking_info.active = False
                    db.session.commit()
                # updating the main booking table
                # the forwading beleow is not required but is there to make sure as the ticket had been forwarded before
                booking_lookup_update = Booking.query.get(booking_data["id"])
                booking_lookup_update.teller = teller_to
                booking_lookup_update.unique_teller = unique_teller_code(teller_to)
                booking_lookup_update.active = False
                booking_lookup_update.forwarded = True
                booking_lookup_update.unique_teller = teller_lookup.unique_id

                if was_kick_back(booking_lookup_update):
                    booking_lookup_update.is_instant = False
                    booking_lookup_update.user = 0

                db.session.commit()

                # create new booking [basically fowarding the ticket]
                booking_teller = TellerBooking(teller_to, booking_data["id"], current_teller, remarks, True)
                if mandatory:
                    booking_teller.pre_req = mandatory
                db.session.add(booking_teller)
                db.session.commit()
                final = booking_schema.dump(booking_lookup_update)
        else:
            # forward issue as new
            # so set foward to true
            # get the current booking info [prev ticket booking]
            if mandatory:
                log("333333")

                current_booking_info = TellerBooking.query.filter_by(booking_id=booking_data["id"]).order_by(
                    TellerBooking.date_added.desc()).first()
                current_booking_data = teller_booking_schema.dump(current_booking_info)
                if current_booking_data and mandatory:
                    current_booking_info.active = True
                    current_booking_info.pre_req = mandatory
                    db.session.commit()
                elif current_booking_data:
                    current_booking_info.active = False
                    db.session.commit()

                # updating the main booking table
                booking_lookup_update = Booking.query.get(booking_data["id"])
                booking_lookup_update.teller = mandatory
                booking_lookup_update.active = False
                booking_lookup_update.forwarded = True
                booking_lookup_update.unique_teller = teller_lookup.unique_id

                if was_kick_back(booking_lookup_update):
                    booking_lookup_update.is_instant = False
                    booking_lookup_update.user = 0
                    booking_lookup_update.start = 99999998

                if is_kickback(this_teller, teller_to):
                    booking_lookup_update.start = 99999999
                    booking_lookup_update.user = 0
                else:
                    booking_lookup_update.start = 99999998

                db.session.commit()
                # create new booking [backically fowarding the ticket]
                booking_teller = TellerBooking(teller_to, booking_data["id"], current_teller, remarks, True)
                if mandatory:
                    booking_teller.pre_req = mandatory
                db.session.add(booking_teller)
                db.session.commit()
            else:
                log("444444")

                current_booking_info = TellerBooking.query.filter_by(booking_id=booking_data["id"]).order_by(
                    TellerBooking.date_added.desc()).first()
                current_booking_data = teller_booking_schema.dump(current_booking_info)
                log(current_booking_data)
                if current_booking_data and mandatory:
                    current_booking_info.active = True
                    current_booking_info.pre_req = 0
                    db.session.commit()
                elif current_booking_data:
                    current_booking_info.active = False
                    db.session.commit()

                # updating the main booking table
                booking_lookup_update = Booking.query.get(booking_data["id"])
                log(booking_lookup_update)
                booking_lookup_update.teller = teller_to
                booking_lookup_update.active = False
                booking_lookup_update.forwarded = True
                booking_lookup_update.unique_teller = teller_lookup.unique_id

                if was_kick_back(booking_lookup_update):
                    booking_lookup_update.is_instant = False
                    booking_lookup_update.user = 0
                db.session.commit()
                # create new booking [backically fowarding the ticket]
                booking_teller = TellerBooking(teller_to, booking_data["id"], current_teller, remarks, True)
                if mandatory:
                    booking_teller.pre_req = 0
                db.session.add(booking_teller)
                db.session.commit()
            final = booking_schema.dump(booking_lookup_update)
        if final:
            branch = Branch.query.get(int(branch_id))
            final.update({"key_": branch.key_})
    return final


def was_kick_back(booking):
    try:
        return int(booking.start) == 99999999
    except Exception:
        return False


def forward_ticket_with_requirement(this_teller, teller_to, branch_id, remarks, requirement):
    # booking exists
    #  get this tellers data current teller
    # update with and is
    # on checkin how many in queue get he current forwarded and the has tellet assigned to a service

    booking_lookup = Booking.query.filter_by(teller=this_teller).filter_by(nxt=1001).filter_by(active=True).filter_by(
        branch_id=branch_id).first()
    booking_data = booking_schema.dump(booking_lookup)
    final = dict()

    # get teller data
    # for mapping the teller unique to the forwarded ticket of online counting
    teller_lookup = Teller.query.filter_by(number=teller_to).first()
    if booking_data and teller_lookup:
        current_teller = booking_data["teller"]
        if booking_data["forwarded"]:
            '''ticket that has been forwareded before'''

            if int(booking_data["teller"]) == int(teller_to):
                # issue cannot be forwarded
                final = dict()

            else:
                # get the current booking info [prev ticket booking]
                current_booking_info = TellerBooking.query.filter_by(booking_id=booking_data["id"]).order_by(
                    TellerBooking.date_added.desc()).first()
                current_booking_data = teller_booking_schema.dump(current_booking_info)
                if current_booking_data:
                    current_booking_info.active = False
                    db.session.commit()

                # updating the main booking table
                booking_lookup_update = Booking.query.get(booking_data["id"])
                booking_lookup_update.teller = teller_to
                booking_lookup_update.active = False

                # the forwading beleow is not required but is there to make sure as the ticket had been forwarded before
                booking_lookup_update.forwarded = True
                booking_lookup_update.unique_teller = teller_lookup.unique_id
                db.session.commit()

                # create new booking [basically fowarding the ticket]
                booking_teller = TellerBooking(teller_to, booking_data["id"], current_teller, remarks, True)
                booking_teller.pre_req = requirement
                db.session.add(booking_teller)
                db.session.commit()

                final = booking_schema.dump(booking_lookup_update)
        else:
            # forward issue as new
            # so set foward to true
            # get the current booking info [prev ticket booking]
            current_booking_info = TellerBooking.query.filter_by(booking_id=booking_data["id"]).order_by(
                TellerBooking.date_added.desc()).first()
            current_booking_data = teller_booking_schema.dump(current_booking_info)
            if current_booking_data:
                current_booking_info.active = False
                db.session.commit()

            # updating the main booking table
            booking_lookup_update = Booking.query.get(booking_data["id"])
            booking_lookup_update.teller = teller_to
            booking_lookup_update.active = False
            booking_lookup_update.forwarded = True
            booking_lookup_update.unique_teller = teller_lookup.unique_id
            db.session.commit()

            # create new booking [backically fowarding the ticket]
            booking_teller = TellerBooking(teller_to, booking_data["id"], current_teller, remarks, True)
            booking_teller.pre_req = requirement
            db.session.add(booking_teller)
            db.session.commit()

            final = booking_schema.dump(booking_lookup_update)
        if final:
            branch = Branch.query.get(int(branch_id))
            final.update({"key_": branch.key_})
    return final


'''
teller booking the first booking
init teller_from with a zero as we do not not have any
also make the teller active by defualt as it is an assumption
for the calling in the user
——
Making active tickets
--

'''


def make_active(teller, branch_id_):
    exists = get_teller(teller, branch_id_)
    log(f"CCCCCC{teller}")
    final = dict()
    if exists:
        if branch_is_medical(exists["branch"]):
            # medical data goes here
            # non-mdeical data goes here
            branch_id = exists["branch"]
            teller_number = exists["number"]
            service_name = exists["service"]

            # active ticket
            lkp = Booking.query.filter_by(branch_id=branch_id).filter_by(serviced=False).filter_by(
                teller=teller_number).filter_by(active=True).first()
            lkp_data = booking_schema.dump(lkp)
            if not lkp_data:
                # kick back category
                # get the next instant ticket and make it active
                insant_nt_f_lookup_kickback = Booking.query.filter_by(branch_id=branch_id).filter_by(
                    forwarded=False).filter_by(serviced=False).filter_by(
                    is_instant=True).order_by(Booking.date_added.asc()).filter_by(nxt=1001).filter(
                    Booking.start == 99999999).first()
                instant_data_uplist_kickback = booking_schema.dump(insant_nt_f_lookup_kickback)

                insant_nt_f_lookup_kickback = Booking.query.filter_by(branch_id=branch_id).filter_by(
                    forwarded=False).filter_by(serviced=False).filter_by(
                    is_instant=True).order_by(Booking.date_added.asc()).filter_by(nxt=4004).filter(
                    Booking.start == 99999999).first()

                instant_data_downlist_kickback = booking_schema.dump(insant_nt_f_lookup_kickback)

                final_list = list()
                final_list.append(instant_data_downlist_kickback) if instant_data_downlist_kickback else ""
                final_list.append(instant_data_uplist_kickback) if instant_data_uplist_kickback else ""
                # new instant list
                instant_data_kickback = sorted(final_list, key=itemgetter('date_added'))

                log(instant_data_kickback)

                # get the next instant ticket and make it active
                insant_nt_f_lookup = Booking.query.filter_by(branch_id=branch_id).filter_by(
                    service_name=service_name).filter_by(forwarded=False).filter_by(serviced=False).filter_by(
                    is_instant=True).order_by(Booking.date_added.asc()).filter_by(nxt=1001).filter(
                    Booking.start != 99999999).first()
                instant_data_uplist = booking_schema.dump(insant_nt_f_lookup)

                insant_nt_f_lookup = Booking.query.filter_by(branch_id=branch_id).filter_by(
                    service_name=service_name).filter_by(forwarded=False).filter_by(serviced=False).filter_by(
                    is_instant=True).order_by(Booking.date_added.asc()).filter_by(nxt=4004).filter(
                    Booking.start != 99999999).first()
                instant_data_downlist = booking_schema.dump(insant_nt_f_lookup)

                final_list = list()
                final_list.append(instant_data_downlist) if instant_data_downlist else ""
                final_list.append(instant_data_uplist) if instant_data_uplist else ""
                instant_data = sorted(final_list, key=itemgetter('date_added'))

                # >>> new Tickets -> ! reset
                # none instant ticket
                normal_nt_f_lookup_uplist = Booking.query.filter_by(branch_id=branch_id).filter_by(
                    service_name=service_name).filter_by(teller=False).filter_by(forwarded=False).filter_by(
                    is_instant=False).order_by(Booking.date_added.asc()).filter_by(serviced=False).filter_by(
                    nxt=1001).first()
                normal_data_uplist = booking_schema.dump(normal_nt_f_lookup_uplist)

                # forwarded ticket
                fowarded_lookup_uplist = Booking.query.filter_by(branch_id=branch_id).filter_by(
                    forwarded=True).filter_by(
                    serviced=False).filter_by(teller=teller).filter_by(serviced=False).filter_by(nxt=1001).order_by(
                    Booking.date_added.asc()).first()
                booking_data_fwrd_uplist = booking_schema.dump(fowarded_lookup_uplist)

                temp_uplist = list()
                temp_uplist.append(normal_data_uplist) if normal_data_uplist else ""
                temp_uplist.append(update_forwarded_data(booking_data_fwrd_uplist)) if booking_data_fwrd_uplist else ""

                # >>> ticket reset -> !new tickets
                # none instant ticket
                normal_nt_f_lookup_downlist = Booking.query.filter_by(branch_id=branch_id).filter_by(
                    service_name=service_name).filter_by(teller=False).filter_by(forwarded=False).filter_by(
                    is_instant=False).order_by(Booking.date_added.asc()).filter_by(nxt=4004).first()
                normal_data_downlist = booking_schema.dump(normal_nt_f_lookup_downlist)

                # forwarded ticket
                fowarded_lookup_downlist = Booking.query.filter_by(branch_id=branch_id).filter_by(
                    forwarded=True).filter_by(serviced=False).filter_by(teller=teller).filter_by(nxt=4004).order_by(
                    Booking.date_added.asc()).first()
                booking_data_fwrd_downlist = booking_schema.dump(fowarded_lookup_downlist)

                temp_downlist = list()
                temp_downlist.append(normal_data_downlist) if normal_data_downlist else ""
                temp_downlist.append(update_forwarded_data(booking_data_fwrd_downlist)) if booking_data_fwrd_downlist \
                    else ""

                temp = temp_downlist + temp_uplist

                newlist = sorted(temp, key=itemgetter('date_added'))

                # first ticket after sorting
                final = newlist[0] if newlist else {}

                ticket_to_be_used = instant_data_kickback[0] if instant_data_kickback else (instant_data[0] if
                                                                                            instant_data else final)

                if ticket_to_be_used:
                    if int(ticket_to_be_used["is_instant"]):
                        '''instant data'''
                        old_id = ticket_to_be_used["id"]

                        lookup = Booking.query.get(old_id)
                        lookup.active = True
                        lookup.teller = teller
                        lookup.unique_teller = unique_teller_code(teller)
                        db.session.commit()

                        # start
                        current_booking_info = TellerBooking.query.filter_by(booking_id=old_id).order_by(
                            TellerBooking.date_added.asc()).first()
                        current_booking_data = teller_booking_schema.dump(current_booking_info)
                        if current_booking_data:
                            current_booking_info.active = False
                            db.session.commit()

                            # making new booking entry
                            if int(current_booking_data["teller_to"]) == int(ticket_to_be_used["teller"]):
                                final = {"msg": "booking is still assigned to the teller"}
                            else:

                                booking_teller = TellerBooking(teller, ticket_to_be_used["id"], 0, "", True)
                                db.session.add(booking_teller)
                                db.session.commit()

                                final = booking_schema.dump(ticket_to_be_used)
                        else:
                            # new booking_assignemnt
                            booking_teller = TellerBooking(teller, ticket_to_be_used["id"], 0, "", True)
                            db.session.add(booking_teller)
                            db.session.commit()

                            final = booking_schema.dump(ticket_to_be_used)
                            # end
                    else:
                        ''' normal data '''
                    if not ticket_to_be_used["forwarded"]:

                        old_id = ticket_to_be_used["id"]
                        lookup = Booking.query.get(old_id)
                        lookup.active = True
                        lookup.teller = teller
                        lookup.unique_teller = unique_teller_code(teller)
                        db.session.commit()

                        # start
                        # the teller booking  ...
                        current_booking_info = TellerBooking.query.filter_by(booking_id=old_id).order_by(
                            TellerBooking.date_added.desc()).first()
                        current_booking_data = teller_booking_schema.dump(current_booking_info)

                        if current_booking_data:
                            current_booking_info.active = False
                            db.session.commit()
                            # making new booking entry
                            if int(current_booking_data["teller_to"]) == int(ticket_to_be_used["teller"]):
                                final = dict()
                            else:
                                booking_teller = TellerBooking(teller, ticket_to_be_used["id"], 0, "", True)
                                db.session.add(booking_teller)
                                db.session.commit()
                                final = booking_schema.dump(ticket_to_be_used)
                        else:
                            # new booking_assignemnt
                            booking_teller = TellerBooking(teller, ticket_to_be_used["id"], 0, "", True)
                            db.session.add(booking_teller)
                            db.session.commit()

                            final = booking_schema.dump(ticket_to_be_used)
                            # end
                        # init for timer
                    else:
                        # if it forwarded
                        # use the update booking to pre_req
                        booking_id = ticket_to_be_used["id"]
                        teller = ticket_to_be_used["teller"]
                        activate_forwarded_booking_on_teller(booking_id, teller)
                else:
                    # no instant nor normal booking data
                    final = dict()
            else:
                final = dict()
        else:
            # non-mdeical data goes here
            branch_id = exists["branch"]
            teller_number = exists["number"]
            service_name = exists["service"]

            # active ticket
            lkp = Booking.query.filter_by(branch_id=branch_id).filter_by(serviced=False).filter_by(
                teller=teller_number).filter_by(active=True).filter_by(serviced=False).first()
            lkp_data = booking_schema.dump(lkp)

            if not lkp_data:
                # get the next instant ticket and make it active
                insant_nt_f_lookup = Booking.query.filter_by(branch_id=branch_id).filter_by(
                    service_name=service_name).filter_by(forwarded=False).filter_by(serviced=False).filter_by(
                    is_instant=True).order_by(Booking.date_added.asc()).filter_by(nxt=1001).first()
                instant_data_uplist = booking_schema.dump(insant_nt_f_lookup)

                insant_nt_f_lookup = Booking.query.filter_by(branch_id=branch_id).filter_by(
                    service_name=service_name).filter_by(forwarded=False).filter_by(serviced=False).filter_by(
                    is_instant=True).order_by(Booking.date_added.asc()).filter_by(nxt=4004).first()
                instant_data_downlist = booking_schema.dump(insant_nt_f_lookup)

                final_list = list()
                final_list.append(instant_data_downlist) if instant_data_downlist else ""
                final_list.append(instant_data_uplist) if instant_data_uplist else ""
                # new instant list
                instant_data = sorted(final_list, key=itemgetter('date_added'))
                # >>> new Tickets -> ! reset
                # none instant ticket
                normal_nt_f_lookup_uplist = Booking.query.filter_by(branch_id=branch_id).filter_by(
                    service_name=service_name).filter_by(teller=False).filter_by(forwarded=False).filter_by(
                    is_instant=False).order_by(Booking.date_added.asc()).filter_by(nxt=1001).first()
                normal_data_uplist = booking_schema.dump(normal_nt_f_lookup_uplist)

                # forwarded ticket
                fowarded_lookup_uplist = Booking.query.filter_by(branch_id=branch_id).filter_by(
                    forwarded=True).filter_by(
                    serviced=False).filter_by(teller=teller).filter_by(nxt=1001).order_by(
                    Booking.date_added.asc()).first()
                booking_data_fwrd_uplist = booking_schema.dump(fowarded_lookup_uplist)

                temp_uplist = list()
                temp_uplist.append(normal_data_uplist) if normal_data_uplist else ""
                temp_uplist.append(update_forwarded_data(booking_data_fwrd_uplist)) if booking_data_fwrd_uplist else ""

                # >>> ticket reset -> !new tickets
                # none instant ticket
                normal_nt_f_lookup_downlist = Booking.query.filter_by(branch_id=branch_id).filter_by(
                    service_name=service_name).filter_by(teller=False).filter_by(forwarded=False).filter_by(
                    is_instant=False).order_by(Booking.date_added.asc()).filter_by(nxt=4004).first()
                normal_data_downlist = booking_schema.dump(normal_nt_f_lookup_downlist)

                # forwarded ticket
                fowarded_lookup_downlist = Booking.query.filter_by(branch_id=branch_id).filter_by(
                    forwarded=True).filter_by(serviced=False).filter_by(teller=teller).filter_by(nxt=4004).order_by(
                    Booking.date_added.asc()).first()
                booking_data_fwrd_downlist = booking_schema.dump(fowarded_lookup_downlist)

                temp_downlist = list()
                temp_downlist.append(normal_data_downlist) if normal_data_downlist else ""
                temp_downlist.append(update_forwarded_data(booking_data_fwrd_downlist)) if booking_data_fwrd_downlist \
                    else ""

                temp = temp_downlist + temp_uplist

                newlist = sorted(temp, key=itemgetter('date_added'))

                # first ticket after sorting
                final = newlist[0] if newlist else {}

                ticket_to_be_used = instant_data[0] if instant_data else final
                if ticket_to_be_used:

                    if int(ticket_to_be_used["is_instant"]):
                        '''instant data'''
                        old_id = ticket_to_be_used["id"]

                        lookup = Booking.query.get(old_id)
                        lookup.active = True
                        lookup.teller = teller
                        lookup.unique_teller = unique_teller_code(teller)
                        db.session.commit()

                        # start
                        current_booking_info = TellerBooking.query.filter_by(booking_id=old_id).order_by(
                            TellerBooking.date_added.asc()).first()
                        current_booking_data = teller_booking_schema.dump(current_booking_info)
                        if current_booking_data:
                            current_booking_info.active = False
                            db.session.commit()

                            # making new booking entry
                            if int(current_booking_data["teller_to"]) == int(ticket_to_be_used["teller"]):
                                final = {"msg": "booking is still assigned to the teller"}
                            else:

                                booking_teller = TellerBooking(teller, ticket_to_be_used["id"], 0, "", True)
                                db.session.add(booking_teller)
                                db.session.commit()

                                final = booking_schema.dump(ticket_to_be_used)
                        else:
                            # new booking_assignemnt
                            booking_teller = TellerBooking(teller, ticket_to_be_used["id"], 0, "", True)
                            db.session.add(booking_teller)
                            db.session.commit()

                            final = booking_schema.dump(ticket_to_be_used)
                            # end
                    else:
                        ''' normal data '''
                    if not ticket_to_be_used["forwarded"]:
                        old_id = ticket_to_be_used["id"]
                        lookup = Booking.query.get(old_id)
                        lookup.active = True
                        lookup.teller = teller
                        lookup.unique_teller = unique_teller_code(teller)
                        db.session.commit()

                        # start
                        # the teller booking  ...
                        current_booking_info = TellerBooking.query.filter_by(booking_id=old_id).order_by(
                            TellerBooking.date_added.desc()).first()
                        current_booking_data = teller_booking_schema.dump(current_booking_info)

                        if current_booking_data:
                            current_booking_info.active = False
                            db.session.commit()
                            # making new booking entry
                            if int(current_booking_data["teller_to"]) == int(ticket_to_be_used["teller"]):
                                final = dict()
                            else:
                                booking_teller = TellerBooking(teller, ticket_to_be_used["id"], 0, "", True)
                                db.session.add(booking_teller)
                                db.session.commit()
                                final = booking_schema.dump(ticket_to_be_used)
                        else:
                            # new booking_assignemnt
                            booking_teller = TellerBooking(teller, ticket_to_be_used["id"], 0, "", True)
                            db.session.add(booking_teller)
                            db.session.commit()

                            final = booking_schema.dump(ticket_to_be_used)
                            # end
                        # init for timer
                    else:
                        # if it forwarded
                        # use the update booking to pre_req
                        booking_id = ticket_to_be_used["id"]
                        teller = ticket_to_be_used["teller"]
                        activate_forwarded_booking_on_teller(booking_id, teller)
                else:
                    # no instant nor normal booking data
                    final = dict()
            else:
                final = dict()

    # end
    else:
        final = None

    if final:
        log(final)
        init_ticket_timer(final["id"], final["service_name"])
        if not int(final["user"]) == 0:
            final = {
                "teller": final["teller"],
                "start": final["start"],
                "user": final["user"],
                "active": final["active"],
                "ticket": final["kind"],
                "id": final["id"],
                "is_instant": final["is_instant"],
                "serviced": final["serviced"],
                "branch_id": final["branch_id"],
                "service_name": final["service_name"],
                "forwarded": final["forwarded"]
            }

    return jsonify(final)


def activate_forwarded_booking_on_teller(booking_id, teller):
    book = Booking.query.get(booking_id)
    book.teller = teller
    book.active = True
    db.session.commit()
    return book


def has_pre_req(booking_id):
    teller_booking = get_teller_booking_ref(booking_id)
    if teller_booking:
        final = teller_booking.pre_req != 0
    else:
        final = False

    return final


def pre_req_is_attended(booking_id):
    teller_booking = get_teller_booking_ref(booking_id)
    return False if teller_booking.preq_date_servived == parser.parse("1970-01-01 00:00:00") else True


def get_teller_booking_ref(booking_id):
    return TellerBooking.query.filter_by(booking_id=booking_id).order_by(TellerBooking.date_added.desc()).first()


def close_ticket(teller, comment):
    # you can only close ac ticket at a cartain teller
    booking_lookup = Booking.query.filter_by(teller=teller).filter_by(serviced=False).order_by(Booking.date_added.desc(
    )).filter_by(active=True).first()
    booking_data = booking_schema.dump(booking_lookup)
    log(booking_data)
    # get bracnch by id
    if booking_data:
        branch_data = branch_by_id(booking_data["branch_id"])
        #  check if booking has a prerequisite
        # and
        if has_pre_req(booking_lookup.id) and not pre_req_is_attended(booking_lookup.id):
            # make teller booking inactive for this booking
            # make leave booking active and forwarded but now make it active to the teller old teller booking
            # create a new teller booking with teller form and preq and teller_to as still teller to
            current_booking_info = TellerBooking.query.filter_by(booking_id=booking_data["id"]).filter_by(
                active=True).all()
            for x in current_booking_info:
                x.active = False
                db.session.commit()

            ref = get_teller_booking_ref(booking_lookup.id)
            if not TellerBooking.query.filter_by(booking_id=booking_data["id"]).filter_by(active=True).all():
                try:
                    if int(booking_lookup.start) == 99999999:
                        booking_lookup.is_instant = True
                        booking_lookup.forwarded = False
                        booking_lookup.teller = 0
                        booking_lookup.user = 99999999
                        booking_lookup.kind = booking_lookup.ticket
                except ValueError:
                    pass

                booking_teller = TellerBooking(ref.teller_to, booking_lookup.id, ref.pre_req, comment, False)
                db.session.add(booking_teller)
                db.session.commit()

            # # we need to update the booking to another new teller
            booking_lookup.teller = ref.teller_to
            booking_lookup.unique_teller = unique_teller_code(ref.teller_to)
            booking_lookup.active = False
            db.session.commit()

        else:
            current_booking_info = TellerBooking.query.filter_by(booking_id=booking_data["id"]).order_by(
                TellerBooking.date_added.desc()).first()
            if current_booking_info:
                current_booking_info.active = False
                db.session.commit()

            # make this booking inactive
            booking_lookup.active = False
            booking_lookup.teller = teller
            booking_lookup.unique_teller = unique_teller_code(teller)
            booking_lookup.serviced = True
            db.session.commit()

        # setting booking end for BookingSetting
        update_timestamp(booking_data["id"], end=datetime.now())

        # make the book inactive
        final = dict()
        key = {"key_": branch_data["key_"]}
        final.update(key)
        final.update(booking_schema.dump(booking_data))
    else:
        final = {}
    return final


def get_active_ticket(teller_number, branch_id):
    data = get_teller_services(teller_number)
    # will be an issue working with many services for asingle teller
    service_name = data["service"]
    teller_number = data["number"]
    lookup = Booking.query.filter_by(service_name=service_name).filter_by(branch_id=branch_id). \
        filter_by(teller=teller_number).filter_by(nxt=1001).filter(Booking.active.is_(True)).first()
    data = booking_schema.dump(lookup)
    return data


# def get_next_ticket(service_name):
#     lookup = Booking.query.filter_by(service_name=service_name).filter(Booking.next.is_(True)).first()
#     data = booking_schema.dump(lookup)
#     return data


def create_service(name, teller, branch_id, code, icon_id, visible):
    branch_data = branch_exist(branch_id)
    if branch_data:
        final = None
        if service_exists(name, branch_id):
            final = {"msg": "Error service name already exists", "status": None}
        else:
            if get_service_code(code, branch_id):
                final = {"msg": "Error Code already exists", "status": None}
            else:
                # check if icon exists for the branch
                # if icon_exists(icon_id, branch_id):
                icon = Icon.query.get(icon_id)
                if icon:
                    try:
                        service = ServiceOffered(name, branch_id, teller, code, icon.id)
                        service.medical_active = True
                        if not visible:
                            service.medical_active = False
                        db.session.add(service)
                        db.session.commit()

                        dict_ = dict()

                        # adding the ofline key so that we can have consitancy
                        key = {"key": branch_data["key_"]}
                        dict_.update(key)
                        dict_.update(service_schema.dump(service))
                        final = dict_
                    except Exception as e:
                        final = {"msg": "Error service by that name exists"}
    else:
        final = {"msg": "Service/Branch issue", "status": None}
    return final


def teller_exists(id):
    lookup = Teller.query.get(id)
    teller_data = teller_schema.dump(lookup)
    return teller_data


def icon_exists(icon_id, branch_id):
    lookup = Icon.query.get(icon_id)
    data = icon_schema.dump(lookup)
    if data:
        if data["branch"] == branch_id:
            final = data
        else:
            final = None
    else:
        final = None
    return final


def branch_exist(branch_id):
    lookup = Branch.query.get(branch_id)
    branch_data = branch_schema.dump(lookup)
    return branch_data


def service_exists(name, branch_id):
    lookup = ServiceOffered.query.filter_by(name=name).filter_by(branch_id=branch_id).first()
    data = service_schema.dump(lookup)
    return data


def get_branch_services(branch_id):
    lookup = ServiceOffered.query.filter_by(branch_id=branch_id).filter_by(active=True).all()
    data = services_schema.dump(lookup)
    final = list()
    if data:
        for icon in data:
            icon_lookup = Icon.query.get(int(icon["icon"]))
            icon_data = icon_schema.dump(icon_lookup)
            if icon_data:
                icon_ = {"icon_image": str(icon_data["icon"])}
                fin = {**icon, **icon_}
                final.append(fin)
    actual_tellers = dict()
    for service in lookup:
        lookup = Teller.query.filter_by(service=service.name).all()
        if len(lookup) > 1:
            tellers = list()
            tellers_ = " ".join(tellers)
            for teller in lookup:
                tellers.append(teller.number)
            actual_tellers.update({service.name: ', '.join([f"{x}" for x in tellers])})
        else:
            if lookup:
                actual_tellers.update({service.name: lookup[0].number})
            else:
                actual_tellers.update({service.name: "N/A"})
    final_ = list()
    for x in final:
        x["teller"] = actual_tellers[x["name"]]

        final_.append(x)
    return final


def get_service_code(code, branch_id):
    lookup = ServiceOffered.query.filter_by(name=code).filter_by(branch_id=branch_id).first()
    data = service_schema.dump(lookup)
    return data


def booking_exists(branch, service, tckt):
    lookup = Booking.query.filter_by(branch_id=branch).filter_by(nxt=1001).filter_by(service_name=service).filter_by(
        ticket=tckt).first()
    data = booking_schema.dump(lookup)
    if data:
        final = True
    else:
        final = False
    return final


def booking_exists_by_unique_id(unique_id):
    lookup = Booking.query.filter_by(unique_id=unique_id).first()
    data = booking_schema.dump(lookup)
    if data:
        final = True
    else:
        final = False
    return final


def update_branch_offline(key):
    lookup = Branch.query.filter_by(key_=key).first()
    lookup_data = branch_schema.dump(lookup)
    return lookup_data


def create_booking(service_name, start, branch_id, is_instant=False, user=0, kind=0, unique_id="", is_synced=""):
    # check if booking is
    if branch_is_medical(branch_id):
        if service_exists(service_name, branch_id):
            # get the service

            data = service_exists(service_name, branch_id)
            name = data["name"]
            if ticket_queue(service_name, branch_id):
                book = ticket_queue(service_name, branch_id)
                last_ticket_number = book["ticket"]
                next_ticket = int(last_ticket_number) + 1

                final = make_booking(name, start, branch_id, next_ticket, instant=False, user=user, kind=kind,
                                     unique_id=unique_id, is_synced=is_synced)
            else:
                # we are making the first booking for this category
                # we are going to make this ticket  active
                next_ticket = 1
                final = make_booking(name, start, branch_id, next_ticket, active=False, instant=False, user=user,
                                     kind=kind, unique_id=unique_id, is_synced=is_synced)
        else:
            final = None
    else:
        if service_exists(service_name, branch_id):
            # get the service
            data = service_exists(service_name, branch_id)
            name = data["name"]
            if ticket_queue(service_name, branch_id):
                book = ticket_queue(service_name, branch_id)
                last_ticket_number = book["ticket"]
                next_ticket = int(last_ticket_number) + 1
                final = make_booking(name, start, branch_id, next_ticket, instant=is_instant, user=user, kind=kind,
                                     unique_id=unique_id, is_synced=is_synced)
            else:
                # we are making the first booking for this category
                # we are going to make this ticket  active
                next_ticket = 1
                final = make_booking(name, start, branch_id, next_ticket, active=False, instant=is_instant, user=user,
                                     kind=kind, unique_id=unique_id, is_synced=is_synced)
        else:
            final = None
    return final


def branch_by_id(id):
    lookup = Branch.query.get(id)
    return branch_schema.dump(lookup)


def make_booking(service_name, start="", branch_id=1, ticket=1, active=False, upcoming=False, serviced=False,
                 teller=0, kind="1", user=0, instant=False, fowarded=False, unique_id="", is_synced=""):
    # check if a branch exists
    branch_data = branch_by_id(branch_id)
    final_ = dict()
    if branch_data:
        try:
            lookup = Booking(service_name, start, branch_id, ticket, active, upcoming, serviced, teller, kind, user,
                             instant, fowarded)
            if unique_id:
                lookup.unique_id = unique_id
            if is_synced:
                lookup.is_synced = True

            if int(user) != 0:
                lookup.is_synced = True

            db.session.add(lookup)
            db.session.commit()

            final = booking_schema.dump(lookup)

            branch_key_data = {"key_": branch_data["key_"]}
            final_.update(branch_key_data)
            final_.update(final)
        except sqlalchemy.exc.IntegrityError:
            pass
    return final_


def make_booking_online(service_name, start="", branch_id=1, ticket=1, active=False, upcoming=False, serviced=False,
                        teller=0, kind="1", user=0, instant=False, fowarded=False, unique_id="", is_synced="",
                        verify=""):
    # check if a branch exists
    branch_data = branch_by_id(branch_id)
    final_ = dict()
    if branch_data:
        lookup = Booking(service_name, start, branch_id, ticket, active, upcoming, serviced, teller, kind, user,
                         instant, fowarded)
        if unique_id:
            lookup.unique_id = unique_id
        if is_synced:
            lookup.is_synced = True
        if int(user) != 0:
            lookup.is_synced = True
        if verify:
            lookup.verify = verify

        db.session.add(lookup)
        db.session.commit()

        final = booking_schema.dump(lookup)

        branch_key_data = {"key_": branch_data["key_"]}
        final_.update(branch_key_data)
        final_.update(final)
    return final_


def booking_active(booking_id, state, teller):
    lookup = Booking.query.get(booking_id)
    lookup.active = state
    if state:
        lookup.teller = teller
        state = db.session.commit()

    return state


def booking_upcoming(booking_id, state):
    lookup = Booking.query.get(booking_id)
    lookup.next = state
    state = db.session.commit()

    return state


def booking_serviced(booking_id, state):
    lookup = Booking.query.get(booking_id)
    lookup.serviced = state
    x = db.session.commit()
    return x


def get_booking_(code):
    lookup = Booking.query.filter_by(verify=code).first()
    data = booking_schema.dump(lookup)
    return data


def get_booking(code):
    lookup = Booking.query.get(code)
    data = booking_schema.dump(lookup)
    return data


def get_bookings():
    lookup = Booking.query.filter_by(nxt=1001).all()
    data = bookings_schema.dump(lookup)
    return jsonify(data)


def user_exists(user_id):
    lookup = Customer.query.get(user_id)
    user_data = user_schema.dump(lookup)
    return user_data


'''
Here the teller in question is the caller teller
so if a teller calls then he/she makes a call to
methods with a give endpoint
---
here we are going to make sure if the teller exists
'''


# this will check the services for this teller
def check_teller_service(teller, service):
    lookup = Teller.query.filter(Teller.service.contains(service)).filter_by(number=teller).first()
    lookup_data = teller_schema.dump(lookup)
    return lookup_data


def get_instant_ticket(service):
    lookup = Booking.query.filter_by(service_name=service).filter_by(is_instant=True).filter_by(nxt=1001).filter_by(
        serviced=False).order_by(Booking.start.desc()).first()
    booking_data = booking_schema.dump(lookup)
    return booking_data


def service_ticket(service_name, teller):
    # get the number of tellers there are for the service
    # if more than one queue the ticket for the next
    # get active ticket with the id
    if check_teller_service(teller, service_name):
        active = get_active_ticket(service_name)
        upcoming = get_next_ticket(service_name)
        last = get_last_ticket(service_name)
        next_by_date = get_next_ticket_by_date(service_name)

        if active and upcoming and next_by_date:
            last_is_active = last["active"]
            if last_is_active:
                # we do no have another record
                booking_active(active["id"], False)
                final = {"msg": "last service active"}
            else:
                # has at least three records
                # make active serviced
                booking_active(active["id"], False)
                # make next active
                booking_active(upcoming["id"], True, teller)
                booking_upcoming(upcoming["id"], False)
                # last booking ot be next
                # just flag one as three was none flagged for active,upcoming serviced
                booking_upcoming(next_by_date["id"], True)
                final = {"msg": "flagged all three"}
        elif active and upcoming:
            # make active serviced
            booking_active(active["id"], False)
            # make next active
            booking_active(upcoming["id"], True, teller)
            booking_upcoming(upcoming["id"], False)
            final = {"msg": "flagged two"}
        elif active:
            booking_active(active["id"], False)
            final = {"msg": "flagged one"}
        else:
            # this table is empty
            final = {"msg": "0"}
    else:
        final = {"msg": "servive/teller issue"}
    return final


def finalize_ticket(booking_id):
    lookup = Booking.query.get(booking_id)
    data = booking_schema.dump(lookup)
    if data:
        booking_serviced(data["id"], True)
    return data


def rivert_finalization(booking_id):
    lookup = Booking.query.get(booking_id)
    data = booking_schema.dump(lookup)
    if data:
        booking_serviced(data["id"], False)
    return data


def teller_exist(teller_id):
    lookup = Teller.query.get(teller_id)
    data = teller_schema.dump(lookup)
    return data


def get_teller(number, branch_id):
    lookup = Teller.query.filter_by(number=number).filter_by(branch=branch_id).first()
    data = teller_schema.dump(lookup)
    return data


'''
changing service_offered for the teller
'''


def modify_teller_service(service_id, service_name):
    lookup = ServiceOffered.query.get(service_id)
    lookup.name = service_name
    db.session.commit()

    return lookup


def services_exist(services, branch_id):
    holder = services.split(",")
    for item in holder:
        if not service_exists(item, branch_id):
            return False
    return True


def add_teller(teller_number, branch_id, service_name, branch_unique_id):
    # here we are going to ad teller details
    if len(service_name.split(",")) > 1:
        if services_exist(service_name, branch_id) and branch_exist(branch_id):
            # get teller by name
            if get_teller(teller_number, branch_id):
                final = dict(), 500
            else:
                lookup = Teller(teller_number, branch_id, service_name, branch_unique_id)
                db.session.add(lookup)
                db.session.commit()

                # update service_offered
                service_lookup = ServiceOffered.query.filter_by(name=service_name).filter_by(
                    branch_id=branch_id).first()
                service_lookup.teller = teller_number
                db.session.commit()

                final = teller_schema.dump(lookup)


        else:
            final = dict()
    else:
        if branch_exist(branch_id) and service_exists(service_name, branch_id):
            # get teller by name
            if get_teller(teller_number, branch_id):
                final = dict(), 500
            else:
                lookup = Teller(teller_number, branch_id, service_name, branch_unique_id)
                db.session.add(lookup)
                db.session.commit()

                data = teller_schema.dump(lookup)
                final = data

                service_lookup = ServiceOffered.query.filter_by(name=service_name).filter_by(
                    branch_id=branch_id).first()
                service_lookup.teller = teller_number
                db.session.commit()
        else:
            final = dict(), 500

    return final


'''
online advantage
check user is online booking
if True queue as next
make next as following.
follow next
then check if next is online
if is online queue next
'''


def get_online_booking(booking_id):
    lookup = OnlineBooking.query.get(booking_id)
    data = online_booking_schema.dump(lookup)
    return data


'''
teller_booking for all bookings
WORKING WITH TICKET FORWARDING
'''


def create_teller_booking(teller_to, booking_id, teller_from, remarks, active):
    lookup = TellerBooking(teller_to, booking_id, teller_from, remarks, active)
    db.session.add(lookup)
    db.session.commit()

    return teller_booking_schema.dump(lookup)


def activate_teller_booking(booking_id):
    lookup = TellerBooking.query.get(booking_id)
    lookup.active = True
    db.session.commit()

    return teller_booking_schema.dump(lookup)


def deactivate_teller_booking(booking_id):
    lookup = TellerBooking.query.get(booking_id)
    lookup.active = False
    db.session.commit()

    return teller_booking_schema.dump(lookup)


'''
get the last teller_booking with that id of active
if None create anew one
if exists make it inactive and create new active
'''


def activate_new_booking(teller_to, booking_id, remarks, active):
    latest_booking = get_last_teller_booking(booking_id)
    if latest_booking:
        # there is a booking here
        # deactivate foward_booking
        deactivate_teller_booking(latest_booking["id"])
        # activate new foward_booking
        final = create_teller_booking(teller_to, latest_booking["booking_id"], latest_booking["teller_to"], remarks,
                                      True)
    else:
        final = create_teller_booking(teller_to, booking_id, 10000000, remarks, active)
    return final


'''
Last booking by date from these booking_id provided
'''


def get_last_teller_booking(booking_id):
    lookup = TellerBooking.query.filter_by(booking_id=booking_id).filter(asc(TellerBooking.date_added)).first()
    data = teller_booking_schema.dump(lookup)
    return data


'''
verify booking
@:param booking_id,time
@:return Boolean
'''


# needs work
def verify_ticket(code):
    if get_booking_(code):
        # get booking data
        final = ""
        if not booking_is_served(code):
            # adding print request to the from end
            final = {"msg": "booking Expired", "status": False}
        else:
            final = {"msg": "booking valid", "status": True}
    else:
        final = {"msg": "Booking Not Exists", "status": False}
    return final


def booking_is_served(code):
    booking = get_booking_by_code(code)
    if booking:
        return booking.serviced
    else:
        return False


def get_booking_by_code(code):
    booking = Booking.query.filter_by(verify=code).first()
    return booking


def is_booking(code):
    return get_booking_by_code(code)


def teller_bookings(teller_id):
    lookup = TellerBooking.query.filter_by(teller_to=teller_id)
    data = teller_schema.dump(lookup)
    return data


'''
file uploading for the icon
'''

ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', "mp4"])


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def upload():
    # check if the post request has the file part
    if 'file' not in request.files:
        resp = jsonify({'message': 'No file part in the request'})
        resp.status_code = 400
        return resp
    file = request.files['file']
    if file.filename == '':
        resp = jsonify({'message': 'No file selected for uploading'})
        resp.status_code = 400
        return resp
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        try:
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        except FileNotFoundError:
            flash("file Not Found. Path Issue.", "warning")
        # adding to the database
        lookup = Icon(filename, 1)
        db.session.add(lookup)
        db.session.commit()

        resp = jsonify({'message': 'File successfully uploaded'})
        resp.status_code = 201
        return resp
    else:
        resp = jsonify({'message': 'Allowed file types are txt, pdf, png, jpg, jpeg, gif'})
        resp.status_code = 400
        return resp


def get_branch_icons(branch_id):
    lookup = Icon.query.filter_by(branch=branch_id)
    data = icons_schema.dump(lookup)
    return jsonify(data)


def branch_activate(branch_id, expires):
    key = secrets.token_hex(1024)
    lookup = Branch.query.get(branch_id)
    if lookup:
        lookup.key = key
        lookup.valid_till = expires
        db.session.commit()
        final = branch_schema.dump(lookup)
    else:
        final = {"msg": "Error, Branch Does not exists."}
    return final


def branch_verify(branch_id):
    lookup = Branch.query.get(branch_id)
    return jsonify(branch_schema.dump(lookup))


def branch_is_valid(branch_id):
    lookup = Branch.query.get(branch_id)
    data = branch_schema.dump(lookup)
    if data:
        key = data["key"]
        if key:
            final = data, 200
        else:
            final = {"msg": "branch Not valid"}, 500
    else:
        final = {"msg": "Error! branch not found"}, 500
    return final


def get_branch_by_key(key):
    lookup = Branch.query.filter_by(key_=key).first()
    return branch_schema.dump(lookup)


def get_company_by_id(id):
    lookup = Company.query.get(id)
    return jsonify(company_schema.dump(lookup))


def get_allbooking(branch_id, service_name):
    online = get_online_booking(branch_id, service_name)
    offline = get_offline_booking(branch_id, service_name)
    data = online + offline
    return data


def get_all_bookings_no_branch():
    data = Booking.query.filter_by(nxt=1001).all()
    return bookings_schema.dump(data)


def loop_data_check_reset_tickets(data):
    ticket_reset = list()
    for item in data:
        if item.nxt == 4004:
            ticket_reset.append(item)
    return ticket_reset


def get_online_booking(branch_id, service_name):
    online = OnlineBooking.query.filter_by(branch_id=branch_id).filter_by(service_name=service_name).all()
    online_data = online_bookings_schema.dump(online)
    return online_data


def get_offline_booking(branch_id, service_name):
    offline = Booking.query.filter_by(branch_id=branch_id).filter_by(nxt=1001).filter_by(
        service_name=service_name).filter_by(active=False). \
        filter_by(serviced=False).all()
    offline_data = bookings_schema.dump(offline)
    return offline_data


def delete_branch_by_key(key):
    if get_branch_by_key(key):
        return None
    else:
        lookup = Branch.query.filter_by(key=key).first()
        db.session.remove(lookup)
        db.session.commit()

        return branch_schema.dump(lookup)


def send_mail(_to, subject, body):
    _from = "admin@fuprox.com"
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = _from
    message["To"] = _to

    # Turn these into plain/html MIMEText objects
    part = MIMEText(body, "html")

    # Add HTML/plain-text parts to MIMEMultipart message
    message.attach(part)

    # Create secure connection with server and send email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("mail.fuprox.com", 465, context=context) as server:
        server.login(_from, "Japanitoes")
        if server.sendmail(_from, _to, message.as_string()):
            final = {"sent": True}
        else:
            final = {"sent": False}
    return final


def upgrade_ticket():
    # require payment
    # get booking id an queue it next
    pass


def get_teller_tickets(teller):
    for_the_service = get_bookings_for_the_service(teller)
    forwarded_for_the_service = get_bookings_forwarded_teller()
    pass


def get_teller_service(teller):
    teller = Teller.query.filter_by(number=int(teller)).first()
    return teller


def teller_bookings(teller):
    teller_service = get_teller_service(teller)
    if teller_service:
        normal = Booking.query.filter_by(service_name=teller_service.service).filter_by(serviced=False).filter_by(
            forwarded=False).filter(Booking.start != 99999999).filter_by(teller=0).all()
        forwarded = Booking.query.filter_by(serviced=False).filter_by(forwarded=True).filter(
            Booking.start != 99999999).filter_by(teller=teller).all()
        kick_back_instant = Booking.query.filter_by(serviced=False).filter_by(is_instant=True).filter(Booking.start ==
                                                                                                      99999999).filter_by(
            teller=teller).all()
        kick_back_normal = Booking.query.filter_by(serviced=False).filter_by(is_instant=False).filter(Booking.start ==
                                                                                                      99999999).filter_by(
            teller=teller).all()
        final = len(normal) + len(forwarded) + len(kick_back_instant) + len(kick_back_normal)
    else:
        final = []
    return final


def get_active_ticket_now(teller_number, branch_id_):
    # here we are going to get post data
    lookup = Teller.query.filter_by(number=teller_number).filter_by(branch=branch_id_).first()
    teller_data = teller_schema.dump(lookup)
    if teller_data:
        branch_id = teller_data["branch"]

        # getting branch data
        branch_lookup = Branch.query.get(branch_id)
        branch_data = branch_schema.dump(branch_lookup)

        # service type
        service_lookup = Service.query.filter_by(name=branch_data["service"]).first()
        service_d = service_.dump(service_lookup)

        lookup_uplist = Booking.query.filter_by(teller=teller_number).filter_by(active=True).filter_by(
            nxt=1001).filter_by(branch_id=branch_id).first()
        booking_data_uplist = booking_schema.dump(lookup_uplist)

        lookup_downlist = Booking.query.filter_by(teller=teller_number).filter_by(active=True).filter_by(
            nxt=4004).filter_by(branch_id=branch_id).first()
        booking_data_downlist = booking_schema.dump(lookup_downlist)

        tellerbooking = False

        final_lookup = list()
        final_lookup.append(booking_data_uplist) if booking_data_uplist else ""
        final_lookup.append(booking_data_downlist) if booking_data_downlist else ""

        list_of_final_lookup = sorted(final_lookup, key=itemgetter('date_added'))

        lookup = list_of_final_lookup[0] if list_of_final_lookup else {}

        if lookup:
            tellerbooking_ = TellerBooking.query.filter_by(booking_id=lookup["id"]).order_by(
                TellerBooking.date_added.desc()).first()
            tellerbooking = teller_booking_schema.dump(tellerbooking_)

        if lookup and service_d:
            # working with the service offered
            service_lookup = ServiceOffered.query.filter_by(name=lookup["service_name"]).filter_by(
                branch_id=branch_id).first()
            service_data = service_schema.dump(service_lookup)
            if not int(lookup["user"]) == 0:
                # online ticket
                user_prefs = callout(lookup["teller"])

                lst = {
                    "id": lookup["id"],
                    "service_name": lookup["service_name"],
                    "start": lookup["start"],
                    "ticket": f"{service_data['code']} {lookup['kind']}",
                    "serviced": lookup["serviced"],
                    "teller": lookup["teller"],
                    "is_instant": lookup["is_instant"],
                    "forwarded": lookup["forwarded"],
                    "user": lookup["user"],
                    "caller": f"Ticket Number, {service_data['code']} {lookup['kind']}, {user_prefs['phrase']},"
                              f" {user_prefs['pref']}.",
                    "teller_booking": tellerbooking
                }
            else:
                # not online
                user_prefs = callout(lookup["teller"])
                lst = {
                    "id": lookup["id"],
                    "service_name": lookup["service_name"],
                    "start": lookup["start"],
                    "ticket": f"{service_data['code']} {lookup['ticket']}",
                    "serviced": lookup["serviced"],
                    "teller": lookup["teller"],
                    "is_instant": lookup["is_instant"],
                    "forwarded": lookup["forwarded"],
                    "user": lookup["user"],
                    "caller": f"Ticket Number, {service_data['code']} {lookup['ticket']}"
                              f", {user_prefs['phrase']}, {user_prefs['pref']}.",
                    "teller_booking": tellerbooking
                }
        else:
            lst = dict()
    else:
        lst = dict()
    return lst


'''
working for norma services :
???? instant services required
:returns list
'''


def callout(teller):
    phrase_prefs = Phrase.query.first()
    lookup = Teller.query.filter_by(number=teller).first()

    if phrase_prefs:
        if phrase_prefs.phrase:
            phrase = phrase_prefs.phrase

            if phrase_prefs.use_teller:
                pref = lookup.service
                final = {
                    "phrase": phrase,
                    "pref": pref
                }
            else:
                pref = lookup.number
                final = {
                    "phrase": phrase,
                    "pref": pref
                }
        else:
            phrase = "proceed to counter number "
            pref = lookup.number
            final = {
                "phrase": phrase,
                "pref": pref
            }
    else:
        phrase = "proceed to counter number "
        pref = lookup.number
        final = {
            "phrase": phrase,
            "pref": pref
        }
    return final


def get_next_ticket(teller_number, branch_id_):
    lookup = Teller.query.filter_by(number=teller_number).filter_by(branch=branch_id_).first()
    teller_data = teller_schema.dump(lookup)
    if teller_data:
        branch_id = teller_data["branch"]
        service_name = teller_data["service"]

        # uplist -> we need a uplist for tickets that were reset valid for all categories in the order as before
        lookup_uplist_kickback = Booking.query.filter_by(branch_id=int(branch_id)).filter_by(forwarded=False).filter_by(
            active=False).filter_by(serviced=False).filter_by(is_instant=True).filter_by(start=99999999).filter_by(
            teller=teller_number).filter_by(
            nxt=4004).order_by(
            Booking.date_added.asc()).first()
        booking_data_notbooking_uplist_kickback = booking_schema.dump(lookup_uplist_kickback)

        fwrd_uplist_kickback = Booking.query.filter_by(branch_id=int(branch_id)).filter_by(forwarded=False).filter_by(
            active=False).filter_by(serviced=False).filter_by(is_instant=True).filter_by(start=99999999).filter_by(
            teller=teller_number).filter_by(
            nxt=1001).order_by(
            Booking.date_added.asc()).first()
        booking_data_fwrd_uplist_kickback = booking_schema.dump(fwrd_uplist_kickback)

        temp_uplist_kickback = list()
        temp_uplist_kickback.append(update_forwarded_data(
            booking_data_notbooking_uplist_kickback)) if booking_data_notbooking_uplist_kickback else ""
        temp_uplist_kickback.append(booking_data_fwrd_uplist_kickback) if booking_data_fwrd_uplist_kickback else ""
        final_fwrd_normal_uplist_kick_back = temp_uplist_kickback

        # uplist -> we need a uplist for tickets that were reset valid for all categories in the order as before
        lookup_uplist = Booking.query.filter_by(branch_id=int(branch_id)).filter_by(
            serviced=False).filter_by(active=False).filter_by(nxt=4004).filter_by(
            forwarded=False).filter_by(is_instant=False).order_by(Booking.date_added.asc()).first()
        booking_data_notbooking_uplist = booking_schema.dump(lookup_uplist)

        fwrd_uplist = Booking.query.filter_by(branch_id=int(branch_id)).filter_by(forwarded=True).filter_by(
            is_instant=False).filter_by(active=False).filter_by(teller=teller_number).filter_by(nxt=1001).filter_by(
            serviced=False).order_by(
            Booking.date_added.asc()).first()
        booking_data_fwrd_uplist = booking_schema.dump(fwrd_uplist)

        temp_uplist = list()
        temp_uplist.append(update_forwarded_data(booking_data_fwrd_uplist)) if booking_data_fwrd_uplist else ""
        temp_uplist.append(booking_data_notbooking_uplist) if booking_data_notbooking_uplist else ""
        final_fwrd_normal_uplist = temp_uplist

        log(f"LOG {final_fwrd_normal_uplist}")
        # downlist
        lookup = Booking.query.filter_by(service_name=service_name).filter_by(branch_id=int(branch_id)).filter_by(
            serviced=False).filter_by(is_instant=False).filter_by(active=False).filter_by(nxt=1001).filter_by(
            forwarded=False).order_by(Booking.date_added.asc()).first()
        booking_data_notbooking_downlist = booking_schema.dump(lookup)

        fwrd = Booking.query.filter_by(branch_id=int(branch_id)).filter_by(serviced=False).filter_by(forwarded=True). \
            filter_by(active=False).filter_by(teller=teller_number).filter_by(nxt=1001).order_by(
            Booking.date_added.asc()).first()
        booking_data_fwrd_downlist = booking_schema.dump(fwrd)

        temp_downlink = list()
        temp_downlink.append(update_forwarded_data(booking_data_fwrd_downlist)) if booking_data_fwrd_downlist else ""
        temp_downlink.append(booking_data_notbooking_downlist) if booking_data_notbooking_downlist else ""
        final_fwrd_normal_downlist = temp_downlink

        final_list = final_fwrd_normal_downlist + final_fwrd_normal_uplist

        newlist = sorted(final_list, key=itemgetter('date_added'))

        # instant -> reset
        instant_uplist = Booking.query.filter_by(branch_id=branch_id).filter_by(service_name=service_name).filter_by(
            serviced=False).filter_by(active=False).filter_by(is_instant=True).filter_by(nxt=4004).filter_by(
            forwarded=False).filter(Booking.start != 99999999).order_by(Booking.date_added.asc()).first()
        booking_data_instant_uplist = booking_schema.dump(instant_uplist)

        # instant -> not reset
        instant_downlist = Booking.query.filter_by(branch_id=branch_id).filter_by(service_name=service_name).filter_by(
            serviced=False).filter_by(active=False).filter(Booking.start != 99999999).filter_by(
            is_instant=True).filter_by(nxt=1001).filter_by(
            forwarded=False).order_by(
            Booking.date_added.asc()).first()
        booking_data_instant_downlist = booking_schema.dump(instant_downlist)

        final_append = list()
        final_append.append(booking_data_instant_uplist) if booking_data_instant_uplist else ""
        final_append.append(booking_data_instant_downlist) if booking_data_instant_downlist else ""

        booking_data_instant = sorted(final_append, key=itemgetter('date_added'))

        booking_data = final_fwrd_normal_uplist_kick_back[0] if final_fwrd_normal_uplist_kick_back else (
            booking_data_instant[0] if booking_data_instant else (newlist[0] if newlist else {}))

        lst = list()
        if booking_data:
            # starting the booking timer for estimations
            # working with the service offered
            service_lookup = ServiceOffered.query.filter_by(name=booking_data["service_name"]).filter_by(
                branch_id=int(branch_id)).first()
            service_data = service_schema.dump(service_lookup)
            if not int(booking_data["user"]) == 0:
                lst = {
                    "service_name": booking_data["service_name"],
                    "start": booking_data["start"],
                    "ticket": f"{service_data['code']} {booking_data['kind']}",
                    "serviced": booking_data["serviced"],
                    "teller": booking_data["teller"],
                    "is_instant": booking_data["is_instant"],
                    "forwarded": booking_data["forwarded"],
                    "unique_id": booking_data["unique_id"]

                }
            else:
                lst = {
                    "service_name": booking_data["service_name"],
                    "start": booking_data["start"],
                    "ticket": f"{service_data['code']} {booking_data['ticket']}",
                    "serviced": booking_data["serviced"],
                    "teller": booking_data["teller"],
                    "is_instant": booking_data["is_instant"],
                    "forwarded": booking_data["forwarded"],
                    "unique_id": booking_data["unique_id"]

                }
        else:
            lst = {}
    else:
        lst = None

    # log(f"NEXTTTTTTTTT TICKET ... {lst}")
    return lst


def map_forwarded_booking(booking):
    data = TellerBooking.query.filter_by(booking_id=booking["id"]).order_by(TellerBooking.date_added.desc()).first()
    final = teller_booking_schema.dump(data)
    return final


def update_forwarded_data(booking):
    mapped = map_forwarded_booking(booking)
    if booking:
        if booking["forwarded"]:
            if mapped["pre_req"]:
                booking_date = mapped["date_added"]
                preq_teller = mapped["pre_req"]
                booking["teller"] = preq_teller
                booking["date_added"] = booking_date
            else:
                booking_date = mapped["date_added"]
                booking_date = mapped["date_added"]
                booking["date_added"] = booking_date
    return booking


def get_all_tellers(branch_id):
    lookup = Teller.query.filter_by(branch=branch_id).all()
    teller_data = tellers_schema.dump(lookup)
    return teller_data


def get_upcoming(teller_id, branch_id_):
    lookup = Teller.query.filter_by(number=teller_id).filter_by(branch=branch_id_).first()
    teller_data = teller_schema.dump(lookup)

    if teller_data:
        branch_id = teller_data["branch"]
        service_name = teller_data["service"]

        #  get next ticket
        next_ticket = get_next_ticket(teller_id, branch_id)
        log(f"next_ticket {next_ticket}")
        # final
        final = list()

        # kick back tickets
        instant_kickback = Booking.query.filter_by(branch_id=branch_id).filter_by(service_name=service_name). \
            filter_by(serviced=False).filter_by(active=False).filter_by(nxt=1001).filter(
            Booking.start == 99999999).filter_by(
            teller=0).filter_by(is_instant=True).order_by(Booking.date_added.asc()).all()
        bk_uplist_kickback = bookings_schema.dump(instant_kickback)

        # ticket that have been closed
        instant_kickback = Booking.query.filter_by(branch_id=branch_id).filter_by(serviced=False).filter_by(
            active=False).filter_by(nxt=4004).filter(Booking.start == 99999999).filter_by(
            teller=0).filter_by(is_instant=True).order_by(Booking.date_added.asc()).all()
        bk_downlist_kickback = bookings_schema.dump(instant_kickback)

        final_instant_kickback = sorted(bk_downlist_kickback + bk_uplist_kickback, key=itemgetter('date_added'))

        # instant
        # ticket not closed
        instant = Booking.query.filter_by(branch_id=branch_id).filter_by(service_name=service_name). \
            filter_by(serviced=False).filter_by(active=False).filter(Booking.start != 99999999).filter_by(
            nxt=1001).filter_by(teller=0).filter_by(is_instant=True).order_by(Booking.date_added.asc()).all()
        bk_uplist = bookings_schema.dump(instant)

        # ticket that have been closed
        instant = Booking.query.filter_by(branch_id=branch_id).filter_by(service_name=service_name). \
            filter_by(serviced=False).filter_by(active=False).filter(Booking.start != 99999999).filter_by(
            nxt=4004).filter_by(teller=0).filter_by(is_instant=True).order_by(Booking.date_added.asc()).all()
        bk_downlist = bookings_schema.dump(instant)

        final_instant = sorted(bk_downlist + bk_uplist, key=itemgetter('date_added'))

        # UPLIST
        # strt non instant
        # geting the none instant one first
        lookup_uplist = Booking.query.filter_by(branch_id=branch_id).filter_by(service_name=service_name). \
            filter_by(serviced=False).filter_by(active=False).filter_by(teller=0).filter_by(
            is_instant=False).filter_by(nxt=4004).order_by(Booking.date_added.asc()).all()
        booking_data_uplist = bookings_schema.dump(lookup_uplist)

        # forwarded
        forwared_uplist = Booking.query.filter_by(branch_id=branch_id).filter_by(serviced=False).filter_by(
            nxt=4004).filter_by(
            active=False).filter_by(teller=teller_id).filter_by(forwarded=True).order_by(
            Booking.date_added.asc()).all()
        fwrded_uplist = bookings_schema.dump(forwared_uplist)
        temp_uplist = list()
        for x in fwrded_uplist:
            updated = update_forwarded_data(x)
            temp_uplist.append(updated)

        final_list_uplist = sorted(booking_data_uplist + temp_uplist, key=itemgetter('date_added'))

        # DOWNLIST
        # strt non instant
        # geting the none instant one first
        lookup_downlist = Booking.query.filter_by(branch_id=branch_id).filter_by(service_name=service_name). \
            filter_by(serviced=False).filter_by(active=False).filter_by(teller=0).filter_by(
            is_instant=False).filter_by(nxt=1001).order_by(Booking.date_added.asc()).all()
        booking_data_downlist = bookings_schema.dump(lookup_downlist)

        # forwarded
        forwared_downlist = Booking.query.filter_by(branch_id=branch_id).filter_by(serviced=False).filter_by(
            nxt=1001).filter_by(
            active=False).filter_by(teller=teller_id).filter_by(forwarded=True).order_by(Booking.date_added.asc()).all()
        fwrded_downlist = bookings_schema.dump(forwared_downlist)
        temp_downlist = list()

        for x in fwrded_downlist:
            updated = update_forwarded_data(x)
            temp_downlist.append(updated)

        final_list_downlist = sorted(booking_data_downlist + temp_downlist, key=itemgetter('date_added'))

        final_up_down_list = final_list_uplist + final_list_downlist
        newlist_ = sorted(final_up_down_list, key=itemgetter('date_added'))
        newlist = final_instant_kickback + final_instant + newlist_

        for booking in newlist:
            service_lookup = ServiceOffered.query.filter_by(name=booking["service_name"]).filter_by(
                branch_id=branch_id).first()
            service_data = service_schema.dump(service_lookup)
            if booking:
                if not int(booking["user"]) == 0:
                    lst = {
                        "service_name": booking["service_name"],
                        "start": booking["start"],
                        "ticket": f"{service_data['code']} {booking['kind']}",
                        "serviced": booking["serviced"],
                        "teller": booking["teller"],
                        "is_instant": booking["is_instant"],
                        "forwarded": booking["forwarded"],
                        "unique_id": booking["unique_id"]
                    }
                else:
                    lst = {
                        "service_name": booking["service_name"],
                        "start": booking["start"],
                        "ticket": f"{service_data['code']} {booking['ticket']}",
                        "serviced": booking["serviced"],
                        "teller": booking["teller"],
                        "is_instant": booking["is_instant"],
                        "forwarded": booking["forwarded"],
                        "unique_id": booking["unique_id"]
                    }
            final.append(lst)
            if next_ticket:
                final = [x for x in final if not (next_ticket["unique_id"] == x.get('unique_id'))]
    else:
        final = list()
    return final


def ahead_of_me(service_name, branch_id):
    lookup = Booking.query.filter_by(service_name=service_name).filter_by(branch_id=branch_id).filter_by(
        nxt=1001).filter_by(serviced=False).all()
    booking_data = bookings_schema.dump(lookup)
    return len(booking_data)


def wait_time(service_name, branch_id):
    lookup = Booking.query.with_entities(Booking.start).filter_by(branch_id=branch_id).filter_by(
        service_name=service_name).all()
    booking_data = bookings_schema.dump(lookup)
    final = list()
    for booking in booking_data:
        final.append(datetime.strftime(booking["start"], '%Y-%m-%d %H:%M:%S.%f'))
    return final


def authenitcate():
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    r = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
    return r.text


def branch_is_medical(branch_id):
    branch_lookup = Branch.query.get(branch_id)
    branch_data = branch_schema.dump(branch_lookup)
    if branch_data:
        lookup = Service.query.filter_by(name=branch_data["service"]).first()
        service_data = service_.dump(lookup)
        if service_data["is_medical"]:
            service_data = True
        else:
            service_data = False
    else:
        service_data = None
    return service_data


def branch_is_active(branch_id):
    branch_lookup = Branch.query.get(branch_id)
    branch_data = branch_schema.dump(branch_lookup)
    if branch_data['key']:
        final = True
    else:
        final = False
    return final


def add_customer(email):
    lookup = Customer(email, secrets.token_hex())
    db.session.add(lookup)
    db.session.commit()

    return user_schema.dump(lookup)


def get_branch_tellers(branch_id):
    lookup = Teller.query.filter_by(branch=branch_id).all()
    lookup_data = tellers_schema.dump(lookup)
    return lookup_data


def get_active_tickets(branch_id):
    lookup = Booking.query.filter_by(branch_id=branch_id).filter_by(active=True).filter_by(nxt=1001).all()
    lookup_data = bookings_schema.dump(lookup)
    final_list = list()

    for item_ in lookup_data:
        final = dict()
        service_lookup_data = update_obj(item_)
        final.update(service_lookup_data)
        final.update(item_)
        final_list.append(final)
    return final_list


def get_active_tickets_no_limit(branch_id):
    lookup = Booking.query.filter_by(branch_id=branch_id).filter_by(active=True).filter_by(nxt=1001).all()
    lookup_data = bookings_schema.dump(lookup)
    final_list = list()
    for item_ in lookup_data:
        final = dict()
        service_lookup_data = update_obj(item_)
        final.update(service_lookup_data)
        final.update(item_)
        final_list.append(final)
    return final_list


def update_obj(indexer):
    service_lookup = ServiceOffered.query.filter_by(branch_id=indexer["branch_id"]).filter_by(
        name=indexer["service_name"]).first()
    service_lookup_data = service_schema.dump(service_lookup)
    return service_lookup_data


def save_icon_to_service(icon, name, branch):
    try:
        try:
            icon_ = bytes(icon, encoding='utf8')
            lookup = Icon(name, branch, icon_)
            db.session.add(lookup)
            db.session.commit()
            final = {"msg": "Icon added succesfully", "status": 201}
        except sqlalchemy.exc.DataError:
            final = {"msg": "Icon size too large", "status": 500}
    except sqlalchemy.exc.IntegrityError:
        final = {"msg": f"Icon \"{name}\" Already Exists", "status": 500}
    return final


def branch_exists(name):
    lookup = Branch.query.filter_by(name=name).first()
    return [1] if lookup else []


def sync_branch_data(name, company, longitude, latitude, opens, closes, service, description, key_, unique_id):
    if not branch_exists(name):
        lookup = Branch(name, company, longitude, latitude, opens, closes, service, description, key_, unique_id)
        try:
            db.session.add(lookup)
            db.session.commit()
            # emit the ack for flagging a branch;
            return dict()
        except sqlalchemy.exc.IntegrityError as e:
            return dict()
    else:
        return dict()


def get_comments(issue_id):
    lookup = TellerBooking.query.filter_by(booking_id=issue_id).all()
    lookup_data = teller_bookings_schema.dump(lookup)
    return lookup_data


def teller_exists(teller_number):
    lookup = Teller.query.filter_by(number=teller_number).first()
    teller_data = teller_schema.dump(lookup)
    return teller_data


def sync_company(name, service):
    lookup = Company(name, service)
    try:
        db.session.add(lookup)
        db.session.commit()
    except sqlalchemy.exc.IntegrityError:
        pass
    lookup_data = company_schema.dump(lookup)
    return lookup_data


def sync_category(name, service, is_medical):
    lookup = Service(name, service, is_medical)
    try:
        db.session.add(lookup)
        db.session.commit()
    except sqlalchemy.exc.IntegrityError:
        pass
    return service_schema.dump(lookup)


def charge(card_number, expiration_date, amount, merchant_id):
    return True
    # creditCard = apicontractsv1.creditCardType()
    # creditCard.cardNumber = card_number
    # creditCard.expirationDate = expiration_date
    #
    # payment = apicontractsv1.paymentType()
    # payment.creditCard = creditCard
    #
    # transactionrequest = apicontractsv1.transactionRequestType()
    # transactionrequest.transactionType = "authCaptureTransaction"
    # transactionrequest.amount = amount
    # transactionrequest.payment = payment
    #
    # createtransactionrequest = apicontractsv1.createTransactionRequest()
    # createtransactionrequest.merchantAuthentication = merchantAuth
    # createtransactionrequest.refId = merchant_id
    #
    # createtransactionrequest.transactionRequest = transactionrequest
    # createtransactioncontroller = createTransactionController(createtransactionrequest)
    # createtransactioncontroller.execute()
    #
    # response = createtransactioncontroller.getresponse()
    #
    # if (response.messages.resultCode == "Ok"):
    #     msg = (f"Transaction ID : {response.transactionResponse.transId}")
    # else:
    #     msg = (f"response code:{response.messages.resultCode}")
    # return msg


# the new charging methodology
def charge_():
    # start
    # Card Present
    config = ServicesConfig()
    config.site_id = '12345'
    config.license_id = '12345'
    config.device_id = '1234567'
    config.username = 'UserName'
    config.password = '$Password'
    config.developer_id = '000000'
    config.version_number = '0000'
    config.secret_api_key = '%%skapi_cert_MWI9AgD55mEA8nsiLmqtNhlHwxsNCcBrMZB4mRYLyw%%'
    config.service_url = 'https://cert.api2.heartlandportico.com'
    ServicesContainer.configure(config)
    # end
    card = CreditCardData()
    card.number = '4111111111111111'
    card.exp_month = '12'
    card.exp_year = '2025'
    card.cvn = '123'
    card.card_holder_name = 'Joe Smith'
    message = ""
    try:
        response = card.charge(10) \
            .with_currency('USD') \
            .execute()
        # response = card.charge(129.99) \
        #     .with_currency("EUR") \
        #     .execute()
        # result = response.response_code  # 00 == Success
        message = response.response_message  # [ test system ] AUTHORISED
    except ApiException as e:
        # // handle errors
        message = f"error! {e}"
        #     print("error", e)
        # except BuilderException as e:
        # # handle builder errors
        #     pass
        # except ConfigurationException as e:
        # # handle errors related to your services configuration
        #     pass
        # except GatewayException as e:
        # # handle gateway errors/exceptions
        #     pass
        # except UnsupportedTransactionException as e:
        # # handle errors when the configured gateway doesn't support
        # # desired transaction
        #     pass
        # except ApiException as e:
        #     pass
        return message


# handle all other errors


''' working with stripe payments'''

'''getting sync info. here we are going to get data from the database'''


def get_online_by_key(key):
    lookup = Branch.query.filter_by(key_=key).first()
    lookup_data = branch_schema.dump(lookup)
    return lookup_data


"""
:::::::::::::::::::::::::::
:::::WORKING WITH VIDEO::::
:::::::::::::::::::::::::::

"""

ALLOWED_EXTENSIONS_ = set(["mp4", "mkv", "flv", "webm"])


def allowed_files_(filename):
    return filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS_


# name.rsplit(".",1)[1] in ext

'''
encoding a base 64 string to mp4
'''


def final_html(message):
    return jsonify(message)


def upload_video():
    # check if the post request has the file part
    if 'file' not in request.files:
        return final_html("'No file part in the request")
    file = request.files['file']
    if file.filename == '':
        return final_html("No file selected for uploading")
    if file and allowed_files_(file.filename):
        try:
            # here wen need the file name
            filename = secure_filename(file.filename)

            # move the file to an appropiate location for play back

            # saving the video to the database
            video_lookup = Video(name=filename, type=1)
            db.session.add(video_lookup)
            db.session.commit()

            video_data = video_schema.dump(video_lookup)

            # do not save the file if there was an error
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # move the file to the appropriate location
            # try:
            #     time.sleep(10)
            #     move_video(file.filename)
            # except FileNotFoundError:
            #     return final_html("File Desination Error")

            return final_html("File successfully uploaded")
        except sqlalchemy.exc.IntegrityError:
            return final_html("Error! File by that name exists")
    else:
        return final_html("Allowed file types are mp4,flv,mkv")


def upload_link(link, type):
    """
    :param link:
    :param type:
    :return:
    """
    try:
        video_lookup = Video(name=link.strip(), type=type)
        db.session.add(video_lookup)
        db.session.commit()

        video_data = video_schema.dump(video_lookup)
        return final_html({"msg": "Link successfully uploaded"})
    except sqlalchemy.exc.IntegrityError:
        return final_html({"msg": "Error! File by that name exists"})


def validate_link(link):
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return {"valid": (re.match(regex, link) is not None)}


def save_mp4(data):
    random = secrets.token_hex(8)
    with open(f"{random}.mp4", "wb") as file:
        file.write(base64.b64encode(data))
        file.close()
        return ""
    return list()


def get_all_videos():
    lookup = Video.query.all()
    data = videos_schema.dump(lookup)
    return jsonify(data)


def get_single_video(id):
    lookup = Video.query.get(id)
    data = video_schema.dump(lookup)
    return data


def make_video_active(id):
    lookup = Video.query.get(id)
    lookup.active = 1
    db.session.commit()

    return video_schema.dump(lookup)


def make_video_inactive(id):
    lookup = Video.query.get(id)
    lookup.active = 0
    db.session.commit()

    return video_schema.dump(lookup)


def toggle_status(id):
    # get the video
    video = get_single_video(id)
    if video:
        final = make_video_inactive(video["id"]) if int(video["active"]) == 1 else make_video_active(video["id"])
    else:
        final = dict()
    return final


def get_active_videos():
    lookup = Video.query.filter_by(active=True).all()
    video_data = videos_schema.dump(lookup)
    new_list = [i.update({"link": app.config['UPLOAD_FOLDER']}) for i in video_data]
    return jsonify(video_data)


""":::::END:::::"""


def ticket_data(key, booking_id):
    branch_details = get_branch_by_key(key)
    if branch_details:
        service_name = branch_details["service"]
        branch_id = branch_details["id"]
        pple = ahead_of_you_id(booking_id) if ahead_of_you_id(booking_id)["msg"] > 0 else {"msg": 0}
        company = branch_details["company"]

        # icon
        booking_lookup = Booking.query.get(booking_id)
        booking_data = booking_schema.dump(booking_lookup)
        service_offered = booking_data["service_name"]

        # getting the average time for the service
        avg_time_ = avg_time(service_offered)
        log(F"AVG !!!{avg_time_}")
        # end_service = datetime.now() + timedelta(seconds=avg_time_) if pple else 00

        # service offered
        service_lookup = ServiceOffered.query.filter_by(name=service_offered).first()
        service_data = service_schema.dump(service_lookup)
        icon_id = service_data["icon"]

        # icon data
        icon_lookup = Icon.query.get(icon_id)
        icon_data = icon_schema.dump(icon_lookup)

        # code
        code = ""
        booking = get_booking(booking_id)
        if booking:
            branch = branch_exist(booking['branch_id'])
            service = service_exists(booking["service_name"], booking["branch_id"])
            if branch and service:
                code = service["code"] + booking["ticket"]
        final = {
            "ticket": code,
            "service_name": service_offered,
            "branch_name": branch_details['name'],
            "opens": branch_details["opens"],
            "closes": branch_details["closes"],
            "pple": int(pple["msg"]),
            "avg_time": seconds_to_min_sec(avg_time_),
            "company": company,
            # "approximate_end_time": f"{end_service.hour}:{end_service.minute}",
            "icon": icon_data["icon"],
            "today": datetime.now().strftime("%a, %d %b %y")
        }
    else:
        final = dict()
    print("----")
    log(final["avg_time"])
    return final


def get_booking_details(booking_id):
    booking_lookup = Booking.query.get(booking_id)
    booking_details = booking_schema.dump(booking_lookup)
    final = dict()
    if booking_details:
        icon_data = ServiceOffered.query.filter_by(name=booking_details["service_name"]).first()
        final.update(icon_data)
        final.update(booking_details)
    return final


def transpose_service(service):
    lookup = ServiceOffered.query.filter_by(name=service).first()
    return lookup


def last_five_booking_dates(service: str) -> list:
    service = transpose_service(service)
    if service:
        # get the las ten bookings
        lookup = BookingTimes.query.filter_by(service=service.unique_id).order_by(BookingTimes.date_added.desc()).all()
        data = booking_times.dump()
        log(data)
        date_list = list()
        final = list()
        if data:
            count = 0
            for booking in data:
                start = booking["start"]
                end = booking['end']
                print(booking["id"])
                count = count + 1
                if count == 5:
                    break
                if end is None:
                    continue
                # getting the date difference
                diff = datetime.fromisoformat(end) - datetime.fromisoformat(start)
                date_list.append(diff.seconds)
        else:
            date_list = list()
    else:
        date_list = list()
    return date_list


def avg_time(service):
    all_bkgs = last_five_booking_dates(service)
    log(f">>>>{all_bkgs}")
    avg = int()
    sum = int()
    for item in all_bkgs:
        sum = sum + item

    log(f"SUM {sum}")

    try:
        avg = sum / len(all_bkgs)
    except ZeroDivisionError:
        avg = 3 * 60

    log(f"AVG {avg}")
    return avg


def seconds_to_min_sec(seconds):
    import time
    h, m, s = (time.strftime('%H:%M:%S', time.gmtime(seconds))).split(":")
    print(h, "-", m, "-", s)
    return {"hours": h, "minutes": m, "seconds": s}


def init_ticket_timer(booking_id, service):
    try:
        service = transpose_service(service)
        if service:
            lookup = BookingTimes(int(booking_id), service.unique_id)
            db.session.add(lookup)
            db.session.commit()
            log(f"BOOKING TIME TIMER INIT {booking_time.dump(lookup)}")
        else:
            logging.error("Service name  - unique id transpose error.")
    except sqlalchemy.exc.IntegrityError:
        logging.error("Entry By That Name exists.")
    data = booking_time.dump(lookup)

    return data


def update_timestamp(id, end=""):
    try:
        if not end:
            lookup = BookingTimes(id)
            db.session.add(lookup)
            db.session.commit()
        else:
            lookup = BookingTimes.query.filter_by(booking_id=id).first()
            lookup.end = end
            db.session.commit()
    except Exception:
        pass
    return booking_time.dump(get_booking)


def ahead_of_you_id(booking_id):
    lookup = Booking.query.get(booking_id)
    lookup_data = booking_schema.dump(lookup)

    # teller service
    if lookup_data:
        all_bookings_ahead = Booking.query.filter(Booking.id < booking_id).filter_by(
            service_name=lookup.service_name).filter_by(serviced=False).filter_by(forwarded=False).filter_by(
            nxt=1001).all()
        booking_service = get_booking_service(booking_id)
        forwarded_tickets = max_booking_from_teller_of_same_service(lookup.service_name)
        final = {"msg": (forwarded_tickets + len(all_bookings_ahead))}
    else:
        final = {"msg": None}
    return final


def get_booking_service(booking_id):
    booking = Booking.query.get(int(booking_id))
    return booking.service_name


def max_booking_from_teller_of_same_service(service):
    tellers = Teller.query.filter_by(service=service).all()
    tellers_counts = list()
    for teller in tellers:
        bookings = get_bookings_forwarded_teller(teller.number)
        tellers_counts.append(len(bookings))
    return max(tellers_counts) if tellers else 0


def get_bookings_forwarded_teller(teller):
    bookings = Booking.query.filter_by(teller=teller).filter_by(forwarded=True).filter_by(serviced=False).filter_by(
        nxt=1001).all()
    return bookings


'''get issue count '''


def get_issue_count():
    data = db.session.execute("SELECT COUNT(*) AS issuesCount, DATE (date_added) AS issueDate FROM booking GROUP BY "
                              "issueDate LIMIT 15")
    return jsonify({'result': [dict(row) for row in data]})


def delete_video(video_id):
    vid = Video.query.get(int(video_id))
    db.session.delete(vid)
    db.session.commit()

    return video_schema.dump(vid)


def get_all_unsyced_bookings():
    offline = Booking.query.filter_by(is_synced=False).filter_by(user=0).all()
    offline_bookings = bookings_schema.dump(offline)
    return offline_bookings


def get_all_services_offered():
    services = ServiceOffered.query.filter_by(is_synced=False).all()
    data = services_schema.dump(services)
    return data


def get_all_tellers_sync():
    # getting teller data
    teller_lookup = Teller.query.filter_by(is_synced=False).all()
    teller_data = tellers_schema.dump(teller_lookup)
    return teller_data


# GET ALL BOOKING THAT ARE FORWARDED, SERVICED
def booking_status_with_unique():
    data = [dict(x) for x in db.session.execute("SELECT id, serviced,forwarded,unique_teller,unique_id FROM booking")]
    return data


# get all data offline to online
def get_sync_all_data(key):
    # get all booking
    bookings_to_sync = get_all_unsyced_bookings()
    services_to_sync = get_all_services_offered()
    tellers_to_sync = get_all_tellers_sync()
    bookings_status = booking_status_with_unique()
    verify_data = offline_verify(key)
    # return the data
    # "bookings_verify": bookings_status,
    final = {"bookings": bookings_to_sync, "services": services_to_sync, "tellers": tellers_to_sync,
             "bookings_verify": bookings_status, "key": key, "verify": verify_data}
    return final


def offline_verify(key):
    # get all booking
    bookings_count = len(Booking.query.all())
    services_count = len(ServiceOffered.query.all())
    tellers_count = len(Teller.query.all())
    synced_booking = len(Booking.query.filter_by(is_synced=False).all())
    serviced_bookings = len(Booking.query.filter_by(serviced=True).all())

    # return the data
    final = {"bookings": bookings_count,
             "services": services_count,
             "tellers": tellers_count,
             "synced": synced_booking,
             "serviced": serviced_bookings,
             "key": key}
    return final


# update date from online to offline
def update_sync_all_data(data):
    bookings = data["bookings"]
    key = data["key"]
    if branch_exists_key(key):
        # we can sync
        for booking in bookings:
            # check if booking exists
            if not booking_exists_unique(booking):
                # booking does not exists
                # add booking to the db
                # flag the booking as synced now
                id = booking["id"]
                service_name = booking["service_name"]
                start = booking["start"]
                branch_id = booking["branch_id"]
                ticket = booking["ticket"]  # replaces kind
                active = booking["active"]
                nxt = booking["nxt"]
                serviced = booking["serviced"]
                teller = booking["teller"]
                kind = booking["kind"]
                user = booking["user"]
                is_instant = booking["is_instant"]
                forwarded = booking["forwarded"]
                is_synced = booking["is_synced"]
                unique_id = booking["unique_id"]
                # adding data to the database
                create_booking(service_name, start, branch_id, bool(is_instant), user, unique_id, is_synced)
            else:
                # booking exists
                flag_booking_as_synced(booking)
    return dict()


def booking_exists_unique(data):
    booking = Booking.query.filter_by(unique_id=data["unique_id"]).first()
    if booking:
        branch = Branch.query.get(booking.branch_id)
        booking.key_ = branch.key_

    return booking


def service_exists_unique_(data):
    booking = dict()
    if data:
        booking = ServiceOffered.query.filter_by(unique_id=data).first()
    return booking


def teller_exists_unique_(data):
    teller = Teller.query.filter_by(unique_id=data["unique_id"]).first()
    return teller


def booking_is_acked(unique_id):
    booking = Booking.query.filter_by(unique_id=unique_id).first()
    return bool(booking.is_synced)


def service_is_acked(unique_id):
    booking = ServiceOffered.query.filter_by(unique_id=unique_id).first()
    return bool(booking.is_synced)


def flag_booking_as_synced(data):
    booking = booking_exists_unique(data)
    if booking:
        if not booking_is_acked(booking.unique_id):
            booking.is_synced = True
            db.session.commit()
            log(f"ack_successful_enitity {data}")
    return booking


def flag_service_as_synced(data):
    service = service_exists_unique_(data)
    if service:
        if not service_is_acked(service.unique_id):
            service.is_synced = True
            db.session.commit()
    return service


def teller_is_synced(unique):
    teller = Teller.query.filter_by(unique_id=unique).first()
    return bool(teller.is_synced)


def flag_teller_as_synced(data):
    teller = teller_exists_unique_(data)
    if teller:
        if not teller_is_synced(teller.unique_id):
            teller.is_synced = True
            db.session.commit()
    return data


def reset_ticket_counter():
    lookup = Booking.query.all()
    for booking in lookup:
        booking.nxt = 4004
        db.session.commit()
    return jsonify(bookings_schema.dump(lookup))


def branch_exists_key(key):
    lookup = Branch.query.filter_by(key_=key).first()
    return lookup


def create_booking_online(service_name, start, branch_id_, is_instant=False, user=0, kind=0, key="",
                          unique_id="", is_synced="", verify=""):
    data_ = update_branch_offline(key)
    branch_id = data_["id"] if data_ else 1
    if branch_is_medical(branch_id):
        if service_exists(service_name, branch_id):
            # get the service
            data = service_exists(service_name, branch_id)
            name = data["name"]
            if ticket_queue(service_name, branch_id):
                book = ticket_queue(service_name, branch_id)
                last_ticket_number = book["ticket"]
                next_ticket = int(last_ticket_number) + 1
                final = make_booking_online(name, start, branch_id, next_ticket, instant=False, user=user, kind=kind,
                                            unique_id=unique_id, is_synced=is_synced, verify=verify)
            else:
                # we are making the first booking for this category
                # we are going to make this ticket  active
                next_ticket = 1
                final = make_booking_online(name, start, branch_id, next_ticket, active=False, instant=False, user=user,
                                            kind=kind, unique_id=unique_id, is_synced=is_synced, verify=verify)
        else:
            final = None
            raise ValueError(f"Service {service_name}Does Not Exist. Please Add Service first")
    else:
        if service_exists(service_name, branch_id):
            # get the service
            data = service_exists(service_name, branch_id)
            name = data["name"]
            if ticket_queue(service_name, branch_id):
                book = ticket_queue(service_name, branch_id)
                last_ticket_number = book["ticket"]
                next_ticket = int(last_ticket_number) + 1
                final = make_booking_online(name, start, branch_id, next_ticket, instant=is_instant, user=user,
                                            kind=kind,
                                            is_synced=is_synced, unique_id=unique_id, verify=verify)
            else:
                # we are making the first booking for this category
                # we are going to make this ticket  active
                next_ticket = 1
                final = make_booking_online(name, start, branch_id, next_ticket, active=False, instant=is_instant,
                                            user=user,
                                            kind=kind, is_synced=is_synced, unique_id=unique_id, verify=verify)
        else:
            final = None
            raise ValueError(f"Service {service_name} Does Not Exist. Please Add Service first")

    return final


def log(msg):
    print(f"{datetime.now().strftime('%d:%m:%Y %H:%M:%S')} — {msg}")
    return True


def ack_teller_success(data):
    # flag as sycned here based on unique key
    return flag_teller_as_synced(data)


def ack_service_success(data):
    # flag as sycned here based on unique key
    return flag_service_as_synced(data)


def ack_booking_success(data):
    return flag_booking_as_synced(data)


def teller_exists_unique(unique_id):
    return Teller.query.filter_by(unique_id=unique_id).first()


def service_exists_unique(unique_id):
    return ServiceOffered.query.filter_by(unique_id=unique_id).first()


def is_this_branch(key):
    return branch_exists_key(key)


def get_all_branches():
    branches = Branch.query.all()
    return branches


# booking_exists_unique(data):

def booking_by_unique(unique_id):
    lookup = Booking.query.filter_by(unique_id=unique_id).first()
    final = dict()
    if lookup:
        branch = Branch.query.get(lookup.branch_id)
        final = booking_schema.dump(lookup)
        final.update({"key_": branch.key_})

    # booking not found we bneed to seek sync
    return final


def branch_exists_id(id):
    return Branch.query.get(id)


def booking_forwarded_count(branch_id):
    return len(booking_forwarded_all(branch_id))


def booking_serviced_count(branch_id):
    return len(booking_serviced_all(branch_id))


def booking_all_count(branch_id):
    return len(booking_clean_all(branch_id))


def booking_forwarded_all(branch_id):
    booking = Booking.query.filter_by(nxt=1001).filter_by(forwarded=True).filter_by(serviced=False).filter_by(
        branch_id=branch_id).all()
    return bookings_schema.dump(booking)


def booking_serviced_all(branch_id):
    booking = Booking.query.filter_by(nxt=1001).filter_by(forwarded=False).filter_by(serviced=True).filter_by(
        branch_id=branch_id).all()
    return bookings_schema.dump(booking)


def booking_clean_all(branch_id):
    booking = Booking.query.filter_by(nxt=1001).filter_by(forwarded=False).filter_by(serviced=False).filter_by(
        branch_id=branch_id).all()
    return bookings_schema.dump(booking)


def sync_2_offline(branch_id):
    data_fowarded_count = booking_forwarded_count(branch_id)
    data_serviced_count = booking_serviced_count(branch_id)
    data_clean_count = booking_all_count(branch_id)
    data_fowarded_data = booking_forwarded_all(branch_id)
    data_serviced_data = booking_serviced_all(branch_id)
    data_clean_data = booking_clean_all(branch_id)

    branch = branch_by_id(branch_id)

    return {
        "forwarded": {
            "count": data_fowarded_count,
            "bookings": data_fowarded_data
        },
        "serviced": {
            "count": data_serviced_count,
            "bookings": data_serviced_data
        },
        "clean": {
            "count": data_clean_count,
            "bookings": data_clean_data
        },
        "key_": branch["key_"]
    }


def this_branch():
    branch = Branch.query.first()
    final = branch_schema.dump(branch)
    today = datetime.now()
    final["today"] = today.strftime(f"%A, %d{date_suffix(today.day)} %B %Y")
    return final


def date_suffix(day):
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]
    return suffix


"""Dept functions """


def add_dept(name):
    final = False
    if not get_dept_by_name(name):
        branch = Branch.query.first()
        lookup = Department(name, branch.unique_id)
        db.session.add(lookup)
        db.session.commit()
        final = department_schema.dump(lookup)
    return final


def dept_by_unique_id(unique_id):
    return Department.query.filter_by(unique_id=unique_id).first()


def get_dept_by_name(name):
    return Department.query.filter_by(name=name).first()


def bind_service_to_dept(service_unique_id, name):
    final = False
    dept = get_dept_by_name(name=name)
    if service_unique_id(service_unique_id) and dept:
        if dept_by_unique_id(name.unique_id):
            lookup = DepartmentService(dept.unique_id, service_unique_id)
            db.session.add(lookup)
            db.session.commit()
            final = department_service_schema.dump(lookup)
    return final


def unbind_dept_to_service(service_unique_id, dept_unique_id):
    final = False
    bond = service_dept_bind_exists(service_unique_id, dept_unique_id)
    if bond:
        db.session.delete(bond)
        db.session.commit()
        final = True
    return final


def service_dept_bind_exists(service_unique_id, dept_unique_id):
    return DepartmentService.query.filter_by(department_id=dept_unique_id).filter_by(
        service_id=service_unique_id).first()


def service_by_name(name):
    return ServiceOffered.query.filter_by(name=name).first()


def service_by_unique_id(unique_id):
    return ServiceOffered.query.filter_by(unique_id=unique_id).first()
