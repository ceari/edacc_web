# -*- coding: utf-8 -*-
"""
    edacc.views.helpers
    -------------------

    Various helper functions, decorators and before- and
    after-request-callbacks.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""



import hashlib
from functools import wraps

from flask import abort, session, url_for, redirect, g, request, flash
import pbkdf2

from edacc import config, models, config

# decorates a decorator function to be able to specify parameters :-)
decorator_with_args = lambda decorator: lambda *args, **kwargs:\
                      lambda func: decorator(func, *args, **kwargs)


def require_admin(f):
    """ View function decorator that checks if the current user is an admin and
        raises a 401 response if not.
    """
    @wraps(f)
    def decorated_f(*args, **kwargs):
        if not session.get('admin', False):
            def redirect_f(*args, **kwargs):
                return redirect(url_for('admin.admin_login'))
            return redirect_f(*args, **kwargs)
        return f(*args, **kwargs)
    return decorated_f


def redirect_ssl(f):
    @wraps(f)
    def decorated_f(*args, **kwargs):
        if request.url.startswith('http://') and not config.DEBUG and config.ENABLE_SSL:
            def redirect_f(*args, **kwargs):
                return redirect('https://' + request.url[7:])
            return redirect_f(*args, **kwargs)
        else:
            return f(*args, **kwargs)
    return decorated_f


def is_admin():
    """ Returns true if the current user is logged in as admin. """
    return session.get('admin', False)


@decorator_with_args
def require_phase(f, phases):
    """ View function decorator only allowing access if the database is no
        competition database or the phase of the competition matches one of
        the phases passed in the iterable argument `phases`.
    """
    @wraps(f)
    def decorated_f(*args, **kwargs):
        db = models.get_database(kwargs['database']) or abort(404)
        if db.is_competition() and not is_admin() and db.competition_phase() not in phases:
            abort(403)
        return f(*args, **kwargs)
    return decorated_f


def require_competition(f):
    """ View function decorator only allowing access if the database is
        a competition database.
    """
    @wraps(f)
    def decorated_f(*args, **kwargs):
        db = models.get_database(kwargs['database']) or abort(404)
        if not db.is_competition():
            abort(404)
        return f(*args, **kwargs)
    return decorated_f


def require_login(f):
    """ View function decorator that checks if the user is logged in to
        the database specified by the route parameter <database> which gets
        passed in **kwargs. Only checked for competition databases and only if
        the competition phase is < 7 (no public access).
    """
    @wraps(f)
    def decorated_f(*args, **kwargs):
        db = models.get_database(kwargs['database']) or abort(404)

        if session.get('logged_in'):
            g.User = db.session.query(db.User).get(session['idUser'])
            if g.User.admin: session['admin'] = True
        else:
            g.User = None

        if db.is_competition() and db.competition_phase() == 7:
            session.pop('logged_in', None)
            session.pop('idUser', None)
            g.User = None

#        if db.is_competition() and db.competition_phase() == 5:
#            def redirect_f(*args, **kwargs):
#                return redirect(url_for('frontend.experiments_index',
#                database=kwargs['database']))
#            if not g.User or not g.User.admin:
#                session.pop('logged_in', None)
#                flash('Website offline for competition computations.')
#                return redirect_f(*args, **kwargs)

        if db.is_competition() and db.competition_phase() < 7:
            def redirect_f(*args, **kwargs):
                return redirect(url_for('accounts.login',
                    database=kwargs['database']))

            if not g.User or not session.get('logged_in') or \
                session.get('idUser', None) is None:
                return redirect_f(*args, **kwargs)
            if session.get('database') != kwargs['database']:
                return redirect_f(*args, **kwargs)

        return f(*args, **kwargs)
    return decorated_f


def password_hash(password):
    """ Returns a cryptographic hash of the given password salted with
        SECRET_KEY as hexstring.
    """
    return pbkdf2.crypt(config.SECRET_KEY + password, iterations=10000)
