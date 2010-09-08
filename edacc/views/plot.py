# -*- coding: utf-8 -*-
"""
    edacc.views.plot
    ----------------

    Plot view functions.

    The handlers defined in this module return the plotted images as
    HTTP responses.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

import os
import json
import numpy

from flask import Module
from flask import render_template, url_for
from flask import Response, abort, request, g
from werkzeug import Headers

from edacc import plots, config, models, forms, ranking
from sqlalchemy.orm import joinedload
from edacc.views.helpers import require_phase, require_login

plot = Module(__name__)


@plot.route('/<database>/experiment/<int:experiment_id>/scatter-plot-1property/<int:s1>/<int:s2>/<run>/')
@require_phase(phases=(5, 6, 7))
@require_login
def scatter_2solver_1property(database, experiment_id, s1, s2, run, instances, result_property):
    """ Plots the cputimes of the two specified solver configurations on the
        experiment's instances against each other in a scatter plot and
        returns the image as HTTP response """
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

    points = []
    if run == 'average':
        for instance in instances:
            s1_avg = numpy.average([j.time if j.status == 1 else exp.timeOut for j in results1.filter_by(instance=instance).all()])
            s2_avg = numpy.average([j.time if j.status == 1 else exp.timeOut for j in results2.filter_by(instance=instance).all()])
            points.append((s1_avg, s2_avg, instance))
    elif run == 'median':
        for instance in instances:
            x = numpy.median([j.time if j.status == 1 else exp.timeOut for j in results1.filter_by(instance=instance).all()])
            y = numpy.median([j.time if j.status == 1 else exp.timeOut for j in results2.filter_by(instance=instance).all()])
            points.append((x, y, instance))
    elif run == 'all':
        for instance in instances:
            xs = [j.time if j.status == 1 else exp.timeOut for j in results1.filter_by(instance=instance).all()]
            ys = [j.time if j.status == 1 else exp.timeOut for j in results2.filter_by(instance=instance).all()]
            points += zip(xs, ys, [instance] * len(xs))
    else:
        for instance in instances:
            r1 = results1.filter_by(instance=instance, run=int(run)).first()
            r2 = results2.filter_by(instance=instance, run=int(run)).first()
            points.append((
                r1.time if r1.status == 1 else exp.timeOut,
                r2.time if r1.status == 1 else exp.timeOut,
                instance
            ))

    title = sc1.solver.name + ' vs. ' + sc2.solver.name
    xlabel = sc1.solver.name + ' CPU time (s)'
    ylabel = sc2.solver.name + ' CPU time (s)'
    if request.args.has_key('pdf'):
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.pdf'
        plots.scatter(points, xlabel, ylabel, title, exp.timeOut, filename, format='pdf')
        headers = Headers()
        headers.add('Content-Disposition', 'attachment', filename=sc1.solver.name + '_vs_' + sc2.solver.name + '.pdf')
        response = Response(response=open(filename, 'rb').read(), mimetype='application/pdf', headers=headers)
        os.remove(filename)
        return response
    else:
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.png'
        pts = plots.scatter(points, xlabel, ylabel, title, exp.timeOut, filename)
        if request.args.has_key('imagemap'):
            mapdata = []
            for i in xrange(len(points)):
                mapdata.append(
                    {'x': pts[0],
                     'y': pts[1],
                     'url': url_for('frontend.instance_details',
                                    database=database,
                                    instance_id=points[i][2].idInstance),
                     'alt': points[i][2].name
                    }
                )
            return json.dumps({
                'data': mapdata
            })
        else:
            response = Response(response=open(filename, 'rb').read(), mimetype='image/png')
        os.remove(filename)
        return response


def scatter_1solver_instance_vs_result_property(database, experiment_id, solver, run, instances, instance_property, result_property):
    pass

def scatter_1solver_result_vs_result_property(database, experiment_id, solver, run, instances, result_property1, result_property2):
    pass

@plot.route('/<database>/experiment/<int:experiment_id>/cactus-plot/')
@require_phase(phases=(5, 6, 7))
@require_login
def cactus_plot(database, experiment_id, instances, result_property):
    """ Renders a cactus plot of the instances solved within a given "amount" of
        a result property of all solver configurations of the specified
        experiment
    """
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    results = db.session.query(db.ExperimentResult)
    results.enable_eagerloads(True).options(joinedload(db.ExperimentResult.solver_configuration))
    results = results.filter_by(experiment=exp)

    solvers = []
    for sc in exp.solver_configurations:
        s = {'xs': [], 'ys': [], 'name': sc.get_name()}
        sc_res = results.filter_by(solver_configuration=sc, status=1).order_by(db.ExperimentResult.time)
        i = 1
        for r in sc_res:
            s['ys'].append(r.time)
            s['xs'].append(i)
            i += 1
        solvers.append(s)

    max_x = max([max(s['xs'] or [0]) for s in solvers]) + 10
    max_y = max([max(s['ys'] or [0]) for s in solvers])

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


@plot.route('/<database>/experiment/<int:experiment_id>/box-plot/')
@require_phase(phases=(6, 7))
@require_login
def box_plot(database, experiment_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    results = {}
    for sc in exp.solver_configurations:
        results[str(sc)] = [res.time for res in db.session.query(db.ExperimentResult)
                                    .filter_by(experiment=exp,
                                               solver_configuration=sc).all()]

    filename = os.path.join(config.TEMP_DIR, g.unique_id) + 'boxplot.png'
    plots.box_plot(results, filename, 'png')
    response = Response(response=open(filename, 'rb').read(), mimetype='image/png')
    os.remove(filename)
    return response

@plot.route('/<database>/experiment/<int:experiment_id>/histogram/<int:solver_configuration_id>/<int:instance_id>/')
@require_phase(phases=(6, 7))
@require_login
def histogram(database, experiment_id, solver_configuration_id, instance_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    sc = db.session.query(db.SolverConfiguration).get(solver_configuration_id) or abort(404)
    instance = db.session.query(db.Instance).filter_by(idInstance=instance_id).first() or abort(404)

    results = [r.time for r in db.session.query(db.ExperimentResult)
                                    .filter_by(experiment=exp,
                                               solver_configuration=sc,
                                               instance=instance).all()]

    filename = os.path.join(config.TEMP_DIR, g.unique_id) + 'hist.png'
    plots.hist(results, filename, 'png')
    response = Response(response=open(filename, 'rb').read(), mimetype='image/png')
    os.remove(filename)
    return response


@plot.route('/<database>/experiment/<int:experiment_id>/ecdf/<int:solver_configuration_id>/<int:instance_id>/')
@require_phase(phases=(6, 7))
@require_login
def ecdf(database, experiment_id, solver_configuration_id, instance_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    sc = db.session.query(db.SolverConfiguration).get(solver_configuration_id) or abort(404)
    instance = db.session.query(db.Instance).filter_by(idInstance=instance_id).first() or abort(404)

    results = [r.time for r in db.session.query(db.ExperimentResult)
                                    .filter_by(experiment=exp,
                                               solver_configuration=sc,
                                               instance=instance).all()]

    filename = os.path.join(config.TEMP_DIR, g.unique_id) + 'ecdf.png'
    plots.ecdf(results, filename, 'png')
    response = Response(response=open(filename, 'rb').read(), mimetype='image/png')
    os.remove(filename)
    return response