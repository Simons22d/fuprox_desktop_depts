from flask import Flask
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_marshmallow import Marshmallow
from flask_sqlalchemy import SQLAlchemy, sqlalchemy
from flask_migrate import Migrate
import os
import logging

# load dotenv
from dotenv import load_dotenv

#  init()
load_dotenv()
db_user = os.getenv("DBUSER")
db_pass = os.getenv("DBPASS")
db_host = os.getenv("DBHOST")
db = os.getenv("DB")

# flask_app
app = Flask(__name__)

# making sure there is no browser caching
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# init cors
CORS(app)

# home directory 
from pathlib import Path

home = str(Path.home())
current_dir = os.getcwd()

# making the directory for the files
os.chdir(home)

# mkdir 
# check if home dir exists
if not os.path.exists(f"{home}/noqueue/uploads"):
    try:
        upload_path = os.path.join(home, "noqueue", "uploads")
        new_dir = Path(upload_path)
        new_dir.mkdir(parents=True)
    except OSError:
        logging.info("error Creating dir")

# move back to the current working DIR
os.chdir(current_dir)

'''
    SQLALCHEMY_NATIVE_UNICODE
    SQLALCHEMY_POOL_SIZE
    SQLALCHEMY_POOL_TIMEOUT
    SQLALCHEMY_POOL_RECYCLE
    SQLALCHEMY_MAX_OVERFLOW
'''

app.config['SQLALCHEMY_POOL_RECYCLE'] = 10
app.config['SQLALCHEMY_NATIVE_UNICODE'] = 20
app.config['SQLALCHEMY_MAX_OVERFLOW'] = 1000
app.config['SQLALCHEMY_POOL_SIZE'] = 1000
app.config["SQLALCHEMY_POOL_TIMEOUT"] = 5
app.config['MAX_CONTENT_LENGTH'] = 2048 * 1024 * 1024
app.config["SQLALCHEMY_DATABASE_URI"] = f"mysql+mysqlconnector://{db_user}:{db_pass}@{db_host}:3306/{db}"

# app.config["SQLALCHEMY_DATABASE_URI"] = f"postgresql://{db_user}:{db_pass}@localhost/fuprox"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['UPLOAD_FOLDER'] = f"{home}/noqueue/uploads"

# setting the jwt key
bcrypt = Bcrypt(app)

try:
    db = SQLAlchemy(app,session_options={"expire_on_commit": True})
    m = Migrate(app, db)
    ma = Marshmallow(app)
except sqlalchemy.exc.ProgrammingError as e:
    print("error", e)



# here we are going to import routes
from fuprox.routes.routes import *
from fuprox.models.models import *


@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()
