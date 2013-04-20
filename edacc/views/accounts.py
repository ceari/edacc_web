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
import time
import hashlib
import zipfile
import tempfile
import datetime
import os
from cStringIO import StringIO

from flask import Blueprint
from flask import render_template as render, g
from flask import Response, abort, request, session, url_for, redirect, flash
from flask.ext.mail import Message
from werkzeug import Headers, secure_filename

from edacc import utils, models, forms, config, constants
from edacc.views.helpers import require_phase, require_competition, \
                                require_login, password_hash, redirect_ssl,\
                                require_admin, is_admin
from edacc.web import mail

accounts = Blueprint('accounts', __name__, template_folder='static')


#def render(*args, **kwargs):
#    from tidylib import tidy_document
#    res = render_template(*args, **kwargs)
#    doc, errs = tidy_document(res)
#    return doc


@accounts.route('/<database>/register/', methods=['GET', 'POST'])
@require_phase(phases=(2,))
@require_competition
@redirect_ssl
def register(database):
    """ User registration """
    db = models.get_database(database) or abort(404)
    form = forms.RegistrationForm()

    errors = []
    if form.validate_on_submit():
        if db.session.query(db.User).filter_by(email=form.email.data.lower()) \
                                    .count() > 0:
            errors.append("An account with this email address already exists. Please check your e-mail account for the activation link.")

        try:
            captcha = map(int, form.captcha.data.split())
            if not utils.satisfies(captcha, session['captcha']):
                errors.append("Wrong solution to the captcha challenge.")
        except:
            errors.append("Wrong format of the solution")

        if not errors:
            user = db.User()
            user.lastname = form.lastname.data
            user.firstname = form.firstname.data
            user.password = password_hash(form.password.data)
            user.email = form.email.data.lower() # store email in lower case for easier password reset etc
            user.postal_address = form.address.data
            user.affiliation = form.affiliation.data
            user.verified = False
            user.accepted_terms = form.accepted_terms.data
            user.affiliation_type = form.affiliation_type.data
            user.country = form.country.data

            hash = hashlib.sha256()
            hash.update(config.SECRET_KEY)
            hash.update(user.email)
            hash.update(str(datetime.datetime.now()))
            hash.update(user.password)
            user.activation_hash = hash.hexdigest()

            db.session.add(user)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                errors.append('Error while trying to save the account to the database. Please \
                              contact an administrator.')
                return render('/accounts/register.html', database=database,
                              db=db, errors=errors, form=form)

            session.pop('captcha', None)

            msg = Message("[" + db.label + "] Account activation",
                          recipients=[user.email])
            msg.body = "Dear " + user.firstname + " " + user.lastname + ",\n\n" + \
                       "Please use the following link to activate your account:\n" + \
                       request.url_root[:-1] + url_for('accounts.activate', database=database, activation_hash=user.activation_hash)
            mail.send(msg)
            flash("Account created successfully. An e-mail has been sent to your account with an activation link.")
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

@accounts.route('/<database>/activate/<activation_hash>')
@require_phase(phases=(2,))
@require_competition
def activate(database, activation_hash):
    db = models.get_database(database) or abort(404)
    user = db.session.query(db.User).filter_by(activation_hash=activation_hash).first() or abort(404)
    user.activation_hash = ""
    try:
        db.session.commit()
        user = db.session.query(db.User).filter_by(email=user.email).first()
        msg = Message("[" + db.label + "][Admin] Account was activated",
            recipients=[config.DEFAULT_MAIL_SENDER])
        msg.body = ("The following account was just activated by a user:\n\n" + \
                   "Last name: %s\n" \
                   "First name: %s\n" \
                   "E-mail: %s\n" \
                   "Postal address: %s\n" \
                   "Affiliation: %s\n" \
                   "Affiliation type: %s\n" \
                   "Country: %s\n\n\n" \
                   "Use the following link to verify this user: " + request.url_root[:-1] + url_for('accounts.verify_user', database=database, user_id=user.idUser)) \
                    % (user.lastname, user.firstname, user.email, user.postal_address, user.affiliation, user.affiliation_type, user.country)
        mail.send(msg)
        flash('Account activated. You will be able to log in when your account was verified by an administrator.')
    except Exception as e:
        db.session.rollback()
        print e
        flash('Could not activate account. Please contact an administrator.')
    return redirect(url_for('frontend.experiments_index',
        database=database))

