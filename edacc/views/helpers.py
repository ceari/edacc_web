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

from flask import abort, session, url_for, redirect, g

from edacc import config, models

# decorates a decorator function to be able to specify parameters :-)
decorator_with_args = lambda decorator: lambda *args, **kwargs:\
                      lambda func: decorator(func, *args, **kwargs)


def require_admin(f):
    """ View function decorator that checks if the current user is an admin and
        raises a 401 response if not.
    """
    @wraps(f)
    def decorated_f(*args, **kwargs):
        if not session.get('admin'):
            abort(401)
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
        if db.is_competition() and db.competition_phase() not in phases:
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

        if session.get('logged_in') and session.get('idUser', None) is not None:
            g.User = db.session.query(db.User).get(session['idUser'])
        else:
            g.User = None

        if db.is_competition() and db.competition_phase() < 7:
            def redirect_f(*args, **kwargs):
                return redirect(url_for('accounts.login',
                                        database=kwargs['database']))

            if not session.get('logged_in') or \
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
    hash = hashlib.sha256()
    hash.update(config.SECRET_KEY)
    hash.update(password)
    return hash.hexdigest()
