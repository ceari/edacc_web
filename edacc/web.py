# -*- coding: utf-8 -*-
"""
    edacc.web
    ---------

    In this module the flask application instance is defined and configured
    according to the settings in config.py.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

import uuid, datetime, os

from jinja2 import FileSystemBytecodeCache
from werkzeug import ImmutableDict
from flask import Flask, Request, g, Blueprint
from flask.ext.cache import Cache
from flask.ext.mail import Mail
from simplekv.fs import FilesystemStore
from flask.ext.kvsession import KVSessionExtension
from edacc import config, models, utils

try:
    os.makedirs(config.TEMP_DIR)
except OSError:
    pass

Flask.jinja_options = ImmutableDict({
    'extensions': ['jinja2.ext.autoescape', 'jinja2.ext.with_'],
    'bytecode_cache': FileSystemBytecodeCache(config.TEMP_DIR),
    'trim_blocks': True
})
app = Flask(__name__)
app.Debug = config.DEBUG
cache = Cache()
mail = Mail()
#session_store = FilesystemStore(config.TEMP_DIR, perm=0600)

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
    """ extending Flask's request class to limit form uploads to 500 MB """
    max_form_memory_size = 500 * 1024 * 1024


app.request_class = LimitedRequest
app.config.update(
    SECRET_KEY=config.SECRET_KEY,
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=14),
    CACHE_TYPE='filesystem',
    CACHE_DIR=config.TEMP_DIR,
    MAIL_SERVER=config.MAIL_SERVER,
    MAIL_PORT=config.MAIL_PORT,
    MAIL_USE_TLS=config.MAIL_USE_TLS,
    MAIL_USE_SSL=config.MAIL_USE_SSL,
    MAIL_USERNAME=config.MAIL_USERNAME,
    MAIL_PASSWORD=config.MAIL_PASSWORD,
    DEFAULT_MAIL_SENDER=config.DEFAULT_MAIL_SENDER
)
cache.init_app(app)
mail.init_app(app)
#KVSessionExtension(session_store, app)

# register view modules
from edacc.views.admin import admin
from edacc.views.accounts import accounts
from edacc.views.frontend import frontend
from edacc.views.analysis import analysis
from edacc.views.plot import plot
from edacc.views.api import api

app.register_blueprint(admin)
app.register_blueprint(accounts)
app.register_blueprint(frontend)
app.register_blueprint(analysis)
app.register_blueprint(plot)
app.register_blueprint(api)

from edacc.plugins.borgexplorer import borgexplorer

app.register_blueprint(borgexplorer)

app.jinja_env.filters['download_size'] = utils.download_size
app.jinja_env.filters['job_status_color'] = utils.job_status_color
app.jinja_env.filters['job_result_code_color'] = utils.job_result_code_color
app.jinja_env.filters['launch_command'] = utils.launch_command
app.jinja_env.filters['datetimeformat'] = utils.datetimeformat
app.jinja_env.filters['competition_phase'] = utils.competition_phase
app.jinja_env.filters['result_time'] = utils.result_time
app.jinja_env.filters['render_formula'] = utils.render_formula
app.jinja_env.filters['truncate_name'] = utils.truncate_name
app.jinja_env.filters['parameter_template'] = utils.parameter_template

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