@accounts.route('/<database>/verify-user/<int:user_id>/')
@require_competition
@require_admin
def verify_user(database, user_id):
    db = models.get_database(database) or abort(404)
    user = db.session.query(db.User).get(user_id) or abort(404)
    if user.verified:
        flash('User already verified.')
        return redirect(url_for('frontend.experiments_index',
            database=database))

    user.verified = True
    try:
        db.session.commit()
        msg = Message("[" + db.label + "] Account verified",
            recipients=[user.email])
        msg.body = "Dear " + user.firstname + " " + user.lastname + ",\n\n" +\
                   "Your account was verified and you can now log in:\n" +\
                   request.url_root[:-1] + url_for('accounts.login', database=database)
        mail.send(msg)
        flash('Verified the account.')
    except Exception as e:
        db.session.rollback()
        flash("Couldn't update verification status of user or send the notification mail: " + str(e))

    return redirect(url_for('frontend.experiments_index',
        database=database))

@accounts.route('/<database>/login/', methods=['GET', 'POST'])
@require_competition
@redirect_ssl
def login(database):
    """ User login form and handling for a specific database. Users can
        only be logged in to one database at a time
    """
    db = models.get_database(database) or abort(404)
    form = forms.LoginForm(csrf_enabled=False)

    error = None
    if form.validate_on_submit():
        user = db.session.query(db.User).filter_by(email=form.email.data).first()
        if user is None:
            error = "Invalid password or username."
        else:
            if user.activation_hash:
                error = "Account not activated yet. Please check your e-mail account, otherwise contact an administrator."
            elif not user.verified:
                error = "Account was not verified yet. Please wait for an administrator to verify your account. You will be notified by e-mail."
            elif user.password != password_hash(form.password.data):
                error = 'Invalid password or username.'
            else:
                session['logged_in'] = True
                session['database'] = database
                session['idUser'] = user.idUser
                session['email'] = user.email
                session['db'] = str(db)
                session['admin'] = user.admin
                session.permanent = form.permanent_login.data

#                if db.is_competition() and db.competition_phase() == 5:
#                    if not user.admin:
#                        session.pop('logged_in', None)
#                        flash('Website offline for competition computations.')
#                        return redirect(url_for('frontend.experiments_index',
#                            database=database))

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
    session.pop('admin', None)
    return redirect(url_for('frontend.experiments_index', database=database))


@accounts.route('/<database>/manage/')
@require_login
@require_competition
@redirect_ssl
def manage(database):
    """ Management for users with links to solver and benchmark submission """
    db = models.get_database(database) or abort(404)

    return render('/accounts/manage.html', database=database, db=db)

@accounts.route('/<database>/submit-benchmarks/', methods=['GET', 'POST'])
@require_login
@require_phase(phases=(2, 4, 5))
@require_competition
def submit_benchmarks(database):
    db = models.get_database(database) or abort(404)
    form = forms.BenchmarksForm()

    if form.validate_on_submit():
        upload_dir = os.path.join(config.UPLOAD_FOLDER, database, str(g.User.idUser))
        move_dir = os.path.join(config.UPLOAD_FOLDER, database, secure_filename(form.category.data), str(g.User.idUser))
        try: os.makedirs(upload_dir, mode=0700)
        except: pass
        try: os.makedirs(move_dir, mode=0700)
        except: pass

        try:
            for file in session.get('benchmarks', list()):
                try:
                    os.rename(os.path.join(upload_dir, file), os.path.join(move_dir, file))
                except Exception as ex:
                    print ex

            flash('Benchmark submission successful.')
            try:
                msg = Message("[" + db.label + "][Admin] Benchmarks submitted",
                    recipients=[config.DEFAULT_MAIL_SENDER])
                msg.body = ("The user %s %s with id %d just submitted some benchmarks" % (g.User.firstname, g.User.lastname, g.User.idUser))
                mail.send(msg)
            except:
                pass
            session.pop('benchmarks', None)
            return redirect(url_for('frontend.experiments_index', database=database))

        except Exception as ex:
            print ex
            flash('Error occured when trying to move the uploaded files.')

    return render('/accounts/submit_benchmarks.html', db=db, database=database, form=form)

