from flask import Module
from flask import render_template as render
from flask import Response, abort, request, session, url_for, redirect, flash, Request

from edacc import utils, models
from edacc.views.helpers import require_phase, require_competition, require_login, password_hash

accounts = Module(__name__)

@accounts.route('/<database>/register/', methods=['GET', 'POST'])
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
            return redirect(url_for('frontend.experiments_index', database=database))
            
    random.seed()
    f = utils.random_formula(2,3)
    while not utils.SAT(f):
        f = utils.random_formula(2,3)
    session['captcha'] = f
    
    return render('/accounts/register.html', database=database, db=db, error=error)

@accounts.route('/<database>/login/', methods=['GET', 'POST'])
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
                return redirect(url_for('frontend.experiments_index', database=database))
    
    return render('/accounts/login.html', database=database, error=error, db=db)

@accounts.route('/<database>/logout')
@require_login
@require_competition
def logout(database):
    """ User logout for a database """
    db = models.get_database(database) or abort(404)
    
    session.pop('logged_in', None)
    session.pop('database', None)
    return redirect('/')

@accounts.route('/<database>/submit-solver/<int:id>', methods=['GET', 'POST']) # for resubmissions of the same solver
@accounts.route('/<database>/submit-solver/', methods=['GET', 'POST'])
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
            return redirect(url_for('frontend.experiments_index', database=database))
    
    return render('submit_solver.html', database=database, error=error, db=db, id=id)
    
@accounts.route('/<database>/solvers')
@require_login
@require_competition
def list_solvers(database):
    """ Lists all solvers that the currently logged in user submitted to the database """
    db = models.get_database(database) or abort(404)
    solvers = db.session.query(db.Solver).filter_by(user=request.User).all()
   
    return render('list_solvers.html', database=database, solvers=solvers, db=db)
    
@accounts.route('/<database>/download-solver/<int:id>/')
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

@accounts.route('/<database>/download-solver-code/<int:id>/')
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

