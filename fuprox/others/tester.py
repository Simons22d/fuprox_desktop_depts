import requests
from requests.auth import HTTPBasicAuth
from base64 import b64encode
from datetime import datetime
import json

#  -----

consumer_key = "p2hOMdhG0T7DDO0MWJvEGsVCyRCvjA3W"
consumer_secret = "Y2uGAIARwnJhB342"



api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
response = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
print("response text >>>> ",response.text)


#  stk push
# ----------------


phonenumber = "0719573310"
token_data = response.text
token = json.loads(token_data)["access_token"]
business_shortcode = "174379"
lipa_na_mpesapasskey = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
amount = 10
party_b = business_shortcode
callback_url = "http://66113442626e.ngrok.io/mpesa/b2c/v1"

print("token>>>>",token)


api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
headers = {"Authorization": "Bearer %s" % token}
timestamp = datetime.now().strftime("%Y%m%d%I%M%S")
pswd = (business_shortcode + lipa_na_mpesapasskey + timestamp).encode("utf-8")
password = b64encode(pswd).decode()



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
    "PartyA": phonenumber,
    "PartyB": business_shortcode,
    "PhoneNumber": phonenumber,
    "CallBackURL": callback_url,
    "AccountReference": business_shortcode,
    "TransactionDesc": "test"
}
response = requests.post(api_url, json=req, headers=headers)
print("response text >>>>>",response)


