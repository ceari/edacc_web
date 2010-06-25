# -*- coding: utf-8 -*-

import json, time, hashlib, os, datetime, cStringIO, re
from functools import wraps

from flask import render_template as render
from flask import Response, abort, Headers, Environment, request, session, url_for, redirect, flash
from werkzeug import secure_filename

from edacc import app, plots, config, utils, models
from edacc.models import joinedload
from edacc.constants import JOB_FINISHED, JOB_ERROR

if config.CACHING:
    from werkzeug.contrib.cache import MemcachedCache
    cache = MemcachedCache([config.MEMCACHED_HOST])
    
for db in config.DEFAULT_DATABASES:
    models.add_database(db[0], db[1], db[2])

app.secret_key = config.SECRET_KEY

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

def require_login(f):
    """ View function decorator that checks if the user is logged in to the database specified
        by the route parameter <database> which gets passed in **kwargs.
        Therefor, this decorator can only be used for URLs that have a <database> part.
        Also attaches the user object to the request as attribute "User"
    """
    @wraps(f)
    def decorated_f(*args, **kwargs):
        def redirect_f(*args, **kwargs):
            return redirect(url_for('login', database=kwargs['database']))
            
        if not session.get('logged_in') or session.get('idUser', None) is None: return redirect_f(*args, **kwargs)
        if session.get('database') != kwargs['database']: return redirect_f(*args, **kwargs)
        
        db = models.get_database(kwargs['database'])
        request.User = db.session.query(db.User).get(session['idUser'])
        
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
    databases = list(models.get_databases().itervalues())
    databases.sort(key=lambda db: db.database.lower())
    
    return render('/admin/databases.html', databases=databases, host=config.DATABASE_HOST, port=config.DATABASE_PORT)

@app.route('/admin/databases/add/', methods=['GET', 'POST'])
@require_admin
def databases_add():
    error = None
    if request.method == 'POST':
        database = request.form['database']
        username = request.form['username']
        password = request.form['password']
        
        if models.get_database(database):
            error = "A database with this name already exists"
        else:
            try:
                models.add_database(username, password, database)
                return redirect(url_for('databases'))
            except Exception as e:
                error = "Can't add database: " + str(e)
        
    
    return render('/admin/databases_add.html', error=error)

@app.route('/admin/databases/remove/<database>/')
@require_admin
def databases_remove(database):
    models.remove_database(database)
    return redirect(url_for('databases'))
    
@app.route('/admin/login/', methods=['GET', 'POST'])
def admin_login():
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
    session.pop('admin', None)
    return redirect('/')

####################################################################
#                   Accounts View Functions
####################################################################
    
@app.route('/<database>/register/', methods=['GET', 'POST'])
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
            valid = false
        
        if valid:
            user = db.User()
            user.lastname = lastname
            user.firstname = firstname
            user.password = password_hash(password)
            user.email = email
            user.postal_address = address
            user.affiliation = affiliation
            
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('experiments_index', database=database))
    
    return render('/accounts/register.html', database=database, error=error)

@app.route('/<database>/login/', methods=['GET', 'POST'])
def login(database):
    """ User login form and handling for a specific database """
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
                flash('Login successful')
                return redirect(url_for('experiments_index', database=database))
    
    return render('/accounts/login.html', database=database, error=error)

@app.route('/<database>/logout')
@require_login
def logout(database):
    """ User logout for a database """
    session.pop('logged_in', None)
    session.pop('database', None)
    return redirect('/')
    
@app.route('/<database>/submit-solver/', methods=['GET', 'POST'])
@require_login
def submit_solver(database):
    """ Form to submit solvers to a database """
    db = models.get_database(database) or abort(404)
    user = db.session.query(db.User).get(session['idUser'])

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
            
        hash = hashlib.md5()
        hash.update(binary.read())
        if db.session.query(db.Solver).filter_by(md5=hash.hexdigest()).first() is not None:
            error = 'Solver with this binary already exists'
            valid = False
        
        if 'SEED' in parameters and 'INSTANCE' in parameters:
            params = utils.parse_parameters(parameters)
        else:
            error = 'You have to specify SEED and INSTANCE as parameters'
            valid = False
        
        if valid:
            solver = db.Solver()
            solver.name = name
            solver.binaryName = secure_filename(binary.filename)
            solver.binary = binary.read()
            solver.md5 = hash.hexdigest()
            solver.description = description
            solver.code = code.read()
            solver.version = version
            solver.authors = authors
            
            solver.user = request.User

            db.session.add(solver)
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
            db.session.commit()
                
            
            flash('Solver submitted successfully')
            return redirect(url_for('experiments_index', database=database))
    
    return render('submit_solver.html', database=database, error=error)
    
@app.route('/<database>/solvers')
@require_login
def list_solvers(database):
    """ Lists all solvers that the currently logged in user submitted to the database """
    db = models.get_database(database) or abort(404)
    
    solvers = db.session.query(db.Solver).filter_by(user=request.User)
   
    return render('list_solvers.html', database=database, solvers=solvers)
    

