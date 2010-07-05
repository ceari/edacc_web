# -*- coding: utf-8 -*-

import json, time, hashlib, os, datetime, cStringIO, re, random
from functools import wraps

from flask import render_template as render
from flask import Response, abort, Headers, Environment, request, session, url_for, redirect, flash, Request
from werkzeug import secure_filename

from edacc import app, plots, config, utils, models
from edacc.models import joinedload, joinedload_all
from edacc.constants import JOB_FINISHED, JOB_ERROR

if config.CACHING:
    from werkzeug.contrib.cache import MemcachedCache
    cache = MemcachedCache([config.MEMCACHED_HOST])
    
if not config.DEBUG:
    import logging
    from logging.handlers import FileHandler
    file_handler = FileHandler(config.LOG_FILE)
    file_handler.setLevel(logging.WARNING)
    app.logger.addHandler(file_handler)
    
for db in config.DEFAULT_DATABASES:
    models.add_database(db[0], db[1], db[2], db[3])
    
class LimitedRequest(Request):
    max_form_memory_size = 16 * 1024 * 1024 # limit form uploads to 16 MB
    
app.request_class = LimitedRequest

app.secret_key = config.SECRET_KEY

####################################################################
# various helper functions and decorators
####################################################################

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
        Also attaches the user object to the request as attribute "User".
    """
    @wraps(f)
    def decorated_f(*args, **kwargs):
        db = models.get_database(kwargs['database']) or abort(404)
        
        if session.get('logged_in') and session.get('idUser', None): # if logged in already, attach user object
            request.User = db.session.query(db.User).get(session['idUser'])
        
        if db.is_competition() and db.competition_phase() < 3:
            def redirect_f(*args, **kwargs):
                return redirect(url_for('login', database=kwargs['database']))
                
            if not session.get('logged_in') or session.get('idUser', None) is None: return redirect_f(*args, **kwargs)
            if session.get('database') != kwargs['database']: return redirect_f(*args, **kwargs)
            
        return f(*args, **kwargs)
    return decorated_f

def password_hash(password):
    """ Returns a crpytographic hash of the given password seeded with SECRET_KEY as hexstring """
    hash = hashlib.sha256()
    hash.update(config.SECRET_KEY)
    hash.update(password)
    return hash.hexdigest()

####################################################################
#                   Admin View Functions
####################################################################

@app.route('/admin/databases/')
@require_admin
def databases():
    """ Show a list of databases this web frontend is serving """
    databases = list(models.get_databases().itervalues())
    databases.sort(key=lambda db: db.database.lower())
    
    return render('/admin/databases.html', databases=databases, host=config.DATABASE_HOST, port=config.DATABASE_PORT)

@app.route('/admin/databases/add/', methods=['GET', 'POST'])
@require_admin
def databases_add():
    """ Display a form to add databases to the web frontend """
    error = None
    if request.method == 'POST':
        label = request.form['label']
        database = request.form['database']
        username = request.form['username']
        password = request.form['password']
        
        if models.get_database(database):
            error = "A database with this name already exists"
        else:
            try:
                models.add_database(username, password, database, label)
                return redirect(url_for('databases'))
            except Exception as e:
                error = "Can't add database: " + str(e)
    
    return render('/admin/databases_add.html', error=error)

@app.route('/admin/databases/remove/<database>/')
@require_admin
def databases_remove(database):
    """ Remove the specified database from the set of databases the web frontend is serving """
    models.remove_database(database)
    return redirect(url_for('databases'))
    
@app.route('/admin/login/', methods=['GET', 'POST'])
def admin_login():
    """ Admin login form """
    if session.get('admin'): return redirect(url_for('databases'))
    
    error = None
    if request.method == 'POST':
        if request.form['password'] != config.ADMIN_PASSWORD:
            error = 'Invalid password'
        else:
            session['admin'] = True
            return redirect(url_for('databases'))
    return render('/admin/login.html', error=error)

@app.route('/admin/logout/')
def admin_logout():
    """ Log out the currently logged in admin """
    session.pop('admin', None)
    return redirect('/')

####################################################################
#                   Accounts View Functions
####################################################################
    
@app.route('/<database>/register/', methods=['GET', 'POST'])
@require_phase(phases=(1,))
@require_competition
def register(database):
    """ User registration """
    db = models.get_database(database) or abort(404)

    error = None
    if request.method == 'POST':
        lastname = request.form['lastname']
        firstname = request.form['firstname']
        email = request.form['email']
        password = request.form['password']
        password_confirm = request.form['password_confirm']
        address = request.form['address']
        affiliation = request.form['affiliation']
        captcha = request.form['captcha']
        
        valid = True
        if any(len(x) > 255 for x in (lastname, firstname, email, address, affiliation)):
            error = 'max. 255 characters'
            valid = False
        
        if password != password_confirm:
            error = "Passwords don't match"
            valid = False
        
        if re.match("^[a-zA-Z0-9._%-+]+@[a-zA-Z0-9._%-]+.[a-zA-Z]{2,6}$", email) is None:
            error = "Invalid e-mail address, contact an administrator if this e-mail address is valid"
            valid = False
        
        if db.session.query(db.User).filter_by(email=email).count() > 0:
            error = "An account with this email address already exists"
            valid = False
            
        captcha = map(int, captcha.split())
        try:
            if not utils.satisfies(captcha, session['captcha']):
                valid = False
                error = "You can't register to a SAT competition without being able to solve a boolean formula!"
        except:
            valid = False
            error = "Wrong format of the solution"

        if valid:
            user = db.User()
            user.lastname = lastname
            user.firstname = firstname
            user.password = password_hash(password)
            user.email = email
            user.postal_address = address
            user.affiliation = affiliation
            
            db.session.add(user)
            try:
                db.session.commit()
            except:
                db.session.rollback()
                error = 'Error when trying to save the account'
                return render('/accounts/register.html', database=database, error=error)
            
            flash('Account created successfully. You can log in now.')
            return redirect(url_for('experiments_index', database=database))
            
    random.seed()
    f = utils.random_formula(2,3)
    while not utils.SAT(f):
        f = utils.random_formula(2,3)
    session['captcha'] = f
    
    return render('/accounts/register.html', database=database, db=db, error=error)

@app.route('/<database>/login/', methods=['GET', 'POST'])
@require_competition
def login(database):
    """ User login form and handling for a specific database. Users can only be logged in to one database at a time """
    db = models.get_database(database) or abort(404)
    
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = db.session.query(db.User).filter_by(email=email).first()
        if user is None:
            error = "Account doesn't exist"
        else:
            if user.password != password_hash(password):
                error = 'Invalid password'
            else:
                session['logged_in'] = True
                session['database'] = database
                session['idUser'] = user.idUser
                session['email'] = user.email
                session['db'] = str(db)
                flash('Login successful')
                return redirect(url_for('experiments_index', database=database))
    
    return render('/accounts/login.html', database=database, error=error, db=db)

@app.route('/<database>/logout')
@require_login
@require_competition
def logout(database):
    """ User logout for a database """
    db = models.get_database(database) or abort(404)
    
    session.pop('logged_in', None)
    session.pop('database', None)
    return redirect('/')

@app.route('/<database>/submit-solver/<int:id>', methods=['GET', 'POST']) # for resubmissions of the same solver
@app.route('/<database>/submit-solver/', methods=['GET', 'POST'])
@require_login
@require_phase(phases=(1,))
@require_competition
def submit_solver(database, id=None):
    """ Form to submit solvers to a database """
    db = models.get_database(database) or abort(404)
    user = db.session.query(db.User).get(session['idUser'])
    
    if id: solver = db.session.query(db.Solver).get(id) or abort(404)

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1] in ['zip']

    error = None
    if request.method == 'POST':
        name = request.form['name']
        binary = request.files['binary']
        code = request.files['code']
        description = request.form['description']
        version = request.form['version']
        authors = request.form['authors']
        parameters = request.form['parameters']
    
        valid = True
        if not binary:
            error = 'You have to provide a binary'
            valid = False
        
        if not code or not allowed_file(code.filename):
            error = 'You have to provide a zip-archive containing the source code'
            valid = False
        
        bin = binary.read()
        hash = hashlib.md5()
        hash.update(bin)
        if not id and db.session.query(db.Solver).filter_by(md5=hash.hexdigest()).first() is not None:
            error = 'Solver with this binary already exists'
            valid = False
            
        if not id and db.session.query(db.Solver).filter_by(name=name, version=version).first() is not None:
            error = 'Solver with this name and version already exists'
            valid = False
        
        if 'SEED' in parameters and 'INSTANCE' in parameters:
            params = utils.parse_parameters(parameters)
        else:
            error = 'You have to specify SEED and INSTANCE as parameters'
            valid = False
        
        if valid:
            if not id:
                solver = db.Solver()
            solver.name = name
            solver.binaryName = secure_filename(binary.filename)
            solver.binary = bin
            solver.md5 = hash.hexdigest()
            solver.description = description
            solver.code = code.read()
            solver.version = version
            solver.authors = authors
            solver.user = request.User

            if not id: db.session.add(solver)
            
            if id: # on resubmissions delete old parameters
                for p in solver.parameters:
                    db.session.delete(p)
                db.session.commit()
            
            for p in params:
                param = db.Parameter()
                param.name = p[0]
                param.prefix = p[1]
                param.value = p[2]
                param.hasValue = not p[3] # p[3] actually means 'is boolean'
                param.order = p[4]
                param.solver = solver
                db.session.add(param)
            try:
                db.session.commit()
            except:
                db.session.rollback()
                flash("Couldn't save solver to the database")
                return render('submit_solver.html', database=database, error=error, db=db, id=id)
                
            
            flash('Solver submitted successfully')
            return redirect(url_for('experiments_index', database=database))
    
    return render('submit_solver.html', database=database, error=error, db=db, id=id)
    
@app.route('/<database>/solvers')
@require_login
@require_competition
def list_solvers(database):
    """ Lists all solvers that the currently logged in user submitted to the database """
    db = models.get_database(database) or abort(404)
    solvers = db.session.query(db.Solver).filter_by(user=request.User).all()
   
    return render('list_solvers.html', database=database, solvers=solvers, db=db)
    
@app.route('/<database>/download-solver/<int:id>/')
@require_login
@require_competition
@require_phase(phases=(1,2,3,4))
def download_solver(database, id):
    """ Lets a user download the binaries of his own solvers """
    db = models.get_database(database) or abort(404)
    solver = db.session.query(db.Solver).get(id) or abort(404)
    if solver.user != request.User: abort(401)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename=solver.binaryName)
    
    res = Response(response=solver.binary, headers=headers)
    db.session.remove()
    return res

@app.route('/<database>/download-solver-code/<int:id>/')
@require_login
@require_competition
@require_phase(phases=(1,2,3,4))
def download_solver_code(database, id):
    """ Lets a user download the binaries of his own solvers """
    db = models.get_database(database) or abort(404)
    solver = db.session.query(db.Solver).get(id) or abort(404)
    if solver.user != request.User: abort(401)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename=solver.name + ".zip")
    
    res = Response(response=solver.code, headers=headers)
    db.session.remove()
    return res

####################################################################
#                   Web Frontend View Functions
####################################################################

@app.route('/')
def index():
    """ Show a list of all served databases """
    databases = list(models.get_databases().itervalues())
    databases.sort(key=lambda db: db.database.lower())
    
    return render('/databases.html', databases=databases)

@app.route('/<database>/experiments')
@require_login
def experiments_index(database):
    """ Show a list of all experiments in the database """
    db = models.get_database(database) or abort(404)
    
    if db.is_competition() and db.competition_phase() not in (3,4):
        # Experiments are only visible in phases 3 through 4 in a competition database
        experiments = []
    else:
        experiments = db.session.query(db.Experiment).all()
        experiments.sort(key=lambda e: e.name.lower())

    res = render('experiments.html', experiments=experiments, db=db, database=database)
    db.session.remove()
    return res

@app.route('/<database>/experiment/<int:experiment_id>/')
@require_phase(phases=(2,3,4))
@require_login
def experiment(database, experiment_id):
    """ Show menu with links to info and evaluation pages """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    res = render('experiment.html', experiment=experiment, database=database, db=db)
    db.session.remove()
    return res
    
@app.route('/<database>/experiment/<int:experiment_id>/solvers')
@require_phase(phases=(3,4))
@require_login
def experiment_solvers(database, experiment_id):
    """ Show a list of all solvers used in the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    # remove duplicates introduced by a solver being used with more than one configuration
    solvers = list(set(sc.solver for sc in experiment.solver_configurations))
    solvers.sort(key=lambda s: s.name)
    
    # if competition db, show only own solvers unless phase == 4
    if not is_admin() and db.is_competition() and not db.competition_phase() in (4,):
        solvers = filter(lambda s: s.user == request.User, solvers)
    
    res = render('experiment_solvers.html', solvers=solvers, experiment=experiment, database=database, db=db)
    db.session.remove()
    return res
    