@accounts.route('/<database>/upload-benchmarks/', methods=['GET', 'POST'])
@require_login
@require_phase(phases=(2, 4, 5))
@require_competition
def upload_benchmarks(database):
    db = models.get_database(database) or abort(404)

    if request.files:
        upload_dir = os.path.join(config.UPLOAD_FOLDER, database, str(g.User.idUser))
        filename = secure_filename(request.files['file'].filename)
        # save list of uploaded files in user session so we can track them until form submission
        benchmarks = session.get('benchmarks', list())
        benchmarks.append(filename)
        session['benchmarks'] = benchmarks
        try:
            os.makedirs(upload_dir, mode=0700)
        except:
            pass
        request.files['file'].save(os.path.join(upload_dir, filename))

    return 'success'

#@accounts.route('/<database>/submit-benchmark/', methods=['GET', 'POST'])
#@require_login
#@require_phase(phases=(2,))
#@require_competition
#def submit_benchmark(database):
#    db = models.get_database(database) or abort(404)
#
#    form = forms.BenchmarkForm(request.form)
#    form.source_class.query = db.session.query(db.InstanceClass).filter_by(user=g.User)
#    form.benchmark_type.query = db.session.query(db.BenchmarkType).filter_by(user=g.User)
#
#    error = None
#    if form.validate_on_submit():
#        name = form.name.data.strip()
#        instance_name = form.instance.file.filename
#        instance_blob = form.instance.file.read()
#
#        md5sum = hashlib.md5()
#        md5sum.update(instance_blob)
#        md5sum = md5sum.hexdigest()
#
#        instance = db.Instance()
#        instance.name = str(g.User.idUser) + "_" + (secure_filename(instance_name) if name == '' else secure_filename(name))
#        if db.session.query(db.Instance).filter_by(name=instance.name).first() is not None:
#            error = 'A benchmark with this name already exists.'
#
#        instance.instance = instance_blob
#        instance.md5 = md5sum
#        db.session.add(instance)
#
#        if form.benchmark_type.data is None:
#            benchmark_type = db.BenchmarkType()
#            db.session.add(benchmark_type)
#            benchmark_type.name = secure_filename(form.new_benchmark_type.data)
#            benchmark_type.user = g.User
#            instance.benchmark_type = benchmark_type
#        else:
#            instance.benchmark_type = form.benchmark_type.data
#
#        if form.source_class.data is None:
#            source_class = db.InstanceClass()
#            db.session.add(source_class)
#            source_class.name = form.new_source_class.data
#            source_class.description = form.new_source_class_description.data
#            source_class.parent = None
#            source_class.user = g.User
#            instance.instance_classes.append(source_class)
#        else:
#            instance.instance_classes.append(source_class)
#
#        if not error:
#            try:
#                db.session.commit()
#                flash('Benchmark submitted.')
#                return redirect(url_for('accounts.submit_benchmark',
#                                        database=database))
#            except:
#                db.session.rollback()
#                flash('An error occured during benchmark submission.')
#                return redirect(url_for('frontend.experiments_index',
#                                        database=database))
#
#    return render('/accounts/submit_benchmark.html', db=db, database=database,
#                  form=form, error=error)


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
        if solver.user.idUser != g.User.idUser: abort(401)
        if db.competition_phase() == 4 and solver.competition_frozen:
            flash('This solver was found to be compatible with our execution environment, i.e. has no crashed test runs or test runs with unknown result, and can not be updated anymore. Please contact the organizers if there\'s a reason to submit a new version.')
            return redirect(url_for('accounts.list_solvers',
                database=database, user_id=g.User.idUser))

        solver_binary = solver.binaries[0] if solver.binaries else None
        form = forms.SolverForm(request.form, solver)
        if request.method == 'GET':
            form.parameters.data = utils.parameter_template(solver)
            form.description_pdf.data = ''
            form.code.data = ''
    else:
        form = forms.SolverForm()

    form.competition_categories.query = db.session.query(db.CompetitionCategory).all()

    error = None
    if form.validate_on_submit():
        valid = True # assume valid, try to falsify with the following checks

        name = form.name.data
        description = form.description.data
        version = form.version.data
        authors = form.authors.data
        parameters = form.parameters.data

        if id is None and db.session.query(db.Solver)\
                          .filter_by(name=name, version=version)\
                          .first() is not None:
            error = 'Solver with this name and version already exists'
            valid = False

        if id is None and not form.code.data:
            error = 'Please provide the code zip archive.'
            valid = False

        code = None
        if id is None or (id is not None and 'code' in request.files):
            code = request.files['code'].read()
            code_hash = hashlib.md5()
            code_hash.update(code)

        description_pdf = None
        if id is None or (id is not None and 'description_pdf' in request.files):
            description_pdf = request.files[form.description_pdf.name].read()
        if id is None and not description_pdf:
            valid = False
            error = "Please provide a description PDF."

        params = utils.parse_parameters(parameters)

        if valid:
            if id is None:
                solver = db.Solver()
                solver_binary = None
            else:
                if solver_binary:
                    # Remove all current solver configurations and jobs
                    for solver_config in solver_binary.solver_configurations:
                        for pi in solver_config.parameter_instances: db.session.delete(pi)
                        db.session.commit()
                        db.session.delete(solver_config)
                    db.session.commit()

            solver.name = name
            solver.description = description
            solver.authors = authors
            solver.user = g.User
            solver.version = version
            solver.competition_categories = form.competition_categories.data
            if code is not None:
                # new or updated code
                solver.code = code

                # save the code in the FS as log
                store_path = os.path.join(config.UPLOAD_FOLDER, 'solvers', secure_filename(str(g.User.idUser) + '-' + g.User.lastname), 'code')
                try:
                    os.makedirs(store_path)
                except: pass
                with open(os.path.join(store_path, code_hash.hexdigest() + '.zip'), 'wb') as f:
                    f.write(code)

            if description_pdf:
                # new or updated description pdf
                solver.description_pdf = description_pdf

            # save run command to text file along the code
            store_path = os.path.join(config.UPLOAD_FOLDER, 'solvers', secure_filename(str(g.User.idUser) + '-' + g.User.lastname), 'code')
            try:
                os.makedirs(store_path)
            except: pass
            with open(os.path.join(store_path, code_hash.hexdigest() + '.txt'), 'wb') as f:
                f.write(form.run_command.data)

            db.session.add(solver)

            # on resubmissions delete old parameters
            if id is not None:
                for p in solver.parameters:
                    db.session.delete(p)
                db.session.commit()

            for p in params:
                param = db.Parameter()
                param.name = None if p[0] == '' else p[0]
                param.prefix = None if p[1] == '' else p[1]
                param.defaultValue = p[2] or ''
                param.hasValue = not p[3] # p[3] actually means 'is boolean (flag)'
                param.order = int(p[4])
                param.space = p[5]
                param.solver = solver
                db.session.add(param)
            try:
                db.session.commit()
                if code:
                    msg = Message("[" + db.label + "][Admin] Code submitted",
                        recipients=[config.DEFAULT_MAIL_SENDER])
                    msg.body = ("The user %s %s just submitted code for the solver with id %d.\n\nArchive MD5: %s" % (g.User.firstname, g.User.lastname, solver.idSolver, code_hash.hexdigest()))
                    mail.send(msg)
            except Exception as e:
                print e
                db.session.rollback()
                flash("Couldn't save solver to the database. Please contact an administrator for support.")
                return render('/accounts/submit_solver.html', database=database,
                              error=error, db=db, id=id, form=form)

            flash('Solver submitted successfully. Once we compiled your solver and ran the test experiments, you will be notified by email. Please check the results page at any time for the computation progress.')
            return redirect(url_for('accounts.list_solvers',
                                    database=database, user_id=g.User.idUser))

    return render('/accounts/submit_solver.html', database=database, error=error,
                  db=db, id=id, form=form)


