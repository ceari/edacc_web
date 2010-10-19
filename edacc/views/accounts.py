# -*- coding: utf-8 -*-
"""
    edacc.views.accounts
    --------------------

    This module defines request handler functions for user account management
    such as registration, login and solver submission.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

import itertools
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


#def render(*args, **kwargs):
#    from tidylib import tidy_document
#    res = render_template(*args, **kwargs)
#    doc, errs = tidy_document(res)
#    return doc


@accounts.route('/<database>/register/', methods=['GET', 'POST'])
@require_phase(phases=(2,))
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


@accounts.route('/<database>/manage/')
@require_login
@require_competition
def manage(database):
    """ Management for users with links to solver and benchmark submission """
    db = models.get_database(database) or abort(404)

    return render('/accounts/manage.html', database=database, db=db)


@accounts.route('/<database>/submit-benchmark/', methods=['GET', 'POST'])
@require_login
@require_phase(phases=(2,))
@require_competition
def submit_benchmark(database):
    db = models.get_database(database) or abort(404)

    form = forms.BenchmarkForm(request.form)
    form.source_class.query = db.session.query(db.InstanceClass).filter_by(user=g.User)
    form.benchmark_type.query = db.session.query(db.BenchmarkType).filter_by(user=g.User)

    error = None
    if form.validate_on_submit():
        name = form.name.data.strip()
        instance_name = form.instance.file.filename
        instance_blob = form.instance.file.read()

        md5sum = hashlib.md5()
        md5sum.update(instance_blob)
        md5sum = md5sum.hexdigest()

        instance = db.Instance()
        instance.name = secure_filename(instance_name) if name == '' else secure_filename(name)
        if db.session.query(db.Instance).filter_by(name=instance.name).first() is not None:
            error = 'A benchmark with this name already exists.'

        instance.instance = instance_blob
        instance.md5 = md5sum
        db.session.add(instance)

        if form.benchmark_type.data is None:
            benchmark_type = db.BenchmarkType()
            db.session.add(benchmark_type)
            benchmark_type.name = secure_filename(form.new_benchmark_type.data)
            benchmark_type.user = g.User
            instance.benchmark_type = benchmark_type
        else:
            instance.benchmark_type = form.benchmark_type.data

        if form.source_class.data is None:
            source_class = db.InstanceClass()
            db.session.add(source_class)
            source_class.name = form.new_source_class.data
            source_class.description = form.new_source_class_description.data
            source_class.source = True
            source_class.user = g.User
            instance.source_class = source_class
        else:
            instance.source_class = form.source_class.data

        if not error:
            try:
                db.session.commit()
                flash('Benchmark submitted.')
                return redirect(url_for('accounts.submit_benchmark',
                                        database=database))
            except:
                db.session.rollback()
                flash('An error occured during benchmark submission.')
                return redirect(url_for('frontend.experiments_index',
                                        database=database))

    return render('/accounts/submit_benchmark.html', db=db, database=database,
                  form=form, error=error)


@accounts.route('/<database>/submit-solver/<int:id>', methods=['GET', 'POST'])
@accounts.route('/<database>/submit-solver/', methods=['GET', 'POST'])
@require_login
@require_phase(phases=(2, 4))
@require_competition
def submit_solver(database, id=None):
    """ Form to submit solvers to a database """
    db = models.get_database(database) or abort(404)

    # Disallow submissions of new solvers in phase 4
    if db.competition_phase() == 4 and id is None:
        abort(401)

    if id is not None:
        solver = db.session.query(db.Solver).get(id) or abort(404)
        if solver.user != g.User:
            abort(401)
        form = forms.SolverForm(request.form, solver)
        form.binary.data = ''
        form.code.data = ''
        if request.method == 'GET':
            form.parameters.data = ''
    else:
        form = forms.SolverForm(request.form)

    form.competition_categories.query = db.session.query(db.CompetitionCategory).all()

    error = None
    if form.validate_on_submit():
        name = form.name.data
        description = form.description.data
        version = form.version.data
        authors = form.authors.data
        parameters = form.parameters.data

        valid = True
        bin = request.files[form.binary.name].read()
        hash = hashlib.md5()
        hash.update(bin)
        if id is None and db.session.query(db.Solver) \
                        .filter_by(md5=hash.hexdigest()).first() is not None:
            error = 'Solver with this binary already exists'
            valid = False

        if id is None and db.session.query(db.Solver) \
                        .filter_by(name=name, version=version) \
                        .first() is not None:
            error = 'Solver with this name and version already exists'
            valid = False

        params = utils.parse_parameters(parameters)

        if valid:
            if id is None:
                solver = db.Solver()
            solver.name = name
            solver.binaryName = secure_filename(form.binary.data)
            solver.binary = bin
            solver.md5 = hash.hexdigest()
            solver.description = description
            solver.code = request.files[form.code.name].read()
            solver.version = version
            solver.authors = authors
            solver.user = g.User
            solver.competition_categories = form.competition_categories.data

            if id is None:
                db.session.add(solver)

            # on resubmissions delete old parameters
            if id is not None:
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
                param.order = int(p[4])
                param.solver = solver
                db.session.add(param)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash("Couldn't save solver to the database. Please contact an administrator for support.")
                return render('/accounts/submit_solver.html', database=database,
                              error=error, db=db, id=id, form=form)

            flash('Solver submitted successfully')
            return redirect(url_for('accounts.list_solvers',
                                    database=database))

    return render('/accounts/submit_solver.html', database=database, error=error,
                  db=db, id=id, form=form)


@accounts.route('/<database>/manage/solvers/')
@require_login
@require_competition
def list_solvers(database):
    """ Lists all solvers that the currently logged in user submitted to
        the database
    """
    db = models.get_database(database) or abort(404)
    solvers = db.session.query(db.Solver).filter_by(user=g.User).all()

    return render('/accounts/list_solvers.html', database=database,
                  solvers=solvers, db=db)


@accounts.route('/<database>/manage/benchmarks/')
@require_login
@require_competition
def list_benchmarks(database):
    """ Lists all benchmarks that the currently logged in user submitted to the
        database
    """
    db = models.get_database(database) or abort(404)
    user_source_classes = db.session.query(db.InstanceClass).filter_by(user=g.User).all()
    instances = list(itertools.chain(*[sc.source_instances for sc in user_source_classes]))

    return render('/accounts/list_benchmarks.html', database=database,
                  db=db, instances=instances)


@accounts.route('/<database>/download-solver/<int:id>/')
@require_login
@require_competition
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

    return Response(response=solver.binary, headers=headers)


@accounts.route('/<database>/download-solver-code/<int:id>/')
@require_login
@require_competition
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

    return Response(response=solver.code, headers=headers)