@app.route('/<database>/experiment/<int:experiment_id>/solver-configurations')
@require_phase(phases=(3,4))
@require_login
def experiment_solver_configurations(database, experiment_id):
    """ List all solver configurations (solver + parameter set) used in the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    solver_configurations = experiment.solver_configurations
    solver_configurations.sort(key=lambda sc: sc.solver.name.lower())
    
    # if competition db, show only own solvers unless phase == 4
    if not is_admin() and db.is_competition() and not db.competition_phase() in (4,):
        solver_configurations = filter(lambda sc: sc.solver.user == request.User, solver_configurations)
    
    res = render('experiment_solver_configurations.html', experiment=experiment, solver_configurations=solver_configurations, database=database, db=db)
    db.session.remove()
    return res
    
@app.route('/<database>/experiment/<int:experiment_id>/instances')
@require_phase(phases=(3,4))
@require_login
def experiment_instances(database, experiment_id):
    """ Show information about all instances used in the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    instances = experiment.instances
    instances.sort(key=lambda i: i.name)
    
    res = render('experiment_instances.html', instances=instances, experiment=experiment, database=database, db=db)
    db.session.remove()
    return res

@app.route('/<database>/experiment/<int:experiment_id>/results')
@require_phase(phases=(3,4))
@require_login
def experiment_results(database, experiment_id):
    """ Show a table with the solver configurations and their results on the instances of the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    instances = experiment.instances
    solver_configs = experiment.solver_configurations
    
    # if competition db, show only own solvers unless phase == 4
    if not is_admin() and db.is_competition() and db.competition_phase() not in (4,):
        solver_configs = filter(lambda sc: sc.solver.user == request.User, solver_configs)
    
    if config.CACHING:
        results = cache.get('experiment_results_' + str(experiment_id))
    else:
        results = None
    
    if results is None:
        results = []
        for instance in instances:
            row = []
            for solver_config in solver_configs:
                query = db.session.query(db.ExperimentResult)
                query.enable_eagerloads(True).options(joinedload(db.ExperimentResult.instance, db.ExperimentResult.solver_configuration))
                jobs = query.filter_by(experiment=experiment) \
                            .filter_by(solver_configuration=solver_config) \
                            .filter_by(instance=instance) \
                            .all()
                completed = len(filter(lambda j: j.status in JOB_FINISHED or j.status in JOB_ERROR, jobs))
                runtimes = [j.time for j in jobs]
                runtimes.sort()
                time_median = runtimes[len(runtimes) / 2]
                time_avg = sum(runtimes) / float(len(jobs))
                time_max = max(runtimes)
                time_min = min(runtimes)
                row.append({'time_avg': time_avg,
                            'time_median': time_median,
                            'time_max': time_max,
                            'time_min': time_min,
                            'completed': completed,
                            'total': len(jobs),
                            'solver_config': solver_config
                            })
            results.append({'instance': instance, 'times': row})
            
        if config.CACHING:
            cache.set('experiment_results_' + str(experiment_id), results, timeout=config.CACHE_TIMEOUT)
        
    res = render('experiment_results.html', experiment=experiment,
                    instances=instances, solver_configs=solver_configs,
                    results=results, database=database, db=db)
    db.session.remove()
    return res
    
@app.route('/<database>/experiment/<int:experiment_id>/progress')
@require_phase(phases=(3,4))
@require_login
def experiment_progress(database, experiment_id):
    """ Show a live information table of the experiment's progress """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    res = render('experiment_progress.html', experiment=experiment, database=database, db=db)
    db.session.remove()
    return res