@accounts.route('/<database>/list-solver-descriptions/', methods=['GET'])
@require_login
@require_admin
def list_solver_descriptions(database):
    db = models.get_database(database) or abort(404)

    solvers = [s for s in db.session.query(db.Solver).all() if s.User_idUser]
    filtered_solvers = []
    for s in solvers:
        if not any(ss.description_pdf == s.description_pdf and s.description_pdf for ss in filtered_solvers):
            filtered_solvers.append(s)


    solvers_by_category = dict()
    filtered_solvers_by_category = dict()
    for category in db.session.query(db.CompetitionCategory).all():
        solvers_by_category[category] = [s for s in category.solvers if s.User_idUser]
        filtered_solvers_by_category[category] = []
        for s in solvers_by_category[category]:
            if not any(ss.description_pdf == s.description_pdf and s.description_pdf for ss in filtered_solvers_by_category[category]):
                filtered_solvers_by_category[category].append(s)

    return render('/accounts/list_solver_descriptions.html', database=database, categories=sorted(solvers_by_category.keys(), key=lambda c: c.name),
        db=db, solvers=solvers, solvers_by_category=solvers_by_category, sorted=sorted, filtered_solvers=filtered_solvers,
        filtered_solvers_by_category=filtered_solvers_by_category)


@accounts.route('/<database>/delete-solver/<int:solver_id>', methods=['GET'])
@require_login
@require_phase(phases=(2, 4))
@require_competition
def delete_solver(database, solver_id):
    db = models.get_database(database) or abort(404)
    solver = db.session.query(db.Solver).get(solver_id) or abort(404)
    if solver.user.idUser != g.User.idUser: abort(401)

    try:
        for solver_binary in solver.binaries:
            for solver_config in solver_binary.solver_configurations:
                for pi in solver_config.parameter_instances: db.session.delete(pi)
                db.session.commit()
                db.session.delete(solver_config)
            db.session.commit()
            db.session.delete(solver_binary)
        for p in solver.parameters: db.session.delete(p)
        db.session.delete(solver)
        db.session.commit()
        flash('Solver deleted successfully.')
    except Exception as e:
        print e
        db.session.rollback()
        flash('Could not delete solver. Please contact an administrator.')

    return redirect(url_for('accounts.list_solvers', database=database, user_id=None))

