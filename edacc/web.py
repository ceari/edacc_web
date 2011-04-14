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

from jinja2 import FileSystemBytecodeCache
from werkzeug import ImmutableDict
from flask import Flask, Request, g
from edacc import config, models, utils

Flask.jinja_options = ImmutableDict({
                            'extensions': ['jinja2.ext.autoescape', 'jinja2.ext.with_'],
                            'bytecode_cache': FileSystemBytecodeCache(config.TEMP_DIR),
                            'trim_blocks':True
})
app = Flask(__name__)
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
for username, password, database, label, hidden in config.DEFAULT_DATABASES:
    models.add_database(username, password, database, label, hidden)


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
from edacc.views.api import api

app.register_module(admin)
app.register_module(accounts)
app.register_module(frontend)
app.register_module(analysis)
app.register_module(plot)
app.register_module(api)

app.jinja_env.filters['download_size'] = utils.download_size
app.jinja_env.filters['job_status_color'] = utils.job_status_color
app.jinja_env.filters['job_result_code_color'] = utils.job_result_code_color
app.jinja_env.filters['launch_command'] = utils.launch_command
app.jinja_env.filters['datetimeformat'] = utils.datetimeformat
app.jinja_env.filters['competition_phase'] = utils.competition_phase
app.jinja_env.filters['result_time'] = utils.result_time
app.jinja_env.filters['render_formula'] = utils.render_formula

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
