# -*- coding: utf-8 -*-
"""
    edacc.views.admin
    -----------------

    This module defines request handler functions for system administration.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

from flask import Module
from flask import render_template
from flask import request, session, url_for, redirect

from edacc import config, models
from edacc.views.helpers import require_admin

admin = Module(__name__)


def render(*args, **kwargs):
    from tidylib import tidy_document
    res = render_template(*args, **kwargs)
    doc, errs = tidy_document(res)
    return doc


@admin.route('/admin/<database>/phase', methods=['GET', 'POST'])
@require_admin
def phase(database):
    competition = models.get_database(database).is_competition()
    competition_phase = models.get_database(database).competition_phase()

    if request.method == 'POST':
        competition = request.form['competition']
        competition_phase = int(request.form['competition_phase'])

        models.get_database(database).set_competition(1 if competition == 'on' else 0)
        models.get_database(database).set_competition_phase(competition_phase)
        models.get_database(database).session.commit()

    return render('/admin/phase.html', database=database, phases=range(1, 8),
                  competition=competition, competition_phase=competition_phase)

@admin.route('/admin/databases/')
@require_admin
def databases():
    """ Show a list of databases this web frontend is serving """
    databases = list(models.get_databases().itervalues())
    databases.sort(key=lambda db: db.database.lower())

    return render('/admin/databases.html', databases=databases,
                  host=config.DATABASE_HOST, port=config.DATABASE_PORT)


@admin.route('/admin/databases/add/', methods=['GET', 'POST'])
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
                return redirect(url_for('frontend.databases'))
            except Exception as e:
                error = "Can't add database: " + str(e)

    return render('/admin/databases_add.html', error=error)


@admin.route('/admin/databases/remove/<database>/')
@require_admin
def databases_remove(database):
    """Remove the specified database from the set of databases the web
       frontend is serving
    """
    models.remove_database(database)
    return redirect('admin.databases')


@admin.route('/admin/login/', methods=['GET', 'POST'])
def admin_login():
    """ Admin login form """
    if session.get('admin'):
        return redirect(url_for('frontend.databases'))

    error = None
    if request.method == 'POST':
        if request.form['password'] != config.ADMIN_PASSWORD:
            error = 'Invalid password'
        else:
            session['admin'] = True
            return redirect(url_for('admin.databases'))
    return render('/admin/login.html', error=error)


@admin.route('/admin/logout/')
def admin_logout():
    """ Log out the currently logged in admin """
    session.pop('admin', None)
    return redirect('/')