@app.route('/<database>/experiment/<int:experiment_id>/progress-ajax')
@require_phase(phases=(3,4))
@require_login
def experiment_progress_ajax(database, experiment_id):
    """ Returns JSON-serialized data of the experiment results. Used by the jQuery datatable as ajax data source """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    query = db.session.query(db.ExperimentResult).enable_eagerloads(True).options(joinedload(db.ExperimentResult.instance))
    query.options(joinedload(db.ExperimentResult.solver_configuration))
    jobs = query.filter_by(experiment=experiment)
    
    # if competition db, show only own solvers unless phase == 4
    if not is_admin() and db.is_competition() and db.competition_phase() not in (4,):
        jobs = filter(lambda j: j.solver_configuration.solver.user == request.User, jobs)
    
    aaData = []
    for job in jobs:
        iname = job.instance.name
        if len(iname) > 30: iname = iname[0:30] + '...'
        aaData.append([job.idJob, job.solver_configuration.get_name(), utils.parameter_string(job.solver_configuration),
               iname, job.run, job.time, job.seed, utils.job_status(job.status)])
    
    res = json.dumps({'aaData': aaData})
    db.session.remove()
    return res
    
@app.route('/<database>/experiment/<int:experiment_id>/result/<int:solver_configuration_id>/<int:instance_id>')
@require_phase(phases=(3,4))
@require_login
def solver_config_results(database, experiment_id, solver_configuration_id, instance_id):
    """ Displays list of results (all jobs) of a solver configuration on an instance """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    solver_configuration = db.session.query(db.SolverConfiguration).get(solver_configuration_id) or abort(404)
    instance = db.session.query(db.Instance).filter_by(idInstance=instance_id).first() or abort(404)
    if solver_configuration not in experiment.solver_configurations: abort(404)
    if instance not in experiment.instances: abort(404)
    
    if not is_admin() and db.is_competition() and not db.competition_phase() in (4,):
        if not solver_configuration.solver.user == request.User: abort(401)
    
    jobs = db.session.query(db.ExperimentResult) \
                    .filter_by(experiment=experiment) \
                    .filter_by(solver_configuration=solver_configuration) \
                    .filter_by(instance=instance) \
                    .all()
    
    completed = len(filter(lambda j: j.status in JOB_FINISHED or j.status in JOB_ERROR, jobs))
    
    res = render('solver_config_results.html', experiment=experiment, solver_configuration=solver_configuration,
                  instance=instance, results=jobs, completed=completed, database=database, db=db)
    db.session.remove()
    return res
    
