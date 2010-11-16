# -*- coding: utf-8 -*-
"""
    edacc.web
    ---------

    In this module the flask application instance is defined and configured
    according to the settings in config.py.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

import uuid, datetime

from flask import Flask, Request, g
app = Flask(__name__)

from edacc import config, models
app.Debug = config.DEBUG

if config.LOGGING:
    # set up logging if configured
    import logging
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(config.LOG_FILE)
    file_handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("---------------------------\n" + \
                                  "%(asctime)s - %(name)s - " + \
                                  "%(levelname)s\n%(message)s")
    file_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)

# initialize configured database connections
for username, password, database, label in config.DEFAULT_DATABASES:
    models.add_database(username, password, database, label)


class LimitedRequest(Request):
    """ extending Flask's request class to limit form uploads to 100 MB """
    max_form_memory_size = 100 * 1024 * 1024

app.request_class = LimitedRequest
app.config.update(
    SECRET_KEY = config.SECRET_KEY,
    PERMANENT_SESSION_LIFETIME = datetime.timedelta(days=1)
)

# register view modules
from edacc.views.admin import admin
from edacc.views.accounts import accounts
from edacc.views.frontend import frontend
from edacc.views.analysis import analysis
from edacc.views.plot import plot

app.register_module(admin)
app.register_module(accounts)
app.register_module(frontend)
app.register_module(analysis)
app.register_module(plot)


if config.PIWIK:
    @app.before_request
    def register_piwik():
        """ Attach piwik URL to g """
        g.PIWIK_URL = config.PIWIK_URL


@app.before_request
def make_unique_id():
    """ Attach an unique ID to the request """
    g.unique_id = uuid.uuid4().hex


@app.after_request
def shutdown_session(response):
    """ remove SQLAlchemy session from thread after requests - might not even be needed for
    non-declarative SQLAlchemy usage according to the SQLAlchemy documentation.
    """
    for db in models.get_databases().itervalues():
        db.session.remove()
    return response
