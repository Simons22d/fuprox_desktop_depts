# import the Flask Framework
from flask import Flask, jsonify, make_response, request
import requests
import secrets

app = Flask(__name__)


# You may create a separate URL for every endpoint you need

@app.route('/mpesa/b2c/v1', methods=["POST"])
def listenb2c():
    print("we got hit")
    # save the data
    request_data = request.data
    # Perform your processing here e.g. print it out...
    requests.post("http://localhost:1000/payments/status", json={"payment_info": f"'{request_data.decode()}'"})
    # Prepare the response, assuming no errors have occurred. Any response
    # other than a 0 (zero) for the 'ResultCode' during Validation only means
    # an error occurred and the transaction is cancelled
    message = {
        "ResultCode": 0,
        "ResultDesc": "The service was accepted successfully",
        "ThirdPartyTransID": secrets.token_hex()
    }
    # Send the response back to the server
    return jsonify({'message': message}), 200


# Change this part to reflect the API you are testing
@app.route('/mpesa/b2b/v1')
def listenb2b():
    request_data = request.data
    print(request_data)
    message = {
        "ResultCode": 0,
        "ResultDesc": "The service was accepted successfully",
        "ThirdPartyTransID": "1234567890"
    }
    return message


if __name__ == '__main__':
    app.run(debug=True, port="8080")