@app.route('/<database>/instance/<int:instance_id>')
@require_phase(phases=(3,4))
@require_login
def instance_details(database, instance_id):
    """ Show instance details """
    db = models.get_database(database) or abort(404)
    instance = db.session.query(db.Instance).filter_by(idInstance=instance_id).first() or abort(404)
        
    instance_blob = instance.instance
    if len(instance_blob) > 1024:
        # show only the first and last 512 characters if the instance is larger than 1kB
        instance_text = instance_blob[:512] + "\n\n... [truncated " + utils.download_size(len(instance_blob) - 1024) + "]\n\n" + instance_blob[-512:]
    else:
        instance_text = instance_blob
    
    res = render('instance_details.html', instance=instance, instance_text=instance_text, blob_size=len(instance.instance), database=database, db=db)
    db.session.remove()
    return res
    
@app.route('/<database>/instance/<int:instance_id>/download')
@require_phase(phases=(3,4))
@require_login
def instance_download(database, instance_id):
    """ Return HTTP-Response containing the instance blob """
    db = models.get_database(database) or abort(404)
    instance = db.session.query(db.Instance).filter_by(idInstance=instance_id).first() or abort(404)
    
    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename=instance.name)
    
    res = Response(response=instance.instance, headers=headers)
    db.session.remove()
    return res
    
