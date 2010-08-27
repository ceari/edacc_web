# -*- coding: utf-8 -*-
"""
    edacc.views.analysis
    --------------------

    Defines request handler functions for all analysis related functionality.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

import os
import json

from flask import Module
from flask import render_template, url_for
from flask import Response, abort, request, g
from werkzeug import Headers

from edacc import plots, config, models, forms
from sqlalchemy.orm import joinedload
from edacc.views.helpers import require_phase, require_login

analysis = Module(__name__)


def render(*args, **kwargs):
    from tidylib import tidy_document
    res = render_template(*args, **kwargs)
    doc, errs = tidy_document(res)
    return doc


@analysis.route('/<database>/experiment/<int:experiment_id>/ranking/')
@require_phase(phases=(6, 7))
@require_login
def ranking(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    from scipy import stats
    def pointbiserialcorr(s1, s2):
        alpha = 0.05
        d = 0.0
        num = 0
        for i in experiment.instances:
            res1 = [res.time if res.status == 1 else experiment.timeOut for res in experiment.results if res.solver_configuration == s1 and res.instance == i]
            res2 = [res.time if res.status == 1 else experiment.timeOut for res in experiment.results if res.solver_configuration == s2 and res.instance == i]
            ranked_data = list(stats.stats.rankdata(res1 + res2))

            r, p = stats.pointbiserialr([1] * len(res1) + [0] * len(res2), ranked_data)
            #print str(s1), str(s2), r, p
            if p < alpha:
                d += r
                num += 1

        if num > 0:
            return d / num
        else:
            return 0 # s1 == s2

    def comp(s1, s2):
        r = pointbiserialcorr(s1, s2)
        if r < 0: return 1
        elif r > 0: return -1
        else: return 0

    scs_nbsolved = [{'sc': sc,
                     'solved': sum(1 for res in experiment.results if res.solver_configuration == sc and res.status == 1)}
                        for sc in experiment.solver_configurations]
    scs_nbsolved = reversed(sorted(scs_nbsolved, key=lambda sc: sc['solved']))

    #rmatrix = [[pointbiserialcorr(s1, s2) for s1 in experiment.solver_configurations] for s2 in experiment.solver_configurations]

    scs = reversed(sorted(experiment.solver_configurations, cmp=comp))

    return render('/analysis/ranking.html', database=database, db=db,
                  experiment=experiment, scs=scs, pointbiserialcorr=pointbiserialcorr, scs_nbsolved=scs_nbsolved)

@analysis.route('/<database>/experiment/<int:experiment_id>/evaluation-solved-instances/')
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

    form = forms.CPUTimeComparisonForm(request.args)
    form.solver1.query = experiment.solver_configurations
    form.solver2.query = experiment.solver_configurations
    numRuns = len(experiment.results) / len(experiment.solver_configurations) / len(experiment.instances)
    runs = zip(range(numRuns), ["#" + str(i) for i in range(numRuns)])
    form.run.choices = [('average', 'All runs - average time'), ('median', 'All runs - median time')] + runs

    return render('/analysis/cputime.html', database=database, experiment=experiment, db=db, form=form)


@analysis.route('/<database>/experiment/<int:experiment_id>/cputime-plot/<int:s1>/<int:s2>/<run>/')
@require_phase(phases=(5, 6, 7))
@require_login
def cputime_plot(database, experiment_id, s1, s2, run):
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

    points = []
    if run == 'average':
        for instance in exp.instances:
            s1_jobs = results1.filter_by(instance=instance).all()
            s1_avg = sum(j.time if j.status == 1 else exp.timeOut for j in s1_jobs) / len(s1_jobs)
            s2_jobs = results2.filter_by(instance=instance).all()
            s2_avg = sum(j.time if j.status == 1 else exp.timeOut for j in s2_jobs) / len(s2_jobs)
            points.append({
                'x': s1_avg,
                'y': s2_avg,
                'instance': instance
            })
    elif run == 'median':
        for instance in exp.instances:
            s1_jobs = sorted(results1.filter_by(instance=instance).all(), key=lambda j: j.time)
            s2_jobs = sorted(results2.filter_by(instance=instance).all(), key=lambda j: j.time)
            points.append({
                'x': s1_jobs[len(s1_jobs)/2].time,
                'y': s2_jobs[len(s2_jobs)/2].time,
                'instance': instance
            })
    else:
        for instance in exp.instances:
            r1 = results1.filter_by(instance=instance, run=int(run)).first()
            r2 = results2.filter_by(instance=instance, run=int(run)).first()
            points.append({
                'x': r1.time if r1.status == 1 else exp.timeOut,
                'y': r2.time if r1.status == 1 else exp.timeOut,
                'instance': instance
            })

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
            return json.dumps({
                'data': [{'x': p['x'],
                          'y': p['y'],
                          'url': url_for('frontend.instance_details',
                                         database=database,
                                         instance_id=p['instance'].idInstance),
                          'alt': p['instance'].name
                        } for p in pts]
            })
        else:
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


@analysis.route('/<database>/experiment/<int:experiment_id>/box-plot/')
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