@accounts.route('/<database>/reset-password/', methods=['GET', 'POST'])
@require_competition
def reset_password(database):
    db = models.get_database(database) or abort(404)
    form = forms.ResetPasswordForm()

    if form.validate_on_submit():
        # find user by lower case email address
        user = db.session.query(db.User).filter_by(email=form.email.data.lower()).first()
        if not user or not user.verified:
            if not user: flash('No account with this e-mail address exists.')
            if user and not user.verified: flash('Account was not verified yet.')
            return render('/accounts/reset_password.html', db=db, database=database, form=form)

        hash = hashlib.sha256()
        hash.update(config.SECRET_KEY)
        hash.update(user.email)
        hash.update(str(datetime.datetime.now()))
        hash.update(user.password)
        # reuse the activation hash (user should be activated at this point already)
        user.activation_hash = 'pw_reset_' + hash.hexdigest()

        try:
            db.session.commit()

            msg = Message("[" + db.label + "] Password reset instructions",
                recipients=[user.email])
            msg.body = "Dear " + user.firstname + " " + user.lastname + ",\n\n" +\
                       "If you did not use the password reset link on the website ignore this mail.\n\n" +\
                       "To reset your password please use the following link:\n" +\
                       request.url_root[:-1] + url_for('accounts.change_password', database=database, reset_hash=hash.hexdigest())
            mail.send(msg)

            flash('E-mail was sent. Please refer to the mail for further instructions.')
        except Exception as e:
            print e
            flash('Could not send reset mail. Please contact an administrator.')

    return render('/accounts/reset_password.html', db=db, database=database, form=form)

@accounts.route('/<database>/change-password/<reset_hash>', methods=['GET', 'POST'])
@require_competition
def change_password(database, reset_hash):
    db = models.get_database(database) or abort(404)
    user = db.session.query(db.User).filter_by(activation_hash='pw_reset_'+reset_hash).first() or abort(404)

    form = forms.ChangePasswordForm()
    if form.validate_on_submit():
        user.activation_hash = ''
        user.password = password_hash(form.password.data)

        try:
            db.session.commit()
            flash('Password changed.')
        except Exception as e:
            print e
            flash('Could not set password in db. Please contact an administrator.')

        return redirect(url_for('frontend.experiments_index',
                database=database))

    return render('/accounts/change_password.html', db=db, database=database, form=form, reset_hash=reset_hash)

@accounts.route('/<database>/manage/solvers/')
@accounts.route('/<database>/manage/solvers/<int:user_id>')
@require_login
@require_competition
def list_solvers(database, user_id=None):
    """ Lists all solvers that the user submitted to
        the database
    """
    db = models.get_database(database) or abort(404)
    user = db.session.query(db.User).get(user_id or g.User.idUser) or abort(404)

    if is_admin() and user_id:
        solvers = db.session.query(db.Solver).filter_by(User_idUser=user_id).all()
    else:
        if user_id and g.User.idUser != user_id: abort(401)
        solvers = db.session.query(db.Solver).filter_by(user=g.User).all()

    return render('/accounts/list_solvers.html', database=database, user=user,
                  solvers=solvers, db=db)


@accounts.route('/<database>/users/')
@require_admin
@require_competition
def list_users(database):
    db = models.get_database(database) or abort(404)
    return render('/accounts/list_users.html', db=db, database=database, users=db.session.query(db.User).all())