@app.route('/<database>/solver/<int:solver_id>')
@require_phase(phases=(1,2,3,4))
@require_login
def solver_details(database, solver_id):
    """ Show solver details """
    db = models.get_database(database) or abort(404)
    solver = db.session.query(db.Solver).get(solver_id) or abort(404)
    
    if not is_admin() and db.is_competition() and not db.competition_phase() in (4,):
        if solver.user != request.User and not is_admin(): abort(401)
    
    res = render('solver_details.html', solver=solver, database=database, db=db)
    db.session.remove()
    return res

@app.route('/<database>/experiment/<int:experiment_id>/solver-configurations/<int:solver_configuration_id>')
@require_phase(phases=(1,2,3,4))
@require_login
def solver_configuration_details(database, experiment_id, solver_configuration_id):
    """ Show solver configuration details """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    solver_config = db.session.query(db.SolverConfiguration).get(solver_configuration_id) or abort(404)
    solver = solver_config.solver
    
    if not is_admin() and db.is_competition() and not db.competition_phase() in (4,):
        if solver.user != request.User: abort(401)
    
    parameters = solver_config.parameter_instances
    parameters.sort(key=lambda p: p.parameter.order)
    
    res = render('solver_configuration_details.html', solver_config=solver_config, solver=solver, parameters=parameters, database=database, db=db)
    db.session.remove()
    return res
    
