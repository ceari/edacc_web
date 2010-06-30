from flask import Flask
app = Flask(__name__)

import edacc.views
from edacc.config import DEBUG
app.Debug = DEBUG
