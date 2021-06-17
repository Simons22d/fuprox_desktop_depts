import requests
from requests.auth import HTTPBasicAuth
from base64 import b64encode
from datetime import datetime

consumer_key = "vK3FkmwDOHAcX8UPt1Ek0njU9iE5plHG"
consumer_secret = "vqB3jnDyqP1umewH"


def authenticate():
    """
    :return: MPESA_TOKEN
    """
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
    return response.text


def stk_push(token, business_shortcode, lipa_na_mpesapasskey, amount, party_a, party_b, phonenumber,
             callbackurl):
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    headers = {"Authorization": "Bearer %s" % token}
    timestamp = datetime.now().strftime("%Y%m%d%I%M%S")
    pswd = (business_shortcode + lipa_na_mpesapasskey + timestamp).encode("utf-8")
    password = b64encode(pswd).decode()

    req = {
        "BusinessShortCode": "174379",
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": party_a,
        "PartyB": business_shortcode,
        "PhoneNumber": phonenumber,
        "CallBackURL": callbackurl,
        "AccountReference": business_shortcode,
        "TransactionDesc": "test"
    }
    response = requests.post(api_url, json=req, headers=headers)
    return response


# working with business to customer requests
def business_to_customer(access_token, initiator_name, security_credential, command_id, amount, party_a, party_b,
                         remarks, timeout_url, result_url):
    """

    :param access_token:
    :param initiator_name: 	This is the credential/username used to authenticate the transaction request.
    :param security_credential: Base64 encoded string of the B2C short code and password, which is encrypted using M-Pesa public key and validates the transaction on M-Pesa Core system.
    :param command_id: Unique command for each transaction type e.g. SalaryPayment, BusinessPayment, PromotionPayment
    :param amount:
    :param party_a: Organization’s short code initiating the transaction.
    :param party_b: Phone number receiving the transaction
    :param remarks: Comments that are sent along with the transaction.
    :param timeout_url:
    :param result_url:
    :return:
    """

    api_url = "https://sandbox.safaricom.co.ke/mpesa/b2c/v1/paymentrequest"
    headers = {"Authorization": "Bearer %s" % access_token}
    request = {
        "InitiatorName": initiator_name,
        "SecurityCredential": security_credential,
        "CommandID": command_id,
        "Amount": amount,
        "PartyA": party_a,
        "PartyB": party_b,
        "Remarks": remarks,
        "QueueTimeOutURL": timeout_url,
        "ResultURL": result_url,
        "Occasion": f"{remarks}."
    }

    response = requests.post(api_url, json=request, headers=headers)
    print(response.text)
    return response


def reverse(access_token, initiator, security_credential, transaction_id, amount, receiver_party, remarks, result_url,
            timeout_url):
    """
    :param access_token:
    :param initiator: This is the credential/username used to authenticate the transaction request.
    :param security_credential: Base64 encoded string of the M-Pesa short code and password, which is encrypted using M-Pesa public key and validates the transaction on M-Pesa Core system.
    :param transaction_id: Organization Receiving the funds.
    :param amount:
    :param receiver_party:
    :param remarks: comment to be sent with the transaction
    :param result_url:
    :param timeout_url:
    :return :
    """
    api_url = "https://sandbox.safaricom.co.ke/mpesa/reversal/v1/request"
    headers = {"Authorization": "Bearer %s" % access_token}
    request = {
               "Initiator": initiator,  # test_api
               "SecurityCredential": security_credential,
               "CommandID": "TransactionReversal",
               "TransactionID": transaction_id,  # this will be the mpesa code 0GE51H9MBP
               "Amount": amount,  # this has to be the exact amount
               "ReceiverParty": receiver_party,
               "RecieverIdentifierType": "11",  # was 4
               "ResultURL": result_url,
               "QueueTimeOutURL": timeout_url,
               "Remarks": f"{remarks}.",
               "Occasion": "Reverse_Cash"
            }

    response = requests.post(api_url, json=request, headers=headers)
    print(response.text)
    return response.text


def transaction_status(access_token, initiator, security_credential, transaction_id, party_a, result_url, timeout_url,
                       remarks, occasion):
    """
    :param access_token: <token>
    :param initiator:  the sender (initiator)
    :param security_credential:
    :param transaction_id: organization receiving funds #NGE41H9MBO
    :param party_a: #>>???
    :param result_url: ur to save transaction info
    :param timeout_url: url for timeouts
    :param remarks: comments sent with the transaction
    :param occasion: optional
    :return:
    """

    api_url = "https://sandbox.safaricom.co.ke/mpesa/transactionstatus/v1/query"
    headers = {"Authorization": "Bearer %s" % access_token}
    request = {
        "Initiator": initiator,
        "SecurityCredential": security_credential,
        "CommandID": "TransactionStatusQuery",
        "TransactionID": transaction_id,  # NGE41H9MBO
        "PartyA": party_a,
        "IdentifierType": "4",
        "ResultURL": result_url,
        "QueueTimeOutURL": timeout_url,
        "Remarks": f"{remarks}.",
        "Occasion": occasion
    }

    response = requests.post(api_url, json=request, headers=headers)

    print(response.text)
    return response.text