@app.route('/<database>/experiment/<int:experiment_id>/result/<int:result_id>')
@require_phase(phases=(3,4))
@require_login
def experiment_result(database, experiment_id, result_id):
    """ Displays information about a single result (job) """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    result = db.session.query(db.ExperimentResult).get(result_id) or abort(404)
    
    if not is_admin() and db.is_competition() and not db.competition_phase() in (4,):
        if result.solver_configuration.solver.user != request.User: abort(401)
    
    resultFile = result.resultFile
    clientOutput = result.clientOutput
    
    if clientOutput is not None:
        if len(clientOutput) > 4*1024:
            # show only the first and last 2048 characters if the resultFile is larger than 4kB
            clientOutput_text = clientOutput[:2048] + "\n\n... [truncated " + str(int((len(clientOutput) - 4096) / 1024.0)) + " kB]\n\n" + clientOutput[-2048:]
        else:
            clientOutput_text = clientOutput
    else: clientOutput_text = "No output"
    
    if resultFile is not None:
        if len(resultFile) > 4*1024:
            # show only the first and last 2048 characters if the resultFile is larger than 4kB
            resultFile_text = resultFile[:2048] + "\n\n... [truncated " + str(int((len(resultFile) - 4096) / 1024.0)) + " kB]\n\n" + resultFile[-2048:]
        else:
            resultFile_text = resultFile
    else: resultFile_text = "No result"
    
    res = render('result_details.html', experiment=experiment, result=result, solver=result.solver_configuration.solver,
                  solver_config=result.solver_configuration, instance=result.instance, resultFile_text=resultFile_text,
                  clientOutput_text=clientOutput_text, database=database, db=db)
    db.session.remove()
    return res
    
@app.route('/<database>/experiment/<int:experiment_id>/result/<int:result_id>/download')
@require_phase(phases=(3,4))
@require_login
def experiment_result_download(database, experiment_id, result_id):
    """ Returns the specified job client output file as HTTP response """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    result = db.session.query(db.ExperimentResult).get(result_id) or abort(404)
    
    if not is_admin() and db.is_competition() and not db.competition_phase() in (4,):
        if result.solver_configuration.solver.user != request.User: abort(401)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename=result.resultFileName)
    
    res = Response(response=result.resultFile, headers=headers)
    db.session.remove()
    return res
    
@app.route('/<database>/experiment/<int:experiment_id>/result/<int:result_id>/download-client-output')
@require_phase(phases=(3,4))
@require_login
def experiment_result_download_client_output(database, experiment_id, result_id):
    """ Returns the specified job client output as HTTP response """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    result = db.session.query(db.ExperimentResult).get(result_id) or abort(404)
    
    if not is_admin() and db.is_competition() and not db.competition_phase() in (4,):
        if result.solver_configuration.solver.user != request.User: abort(401)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename="client_output_"+result.resultFileName)
    
    res = Response(response=result.clientOutput, headers=headers)
    db.session.remove()
    return res

@app.route('/<database>/experiment/<int:experiment_id>/evaluation-solved-instances')
@require_phase(phases=(4,))
@require_login
def evaluation_solved_instances(database, experiment_id):
    """ Shows a page with a cactus plot of the instances solved within a given amount of time of all solver configurations
        of the specified experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    return render('/evaluation/solved_instances.html', database=database, experiment=experiment)

@app.route('/<database>/experiment/<int:experiment_id>/evaluation-cputime/')
@require_phase(phases=(4,))
@require_login
def evaluation_cputime(database, experiment_id):
    """ Shows a page that lets users plot the cputimes of two solver configurations on the instances of the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    s1 = request.args.get('s1', None)
    s2 = request.args.get('s2', None)
    solver1, solver2 = None, None
    if s1:
        s1 = int(s1)
        solver1 = db.session.query(db.SolverConfiguration).get(s1)
    if s2:
        s2 = int(s2)
        solver2 = db.session.query(db.SolverConfiguration).get(s2)

    return render('/evaluation/cputime.html', database=database, experiment=experiment, s1=s1, s2=s2, solver1=solver1, solver2=solver2, db=db)