@accounts.route('/<database>/manage/benchmarks/')
@accounts.route('/<database>/manage/benchmarks/<int:user_id>')
@require_login
@require_competition
def list_benchmarks(database, user_id=None):
    """ Lists all benchmarks that the currently logged in user submitted.
    """
    db = models.get_database(database) or abort(404)
    uploaded_files = {}
    directory = os.path.join(config.UPLOAD_FOLDER, database)
    for file in os.listdir(directory):
        if os.path.isdir(os.path.join(directory, file)):
            for user_dir in os.listdir(os.path.join(directory, file)):
                if (is_admin() and user_id and user_dir == str(user_id)) or (not user_id and user_dir == str(g.User.idUser)):
                    if not file in uploaded_files: uploaded_files[file] = list()
                    files = os.listdir(os.path.join(directory, file, user_dir))
                    files_full_path = [os.path.join(directory, file, user_dir, f) for f in files]
                    uploaded_files[file] += zip(files, [time.ctime(os.path.getmtime(f)) for f in files_full_path])

    return render('/accounts/list_benchmarks.html', database=database,
                  db=db, uploaded_files=uploaded_files, user_id=user_id)

@accounts.route('/<database>/manage/admin-benchmarks/')
@require_login
@require_admin
@require_competition
def admin_list_benchmarks(database):
    """ Lists all benchmarks that the currently logged in user submitted.
    """
    db = models.get_database(database) or abort(404)
    uploaded_files = {}
    directory = os.path.join(config.UPLOAD_FOLDER, database)
    for file in os.listdir(directory):
        if os.path.isdir(os.path.join(directory, file)):
            for user_dir in os.listdir(os.path.join(directory, file)):
                if not file in uploaded_files: uploaded_files[file] = list()
                files = os.listdir(os.path.join(directory, file, user_dir))
                files_full_path = [os.path.join(directory, file, user_dir, f) for f in files]
                files_sizes = [os.stat(f).st_size for f in files_full_path]
                uploaded_files[file] += zip(files, [time.ctime(os.path.getmtime(f)) for f in files_full_path], [user_dir] * len(files), files_sizes)

    return render('/accounts/admin_list_benchmarks.html', database=database,
        db=db, uploaded_files=uploaded_files)

@accounts.route('/<database>/manage/admin-download-benchmark/<category>/<user_dir>/<filename>')
@require_login
@require_admin
@require_competition
def admin_download_benchmark(database, category, user_dir, filename):
    directory = os.path.join(config.UPLOAD_FOLDER, database)

    import mimetypes

    headers = Headers()
    headers.add('Content-Type', mimetypes.guess_type(filename))
    headers.add('Content-Disposition', 'attachment', filename=secure_filename(filename))

    return Response(response=open(os.path.join(directory, category, user_dir, filename), 'rb'), headers=headers)

@accounts.route('/<database>/manage/admin-toggle-solver-freeze/<int:solver_id>/')
@require_login
@require_admin
@require_competition
def admin_toggle_solver_freeze(database, solver_id):
    db = models.get_database(database) or abort(404)
    solver = db.session.query(db.Solver).get(solver_id) or abort(404)

    solver.competition_frozen = not solver.competition_frozen
    try:
        db.session.commit()
    except:
        db.session.rollback()
        flash('DB error when commiting. Rolled back.')

    return redirect(url_for('frontend.solver_details',
        database=database, solver_id=solver_id))

@accounts.route('/<database>/manage/update-description/<int:solver_id>/', methods=['GET', 'POST'])
@require_login
@require_admin
@require_competition
def update_description(database, solver_id):
    db = models.get_database(database) or abort(404)
    solver = db.session.query(db.Solver).get(solver_id) or abort(404)
    form = forms.UpdateDescriptionForm()

    if form.validate_on_submit():
        solver.description_pdf = request.files[form.description_pdf.name].stream.read()

        try:
            db.session.commit()
            flash("Solver description updated.")
            return redirect(url_for('accounts.list_submitted_solvers',
                database=database))
        except Exception as e:
            db.session.rollback()
            flash("Error updating description: " + str(e))

    return render("/accounts/update_description.html", database=database, db=db, solver=solver, form=form)

@accounts.route('/<database>/manage/list-submitted-solvers/')
@require_login
@require_admin
@require_competition
def list_submitted_solvers(database):
    db = models.get_database(database) or abort(404)
    solvers = db.session.query(db.Solver).filter(db.Solver.User_idUser!=None).order_by(db.Solver.name).all()

    return render("/accounts/list_submitted_solvers.html", database=database, db=db, solvers=solvers)
