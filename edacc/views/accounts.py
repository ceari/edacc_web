# -*- coding: utf-8 -*-
"""
    edacc.views.accounts
    --------------------

    This module defines request handler functions for user account management
    such as registration, login and solver submission.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

import random
import hashlib

from flask import Module
from flask import render_template as render, g
from flask import Response, abort, request, session, url_for, redirect, flash
from werkzeug import Headers, secure_filename

from edacc import utils, models, forms
from edacc.views.helpers import require_phase, require_competition, \
                                require_login, password_hash

accounts = Module(__name__)


@accounts.route('/<database>/register/', methods=['GET', 'POST'])
@require_phase(phases=(1,))
@require_competition
def register(database):
    """ User registration """
    db = models.get_database(database) or abort(404)
    form = forms.RegistrationForm()

    errors = []
    if form.validate_on_submit():
        if db.session.query(db.User).filter_by(email=form.email.data) \
                                    .count() > 0:
            errors.append("An account with this email address already exists")

        try:
            captcha = map(int, form.captcha.data.split())
            if not utils.satisfies(captcha, session['captcha']):
                errors.append("You can't register to a SAT competition without \
                    being able to solve a SAT challenge!")
        except:
            errors.append("Wrong format of the solution")

        if not errors:
            user = db.User()
            user.lastname = form.lastname.data
            user.firstname = form.firstname.data
            user.password = password_hash(form.password.data)
            user.email = form.email.data
            user.postal_address = form.address.data
            user.affiliation = form.affiliation.data

            db.session.add(user)
            try:
                db.session.commit()
            except:
                db.session.rollback()
                errors.append('Error when trying to save the account. Please \
                              contact an administrator.')
                return render('/accounts/register.html', database=database,
                              db=db, errors=errors, form=form)

            try:
                del session['captcha']
            except:
                pass
            flash('Account created successfully. You can log in now.')
            return redirect(url_for('frontend.experiments_index',
                                    database=database))

    # Save captcha to the session. The user will have to provide a solution for
    # the same captcha that was given to him.
    random.seed()
    f = utils.random_formula(2, 3)
    while not utils.SAT(f):
        f = utils.random_formula(2, 3)
    session['captcha'] = f

    return render('/accounts/register.html', database=database, db=db,
                  errors=errors, form=form)


@accounts.route('/<database>/login/', methods=['GET', 'POST'])
@require_competition
def login(database):
    """ User login form and handling for a specific database. Users can
        only be logged in to one database at a time
    """
    db = models.get_database(database) or abort(404)
    form = forms.LoginForm()

    error = None
    if form.validate_on_submit():
        user = db.session.query(db.User).filter_by(email=form.email.data).first()
        if user is None:
            error = "Invalid password or username."
        else:
            if user.password != password_hash(form.password.data):
                error = 'Invalid password or username.'
            else:
                session['logged_in'] = True
                session['database'] = database
                session['idUser'] = user.idUser
                session['email'] = user.email
                session['db'] = str(db)
                flash('Login successful')
                return redirect(url_for('frontend.experiments_index',
                                        database=database))

    return render('/accounts/login.html', database=database, error=error,
                  db=db, form=form)


@accounts.route('/<database>/logout')
@require_login
@require_competition
def logout(database):
    """ User logout for a database """

    session.pop('logged_in', None)
    session.pop('database', None)
    return redirect('/')


@accounts.route('/<database>/submit-solver/<int:id>', methods=['GET', 'POST'])
@accounts.route('/<database>/submit-solver/', methods=['GET', 'POST'])
@require_login
@require_phase(phases=(1,))
@require_competition
def submit_solver(database, id=None):
    """ Form to submit solvers to a database """
    db = models.get_database(database) or abort(404)
    user = db.session.query(db.User).get(session['idUser'])

    if id:
        solver = db.session.query(db.Solver).get(id) or abort(404)
        if solver.user != user:
            abort(401)

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
            error = 'You have to provide a zip-archive containing \
                    the source code'
            valid = False

        bin = binary.read()
        hash = hashlib.md5()
        hash.update(bin)
        if not id and db.session.query(db.Solver) \
                        .filter_by(md5=hash.hexdigest()).first() is not None:
            error = 'Solver with this binary already exists'
            valid = False

        if not id and db.session.query(db.Solver) \
                        .filter_by(name=name, version=version) \
                        .first() is not None:
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
            solver.user = g.User

            if not id:
                db.session.add(solver)

            # on resubmissions delete old parameters
            if id:
                for p in solver.parameters:
                    db.session.delete(p)
                db.session.commit()

            for p in params:
                param = db.Parameter()
                param.name = p[0]
                param.prefix = p[1]
                param.value = p[2]
                # p[3] actually means 'is boolean'
                param.hasValue = not p[3]
                param.order = p[4]
                param.solver = solver
                db.session.add(param)
            try:
                db.session.commit()
            except:
                db.session.rollback()
                flash("Couldn't save solver to the database")
                return render('submit_solver.html', database=database,
                              error=error, db=db, id=id)

            flash('Solver submitted successfully')
            return redirect(url_for('frontend.experiments_index',
                                    database=database))

    return render('submit_solver.html', database=database, error=error,
                  db=db, id=id)


@accounts.route('/<database>/solvers')
@require_login
@require_competition
def list_solvers(database):
    """ Lists all solvers that the currently logged in user submitted to
        the database
    """
    db = models.get_database(database) or abort(404)
    solvers = db.session.query(db.Solver).filter_by(user=g.User).all()

    return render('list_solvers.html', database=database,
                  solvers=solvers, db=db)


@accounts.route('/<database>/download-solver/<int:id>/')
@require_login
@require_competition
@require_phase(phases=(1, 2, 3, 4))
def download_solver(database, id):
    """ Lets a user download the binaries of his own solvers """
    db = models.get_database(database) or abort(404)
    solver = db.session.query(db.Solver).get(id) or abort(404)
    if solver.user != g.User:
        abort(401)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment',
                filename=solver.binaryName)

    res = Response(response=solver.binary, headers=headers)
    db.session.remove()
    return res


@accounts.route('/<database>/download-solver-code/<int:id>/')
@require_login
@require_competition
@require_phase(phases=(1, 2, 3, 4))
def download_solver_code(database, id):
    """ Lets a user download the binaries of his own solvers """
    db = models.get_database(database) or abort(404)
    solver = db.session.query(db.Solver).get(id) or abort(404)
    if solver.user != g.User:
        abort(401)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment',
                filename=solver.name + ".zip")

    res = Response(response=solver.code, headers=headers)
    db.session.remove()
    return res