@app.route('/<database>/experiment/<int:experiment_id>/cputime-plot/<int:s1>/<int:s2>/')
@require_phase(phases=(4,))
@require_login
def cputime_plot(database, experiment_id, s1, s2):
    """ Plots the cputimes of the two specified solver configurations on the experiment's instances against each
        other in a scatter plot and returns the image in a HTTP response """
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    sc1 = db.session.query(db.SolverConfiguration).get(s1) or abort(404)
    sc2 = db.session.query(db.SolverConfiguration).get(s2) or abort(404)
        
    results1 = db.session.query(db.ExperimentResult)
    results1.enable_eagerloads(True).options(joinedload(db.ExperimentResult.instance, db.ExperimentResult.solver_configuration))
    results1 = results1.filter_by(experiment=exp, solver_configuration=sc1)
    
    results2 = db.session.query(db.ExperimentResult)
    results2.enable_eagerloads(True).options(joinedload(db.ExperimentResult.instance, db.ExperimentResult.solver_configuration))
    results2 = results2.filter_by(experiment=exp, solver_configuration=sc2)
    
    xs = []
    ys = []
    for instance in exp.instances:
        r1 = results1.filter_by(instance=instance).first()
        r2 = results2.filter_by(instance=instance).first()
        if r1: xs.append(r1.time)
        if r2: ys.append(r2.time)

    title = sc1.solver.name + ' vs. ' + sc2.solver.name
    xlabel = sc1.solver.name + ' CPU time (s)'
    ylabel = sc2.solver.name + ' CPU time (s)'
    if request.args.has_key('pdf'):
        filename = os.path.join(config.TEMP_DIR, request.unique_id) + '.pdf'
        plots.scatter(xs, ys, xlabel, ylabel, title, exp.timeOut, filename, format='pdf')
        headers = Headers()
        headers.add('Content-Disposition', 'attachment', filename=sc1.solver.name + '_vs_' + sc2.solver.name + '.pdf')
        response = Response(response=open(filename, 'rb').read(), mimetype='application/pdf', headers=headers)
        os.remove(filename)
        return response
    else:
        filename = os.path.join(config.TEMP_DIR, request.unique_id) + '.png'
        plots.scatter(xs, ys, xlabel, ylabel, title, exp.timeOut, filename)
        response = Response(response=open(filename, 'rb').read(), mimetype='image/png')
        os.remove(filename)
        return response
    
@app.route('/<database>/experiment/<int:experiment_id>/cactus-plot/')
@require_phase(phases=(4,))
@require_login
def cactus_plot(database, experiment_id):
    """ Renders a cactus plot of the instances solved within a given amount of time of all solver configurations
        of the specified experiment """
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    results = db.session.query(db.ExperimentResult)
    results.enable_eagerloads(True).options(joinedload(db.ExperimentResult.solver_configuration))
    results = results.filter_by(experiment=exp)
    
    solvers = []
    for sc in exp.solver_configurations:
        s = {'xs': [], 'ys': [], 'name': sc.get_name()}
        sc_res = results.filter_by(solver_configuration=sc, run=0, status=1).order_by(db.ExperimentResult.time)
        i = 1
        for r in sc_res:
            s['ys'].append(r.time)
            s['xs'].append(i)
            i += 1
        solvers.append(s)
        
    max_x = len(exp.instances) + 10
    max_y = max([max(s['ys']) for s in solvers])
    
    if request.args.has_key('pdf'):
        filename = os.path.join(config.TEMP_DIR, request.unique_id) + 'cactus.pdf'
        plots.cactus(solvers, max_x, max_y, filename, format='pdf')
        headers = Headers()
        headers.add('Content-Disposition', 'attachment', filename='instances_solved_given_time.pdf')
        response = Response(response=open(filename, 'rb').read(), mimetype='application/pdf', headers=headers)
        os.remove(filename)
        return response
    else:
        filename = os.path.join(config.TEMP_DIR, request.unique_id) + 'cactus.png'
        plots.cactus(solvers, max_x, max_y, filename)
        response = Response(response=open(filename, 'rb').read(), mimetype='image/png')
        os.remove(filename)
        return response