####################################################################
#                   Web Frontend View Functions
####################################################################

@app.route('/')
def index():
    """ Show a list of all managed databases """
    databases = list(models.get_databases().itervalues())
    databases.sort(key=lambda db: db.database.lower())
    
    return render('/databases.html', databases=databases)

@app.route('/<database>/')
@require_login
def experiments_index(database):
    """ Show a list of all experiments in the database """
    db = models.get_database(database) or abort(404)
    
    experiments = db.session.query(db.Experiment).all()
    experiments.sort(key=lambda e: e.name.lower())

    res = render('experiments.html', experiments=experiments, database=database)
    db.session.remove()
    return res

@app.route('/<database>/experiment/<int:experiment_id>/')
@require_login
def experiment(database, experiment_id):
    """ Show menu with links to info and evaluation pages """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    res = render('experiment.html', experiment=experiment, database=database)
    db.session.remove()
    return res
    

@app.route('/<database>/experiment/<int:experiment_id>/solvers')
@require_login
def experiment_solvers(database, experiment_id):
    """ Show a list of all solvers used in the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    # remove duplicates introduced by a solver being used with more than one configuration
    solvers = list(set(sc.solver for sc in experiment.solver_configurations))
    solvers.sort(key=lambda s: s.name)
    
    if not experiment.is_finished() and not is_admin():
        solvers = filter(lambda s: s.user == request.User, solvers)
    
    res = render('experiment_solvers.html', solvers=solvers, experiment=experiment, database=database)
    db.session.remove()
    return res
    
@app.route('/<database>/experiment/<int:experiment_id>/solver-configurations')
@require_login
def experiment_solver_configurations(database, experiment_id):
    """ List all solver configurations (solver + parameter set) used in the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    solver_configurations = experiment.solver_configurations
    solver_configurations.sort(key=lambda sc: sc.solver.name.lower())
    
    if not experiment.is_finished() and not is_admin():
        solver_configurations = filter(lambda sc: sc.solver.user == request.User, solver_configurations)
    
    res = render('experiment_solver_configurations.html', experiment=experiment, solver_configurations=solver_configurations, database=database)
    db.session.remove()
    return res
    
@app.route('/<database>/experiment/<int:experiment_id>/instances')
@require_login
def experiment_instances(database, experiment_id):
    """ Show information about all instances used in the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    instances = experiment.instances
    instances.sort(key=lambda i: i.name)
    
    res = render('experiment_instances.html', instances=instances, experiment=experiment, database=database)
    db.session.remove()
    return res

@app.route('/<database>/experiment/<int:experiment_id>/results')
@require_login
def experiment_results(database, experiment_id):
    """ Show a table with the solver configurations and their results on the instances of the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    instances = experiment.instances
    solver_configs = experiment.solver_configurations
    
    if not experiment.is_finished() and not is_admin():
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
                    results=results, database=database)
    db.session.remove()
    return res
    
@app.route('/<database>/experiment/<int:experiment_id>/progress')
@require_login
def experiment_progress(database, experiment_id):
    """ Show a live information table of the experiment's progress """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    res = render('experiment_progress.html', experiment=experiment, database=database)
    db.session.remove()
    return res

@app.route('/<database>/experiment/<int:experiment_id>/progress-ajax')
@require_login
def experiment_progress_ajax(database, experiment_id):
    """ Returns JSON-serialized data of the experiment results. Used by the jQuery datatable as ajax data source """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    query = db.session.query(db.ExperimentResult).enable_eagerloads(True).options(joinedload(db.ExperimentResult.instance))
    query.options(joinedload(db.ExperimentResult.solver_configuration))
    jobs = query.filter_by(experiment=experiment)
    
    if not experiment.is_finished() and not is_admin():
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
@require_login
def solver_config_results(database, experiment_id, solver_configuration_id, instance_id):
    """ Displays list of results (all jobs) of a solver configuration on an instance """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    solver_configuration = db.session.query(db.SolverConfiguration).get(solver_configuration_id) or abort(404)
    instance = db.session.query(db.Instance).filter_by(idInstance=instance_id).first() or abort(404)
    if solver_configuration not in experiment.solver_configurations: abort(404)
    if instance not in experiment.instances: abort(404)
    
    if not experiment.is_finished() and not solver_configuration.solver.user == request.User and not is_admin(): abort(401)
    
    jobs = db.session.query(db.ExperimentResult) \
                    .filter_by(experiment=experiment) \
                    .filter_by(solver_configuration=solver_configuration) \
                    .filter_by(instance=instance) \
                    .all()
    
    completed = len(filter(lambda j: j.status in JOB_FINISHED or j.status in JOB_ERROR, jobs))
    
    res = render('solver_config_results.html', experiment=experiment, solver_configuration=solver_configuration,
                  instance=instance, results=jobs, completed=completed, database=database)
    db.session.remove()
    return res
    
