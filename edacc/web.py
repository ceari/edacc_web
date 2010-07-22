# -*- coding: utf-8 -*-

from flask import Flask, Request
app = Flask(__name__)

from edacc import config, models
app.Debug = config.DEBUG
  
if config.LOGGING:
    import logging
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(config.LOG_FILE)
    file_handler.setLevel(logging.WARNING)
    app.logger.addHandler(file_handler)
    
for db in config.DEFAULT_DATABASES:
    models.add_database(db[0], db[1], db[2], db[3])
    
class LimitedRequest(Request):
    """ extending Flask's request class to limit form uploads """
    max_form_memory_size = 16 * 1024 * 1024 # limit form uploads to 16 MB
app.request_class = LimitedRequest

app.secret_key = config.SECRET_KEY

from edacc.views.admin import admin
from edacc.views.accounts import accounts
from edacc.views.frontend import frontend

app.register_module(admin)
app.register_module(accounts)
app.register_module(frontend)