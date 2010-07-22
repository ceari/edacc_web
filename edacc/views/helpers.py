import hashlib, time
from functools import wraps

from flask import abort, request, session, url_for, redirect

from edacc import config, utils, models
from edacc.web import app
from edacc.models import joinedload, joinedload_all
from edacc.constants import JOB_FINISHED, JOB_ERROR

# decorates a decorator function to be able to parameterize the decorator
decorator_with_args = lambda decorator: lambda *args, **kwargs: lambda func: decorator(func, *args, **kwargs)

@app.before_request
def make_unique_id():
    """ Attach an unique ID to the request (hash of current server time and request headers) """
    hash = hashlib.md5()
    hash.update(str(time.time()) + str(request.headers))
    request.unique_id = hash.hexdigest()
    
def require_admin(f):
    """ View function decorator that checks if the current user is an admin and
        raises a 401 response if not """
    @wraps(f)
    def decorated_f(*args, **kwargs):
        if not session.get('admin'): abort(401)
        return f(*args, **kwargs)
    return decorated_f

def is_admin():
    """ Returns true if the current user is logged in as admin """
    return session.get('admin', False)

@decorator_with_args
def require_phase(f, phases):
    """ View function decorator only allowing access if the database is no competition database
        or the phase of the competition matches one of the phases passed in the iterable argument `phases` """
    @wraps(f)
    def decorated_f(*args, **kwargs):
        db = models.get_database(kwargs['database'])
        if db.is_competition() and db.competition_phase() not in phases: abort(404)
        return f(*args, **kwargs)
    return decorated_f

def require_competition(f):
    """ View function decorator only allowing access if the database is a competition database """
    @wraps(f)
    def decorated_f(*args, **kwargs):
        db = models.get_database(kwargs['database'])
        if not db.is_competition(): abort(404)
        return f(*args, **kwargs)
    return decorated_f

def require_login(f):
    """ View function decorator that checks if the user is logged in to the database specified
        by the route parameter <database> which gets passed in **kwargs.
        Only checked for competition databases that are in a phase < 3 (not finished).
        Also attaches the user object to the request as attribute "User". """
    @wraps(f)
    def decorated_f(*args, **kwargs):
        db = models.get_database(kwargs['database']) or abort(404)
        
        if session.get('logged_in') and session.get('idUser', None): # if logged in already, attach user object
            request.User = db.session.query(db.User).get(session['idUser'])
        
        if db.is_competition() and db.competition_phase() < 3:
            def redirect_f(*args, **kwargs):
                return redirect(url_for('accounts.login', database=kwargs['database']))
                
            if not session.get('logged_in') or session.get('idUser', None) is None: return redirect_f(*args, **kwargs)
            if session.get('database') != kwargs['database']: return redirect_f(*args, **kwargs)
            
        return f(*args, **kwargs)
    return decorated_f

def password_hash(password):
    """ Returns a crpytographic hash of the given password salted with SECRET_KEY as hexstring """
    hash = hashlib.sha256()
    hash.update(config.SECRET_KEY)
    hash.update(password)
    return hash.hexdigest()
