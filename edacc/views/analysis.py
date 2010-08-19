# -*- coding: utf-8 -*-
"""
    edacc.views.analysis
    --------------------

    Defines request handler functions for all analysis related functionality.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

import os

from flask import Module
from flask import render_template as render
from flask import Response, abort, request, g
from werkzeug import Headers

from edacc import plots, config, models
from sqlalchemy.orm import joinedload
from edacc.views.helpers import require_phase, require_login

analysis = Module(__name__)

@analysis.route('/<database>/experiment/<int:experiment_id>/evaluation-solved-instances')
@require_phase(phases=(5, 6, 7))
@require_login
def evaluation_solved_instances(database, experiment_id):
    """ Shows a page with a cactus plot of the instances solved within a given amount of time of all solver configurations
        of the specified experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    return render('/analysis/solved_instances.html', database=database, experiment=experiment, db=db)


@analysis.route('/<database>/experiment/<int:experiment_id>/evaluation-cputime/')
@require_phase(phases=(5, 6, 7))
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

    return render('/analysis/cputime.html', database=database, experiment=experiment, s1=s1, s2=s2, solver1=solver1, solver2=solver2, db=db)


@analysis.route('/<database>/experiment/<int:experiment_id>/cputime-plot/<int:s1>/<int:s2>/')
@require_phase(phases=(5, 6, 7))
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
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.pdf'
        plots.scatter(xs, ys, xlabel, ylabel, title, exp.timeOut, filename, format='pdf')
        headers = Headers()
        headers.add('Content-Disposition', 'attachment', filename=sc1.solver.name + '_vs_' + sc2.solver.name + '.pdf')
        response = Response(response=open(filename, 'rb').read(), mimetype='application/pdf', headers=headers)
        os.remove(filename)
        return response
    else:
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.png'
        plots.scatter(xs, ys, xlabel, ylabel, title, exp.timeOut, filename)
        response = Response(response=open(filename, 'rb').read(), mimetype='image/png')
        os.remove(filename)
        return response


@analysis.route('/<database>/experiment/<int:experiment_id>/cactus-plot/')
@require_phase(phases=(5, 6, 7))
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
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + 'cactus.pdf'
        plots.cactus(solvers, max_x, max_y, filename, format='pdf')
        headers = Headers()
        headers.add('Content-Disposition', 'attachment', filename='instances_solved_given_time.pdf')
        response = Response(response=open(filename, 'rb').read(), mimetype='application/pdf', headers=headers)
        os.remove(filename)
        return response
    else:
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + 'cactus.png'
        plots.cactus(solvers, max_x, max_y, filename)
        response = Response(response=open(filename, 'rb').read(), mimetype='image/png')
        os.remove(filename)
        return response