@app.route('/<database>/instance/<int:instance_id>')
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
    
    res = render('instance_details.html', instance=instance, instance_text=instance_text, blob_size=len(instance.instance), database=database)
    db.session.remove()
    return res
    
@app.route('/<database>/instance/<int:instance_id>/download')
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
@require_login
def solver_details(database, solver_id):
    """ Show solver details """
    db = models.get_database(database) or abort(404)
    solver = db.session.query(db.Solver).get(solver_id) or abort(404)
    if solver.user != request.User and not is_admin(): abort(401)
    
    res = render('solver_details.html', solver=solver, database=database)
    db.session.remove()
    return res

@app.route('/<database>/experiment/<int:experiment_id>/solver-configurations/<int:solver_configuration_id>')
@require_login
def solver_configuration_details(database, experiment_id, solver_configuration_id):
    """ Show solver configuration details """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    solver_config = db.session.query(db.SolverConfiguration).get(solver_configuration_id) or abort(404)
    solver = solver_config.solver
    
    if not experiment.is_finished() and solver.user != request.User and not is_admin(): abort(401)
    
    parameters = solver_config.parameter_instances
    parameters.sort(key=lambda p: p.parameter.order)
    
    res = render('solver_configuration_details.html', solver_config=solver_config, solver=solver, parameters=parameters, database=database)
    db.session.remove()
    return res
    
@app.route('/<database>/experiment/<int:experiment_id>/result/<int:result_id>')
@require_login
def experiment_result(database, experiment_id, result_id):
    """ Displays information about a single result (job) """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    result = db.session.query(db.ExperimentResult).get(result_id) or abort(404)
    
    if not experiment.is_finished() and result.solver_configuration.solver.user != request.User and not is_admin(): abort(401)
    
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
                  clientOutput_text=clientOutput_text, database=database)
    db.session.remove()
    return res
    
@app.route('/<database>/experiment/<int:experiment_id>/result/<int:result_id>/download')
@require_login
def experiment_result_download(database, experiment_id, result_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    result = db.session.query(db.ExperimentResult).get(result_id) or abort(404)
    
    if not experiment.is_finished() and result.solver_configuration.solver.user != request.User and not is_admin(): abort(401)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename=result.resultFileName)
    
    res = Response(response=result.resultFile, headers=headers)
    db.session.remove()
    return res
    
@app.route('/<database>/experiment/<int:experiment_id>/result/<int:result_id>/download-client-output')
@require_login
def experiment_result_download_client_output(database, experiment_id, result_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    result = db.session.query(db.ExperimentResult).get(result_id) or abort(404)
    
    if not experiment.is_finished() and result.solver_configuration.solver.user != request.User and not is_admin(): abort(401)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename="client_output_"+result.resultFileName)
    
    res = Response(response=result.clientOutput, headers=headers)
    db.session.remove()
    return res

@app.route('/<database>/imgtest/<int:experiment_id>')
@require_login
def imgtest(database, experiment_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    
    import random
    random.seed()

    # 2 random solverconfigs
    sc1 = random.choice(exp.solver_configurations)
    sc2 = random.choice(exp.solver_configurations)
    
    results1 = db.session.query(db.ExperimentResult)
    results1.enable_eagerloads(True).options(joinedload(db.ExperimentResult.instance, db.ExperimentResult.solver_configuration))
    results1 = results1.filter_by(experiment=exp, solver_configuration=sc1)
    
    results2 = db.session.query(db.ExperimentResult)
    results2.enable_eagerloads(True).options(joinedload(db.ExperimentResult.instance, db.ExperimentResult.solver_configuration))
    results2 = results2.filter_by(experiment=exp, solver_configuration=sc2)
    
    xs = []
    ys = []
    for instance in exp.instances:
        r1 = results1.filter_by(instance=instance).all()[0].time
        r2 = results2.filter_by(instance=instance).all()[0].time
        xs.append(r1)
        ys.append(r2)
    
    if request.args.has_key('pdf'):
        filename = os.path.join(config.TEMP_DIR, request.unique_id) + '.pdf'
        plots.scatter(xs,ys,sc1.solver.name,sc2.solver.name, exp.timeOut, filename, format='pdf')
        headers = Headers()
        headers.add('Content-Disposition', 'attachment', filename=sc1.solver.name + '_vs_' + sc2.solver.name + '.pdf')
        response = Response(response=open(filename, 'rb').read(), mimetype='application/pdf', headers=headers)
        os.remove(filename)
        return response
    elif request.args.has_key('svg'):
        return Response(response=plots.scatter(xs,ys,sc1.solver.name,sc2.solver.name, format='svg'), mimetype='image/svg+xml')
    else:
        filename = os.path.join(config.TEMP_DIR, request.unique_id) + '.png'
        plots.scatter(xs,ys,sc1.solver.name,sc2.solver.name, exp.timeOut, filename)
        response = Response(response=open(filename, 'rb').read(), mimetype='image/png')
        os.remove(filename)
        return response