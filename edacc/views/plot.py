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
import numpy
import StringIO
import csv
import random

from sqlalchemy import or_, not_, func
from sqlalchemy.sql import select, and_, functions, expression, alias
from sqlalchemy.orm import joinedload_all
import sqlalchemy.types

from flask import Blueprint, render_template as render
from flask import Response, abort, request, g
from werkzeug import Headers, secure_filename

from edacc import plots, config, models
from edacc.web import cache
from sqlalchemy.orm import joinedload
from edacc.views.helpers import require_phase, require_login
from edacc.constants import ANALYSIS1, ANALYSIS2
from edacc import statistics

random.seed()

plot = Blueprint('plot', __name__, template_folder='static')


def get_request_plot_type():
    if request.args.has_key('pdf'):
        return 'pdf'
    elif request.args.has_key('eps'):
        return 'eps'
    elif request.args.has_key('rscript'):
        return 'rscript'
    elif request.args.has_key('csv'):
        return 'csv'
    else:
        return 'png'


def make_plot_response(function, *args, **kwargs):
    if request.args.has_key('pdf'):
        type = 'pdf'; mime = 'application/pdf'
    elif request.args.has_key('eps'):
        type = 'eps'; mime = 'application/eps'
    elif request.args.has_key('rscript'):
        type = 'rscript'; mime = 'text/plain'
    else:
        type = 'png'; mime = 'image/png'
    filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.' + type

    try:
        function(*args, filename=filename, format=type, **kwargs)
    except Exception as exception:
        plots.make_error_plot(text=str(exception), filename=filename, format='png')
        print str(exception)
    headers = Headers()
    headers.add('Content-Disposition', 'attachment', filename=secure_filename('data.' + type))
    response = Response(response=open(filename, 'rb').read(), mimetype=mime, headers=headers)
    os.remove(filename)
    return response


def filter_results(l1, l2):
    """Filter the lists l1 and l2 pairwise for None elements in either
    pair component. Only elements i with l1[i] == l2[i] != None remain.
    """
    r1 = [l1[i] for i in xrange(min(len(l1), len(l2))) if l1[i] is not None and l2[i] is not None]
    r2 = [l2[i] for i in xrange(min(len(l1), len(l2))) if l2[i] is not None and l1[i] is not None]
    return r1, r2


def scatter_2solver_1property_points(db, exp, sc1, sc2, instances, result_property, run):
    instance_ids = [i.idInstance for i in instances]

    results1 = db.session.query(db.ExperimentResult)
    results1 = results1.enable_eagerloads(True).options(joinedload(db.ExperimentResult.solver_configuration))
    results1 = results1.options(joinedload(db.ExperimentResult.properties), joinedload(db.ExperimentResult.instance))
    results1 = results1.filter_by(experiment=exp, solver_configuration=sc1).order_by(db.ExperimentResult.run) \
        .filter(db.ExperimentResult.Instances_idInstance.in_(instance_ids)).all()

    results2 = db.session.query(db.ExperimentResult)
    results2 = results2.enable_eagerloads(True).options(joinedload(db.ExperimentResult.solver_configuration))
    results2 = results2.options(joinedload(db.ExperimentResult.properties), joinedload(db.ExperimentResult.instance))
    results2 = results2.filter_by(experiment=exp, solver_configuration=sc2).order_by(db.ExperimentResult.run) \
        .filter(db.ExperimentResult.Instances_idInstance.in_(instance_ids)).all()

    jobs_by_instance_id1 = dict((i.idInstance, list()) for i in instances)
    jobs_by_instance_id2 = dict((i.idInstance, list()) for i in instances)
    for res in results1:
        jobs_by_instance_id1[res.Instances_idInstance].append(res)
    for res in results2:
        jobs_by_instance_id2[res.Instances_idInstance].append(res)

    points = []
    if run == 'average':
        for instance in instances:
            r1 = [j.get_property_value(result_property, db) for j in jobs_by_instance_id1[instance.idInstance]]
            r2 = [j.get_property_value(result_property, db) for j in jobs_by_instance_id2[instance.idInstance]]
            r1, r2 = filter_results(r1, r2)
            if len(r1) > 0 and len(r2) > 0:
                s1_avg = numpy.average(r1)
                s2_avg = numpy.average(r2)
                points.append((s1_avg, s2_avg, instance))
    elif run == 'median':
        for instance in instances:
            r1 = [j.get_property_value(result_property, db) for j in jobs_by_instance_id1[instance.idInstance]]
            r2 = [j.get_property_value(result_property, db) for j in jobs_by_instance_id2[instance.idInstance]]
            r1, r2 = filter_results(r1, r2)
            if len(r1) > 0 and len(r2) > 0:
                x = numpy.median(r1)
                y = numpy.median(r2)
                points.append((x, y, instance))
    elif run == 'all':
        for instance in instances:
            xs = [j.get_property_value(result_property, db) for j in jobs_by_instance_id1[instance.idInstance]]
            ys = [j.get_property_value(result_property, db) for j in jobs_by_instance_id2[instance.idInstance]]
            xs, ys = filter_results(xs, ys)
            if len(xs) > 0 and len(ys) > 0:
                points += zip(xs, ys, [instance] * len(xs))
    else:
        for instance in instances:
            r1 = ([j for j in jobs_by_instance_id1[instance.idInstance] if j.run == int(run)] or [None])[0]
            r2 = ([j for j in jobs_by_instance_id2[instance.idInstance] if j.run == int(run)] or [None])[0]
            if r1 is None or r2 is None: continue
            if r1.get_property_value(result_property, db) is not None and r2.get_property_value(result_property,
                                                                                                db) is not None:
                points.append((
                    r1.get_property_value(result_property, db),
                    r2.get_property_value(result_property, db),
                    instance
                ))

    return points


@plot.route('/<database>/experiment/<int:experiment_id>/scatter-plot-1property/')
@require_phase(phases=ANALYSIS2)
@require_login
def scatter_2solver_1property(database, experiment_id):
    """Returns an image with a scatter plot of the result property of two
    solver configurations' results on instances as HTTP response.

    The data to be plotted has to be specified as GET parameters:

    solver_config1: id of the first solver configuration
    solver_config2: id of the second solver configuratio
    instances: id of an instance, multiple occurences allowed.
    run: 'average', 'median', 'all', or an integer of the run.
            If the value is 'all', all runs of the solvers will be plotted.
            If the value is 'average' or 'median', these values will be calculated
            across multiple runs of one solver on an instance.
            If the value is an integer, the data of this specific run is used.
    result_property: id of a result property (Property table) or the special case
                     'cputime' for the time column of the ExperimentResult table.
    """
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    s1 = int(request.args['solver_config1'])
    s2 = int(request.args['solver_config2'])

    instances = [
        db.session.query(db.Instance).filter(db.Instance.idInstance.in_(map(int, request.args.getlist('i')))).all()]
    instance_groups_count = int(request.args.get('instance_groups_count', 1))
    for i in xrange(1, instance_groups_count):
        instances.append(db.session.query(db.Instance).filter(
            db.Instance.idInstance.in_(map(int, request.args.getlist('i' + str(i))))).all())

    run = request.args['run']
    xscale = request.args['xscale']
    yscale = request.args['yscale']
    result_property = request.args['result_property']
    if result_property not in ('resultTime', 'wallTime', 'cost'):
        solver_prop = db.session.query(db.Property).get(int(result_property))

    sc1 = db.session.query(db.SolverConfiguration).get(s1) or abort(404)
    sc2 = db.session.query(db.SolverConfiguration).get(s2) or abort(404)

    points = []
    for instance_group in instances:
        points.append(scatter_2solver_1property_points(db, exp, sc1, sc2, instance_group, result_property, run))

    max_x = max([max([p[0] for p in ig] or [0]) for ig in points] or [0])
    max_y = max([max([p[1] for p in ig] or [0]) for ig in points] or [0])
    max_x = max_y = max(max_x, max_y) * 1.1

    title = sc1.get_name() + ' vs. ' + sc2.get_name()
    if result_property == 'resultTime':
        xlabel = sc1.get_name() + ' CPU Time'
        ylabel = sc2.get_name() + ' CPU Time'
    elif result_property == 'wallTime':
        xlabel = sc1.get_name() + ' Wall Clock Time'
        ylabel = sc2.get_name() + ' Wall Clock Time'
    elif result_property == 'cost':
        xlabel = sc1.get_name() + ' Cost'
        ylabel = sc2.get_name() + ' Cost'
    else:
        xlabel = sc1.get_name() + ' ' + solver_prop.name
        ylabel = sc2.get_name() + ' ' + solver_prop.name

    if request.args.has_key('csv'):
        csv_response = StringIO.StringIO()
        csv_writer = csv.writer(csv_response)
        csv_writer.writerow(['Instance', xlabel, ylabel])
        for ig in points:
            for x, y, i in ig:
                csv_writer.writerow([str(i), x, y])
        csv_response.seek(0)

        headers = Headers()
        headers.add('Content-Type', 'text/csv')
        headers.add('Content-Disposition', 'attachment', filename=secure_filename(
            exp.name + "_scatter_" + sc1.get_name() + '_vs_' + sc2.get_name() + ".csv"))
        return Response(response=csv_response.read(), headers=headers)
    elif request.args.has_key('pdf'):
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.pdf'
        plots.scatter(points, xlabel, ylabel, title, max_x, max_y, filename, format='pdf', xscale=xscale, yscale=yscale,
                      diagonal_line=True)
        headers = Headers()
        headers.add('Content-Disposition', 'attachment',
                    filename=secure_filename(sc1.get_name() + '_vs_' + sc2.get_name() + '.pdf'))
        response = Response(response=open(filename, 'rb').read(), mimetype='application/pdf', headers=headers)
        os.remove(filename)
        return response
    elif request.args.has_key('eps'):
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.eps'
        plots.scatter(points, xlabel, ylabel, title, max_x, max_y, filename, format='eps', xscale=xscale, yscale=yscale,
                      diagonal_line=True)
        headers = Headers()
        headers.add('Content-Disposition', 'attachment',
                    filename=secure_filename(sc1.get_name() + '_vs_' + sc2.get_name() + '.eps'))
        response = Response(response=open(filename, 'rb').read(), mimetype='application/eps', headers=headers)
        os.remove(filename)
        return response
    elif request.args.has_key('rscript'):
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.txt'
        plots.scatter(points, xlabel, ylabel, title, max_x, max_y, filename, format='rscript', xscale=xscale,
                      yscale=yscale, diagonal_line=True)
        headers = Headers()
        headers.add('Content-Disposition', 'attachment',
                    filename=secure_filename(sc1.get_name() + '_vs_' + sc2.get_name() + '.txt'))
        response = Response(response=open(filename, 'rb').read(), mimetype='text/plain', headers=headers)
        os.remove(filename)
        return response
    else:
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.png'
        pts = plots.scatter(points, xlabel, ylabel, title, max_x, max_y, filename, xscale=xscale, yscale=yscale,
                            diagonal_line=True)
        pts2 = []
        for j in xrange(len(points)):
            pts2 += [(pts[j][i][0], pts[j][i][1], points[j][i][0], points[j][i][1], points[j][i][2]) for i in
                     xrange(len(points[j]))]
        if request.args.has_key('imagemap'):
            return render('/analysis/imagemap_2solver_1property.html', database=database, experiment=exp, points=pts2,
                          sc1=sc1, sc2=sc2)
        else:
            response = Response(response=open(filename, 'rb').read(), mimetype='image/png')
        os.remove(filename)
        return response


def scatter_1solver_instance_vs_result_property_points(db, exp, solver_config, instances, instance_property,
                                                       result_property, run):
    instance_ids = [i.idInstance for i in instances]
    results = db.session.query(db.ExperimentResult)
    results = results.enable_eagerloads(True).options(joinedload(db.ExperimentResult.solver_configuration)).options(
        joinedload(db.ExperimentResult.instance))
    results = results.filter_by(experiment=exp, solver_configuration=solver_config) \
        .filter(db.ExperimentResult.Instances_idInstance.in_(instance_ids)).all()

    jobs_by_instance_id = dict((i, list()) for i in instance_ids)
    for res in results:
        jobs_by_instance_id[res.Instances_idInstance].append(res)

    points = []
    if run == 'average':
        for instance in instances:
            prop_value = instance.get_property_value(instance_property, db)
            res = [j.get_property_value(result_property, db) for j in jobs_by_instance_id[instance.idInstance]]
            res = filter(lambda r: r is not None, res)
            if res != [] and prop_value is not None:
                s_avg = numpy.average(res)
                points.append((prop_value, s_avg, instance))
    elif run == 'median':
        for instance in instances:
            prop_value = instance.get_property_value(instance_property, db)
            res = [j.get_property_value(result_property, db) for j in jobs_by_instance_id[instance.idInstance]]
            res = filter(lambda r: r is not None, res)
            if res != [] and prop_value is not None:
                y = numpy.median(res)
                points.append((prop_value, y, instance))
    elif run == 'all':
        for instance in instances:
            prop_value = instance.get_property_value(instance_property, db)
            if prop_value is not None:
                xs = [prop_value] * len(results.filter_by(instance=instance).all())
                ys = [j.get_property_value(result_property, db) for j in jobs_by_instance_id[instance.idInstance]]
                ys = filter(lambda r: r is not None, ys)
                points += zip(xs, ys, [instance] * len(xs))
    else:
        for instance in instances:
            res = ([j for j in jobs_by_instance_id[instance.idInstance] if j.run == int(run)] or [None])[0]
            if res is None: continue
            if instance.get_property_value(instance_property, db) is not None and res.get_property_value(
                    result_property, db) is not None:
                points.append((
                    instance.get_property_value(instance_property, db),
                    res.get_property_value(result_property, db),
                    instance
                ))

    return points


@plot.route('/<database>/experiment/<int:experiment_id>/scatter-plot-instance-vs-result/')
@require_phase(phases=ANALYSIS2)
@require_login
def scatter_1solver_instance_vs_result_property(database, experiment_id):
    """ Returns an image with the result property values of one solver
    against the instance property values, e.g. CPU time vs memory used.
    """
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    solver_config = int(request.args['solver_config'])
    run = request.args['run']
    xscale = request.args['xscale']
    yscale = request.args['yscale']
    result_property = request.args['result_property']
    instance_property = request.args['instance_property']

    instances = [
        db.session.query(db.Instance).filter(db.Instance.idInstance.in_(map(int, request.args.getlist('i')))).all()]
    instance_groups_count = int(request.args.get('instance_groups_count', 1))
    for i in xrange(1, instance_groups_count):
        instances.append(db.session.query(db.Instance).filter(
            db.Instance.idInstance.in_(map(int, request.args.getlist('i' + str(i))))).all())

    if result_property not in ('resultTime', 'wallTime', 'cost'):
        solver_prop = db.session.query(db.Property).get(int(result_property))

    instance_prop = db.session.query(db.Property).get(int(instance_property))

    solver_config = db.session.query(db.SolverConfiguration).get(solver_config) or abort(404)

    points = []
    for instance_group in instances:
        points.append(scatter_1solver_instance_vs_result_property_points(db, exp, solver_config, instance_group,
                                                                         int(instance_property), result_property, run))

    xlabel = instance_prop.name

    if result_property == 'resultTime':
        ylabel = 'CPU Time'
    elif result_property == 'wallTime':
        ylabel = 'Wall Clock Time'
    elif result_property == 'cost':
        ylabel = 'Cost'
    else:
        ylabel = solver_prop.name

    title = str(solver_config)

    max_x = max([max([p[0] for p in ig] or [0]) for ig in points] or [0]) * 1.1
    max_y = max([max([p[1] for p in ig] or [0]) for ig in points] or [0]) * 1.1

    if request.args.has_key('csv'):
        csv_response = StringIO.StringIO()
        csv_writer = csv.writer(csv_response)
        csv_writer.writerow(['Instance', xlabel, ylabel])
        for x, y, i in points:
            csv_writer.writerow([str(i), x, y])
        csv_response.seek(0)

        headers = Headers()
        headers.add('Content-Type', 'text/csv')
        headers.add('Content-Disposition', 'attachment', filename=secure_filename(
            exp.name + "_scatter_" + str(solver_config) + "_" + ylabel + "_vs_" + xlabel + ".csv"))
        return Response(response=csv_response.read(), headers=headers)
    elif request.args.has_key('pdf'):
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.pdf'
        plots.scatter(points, xlabel, ylabel, title, max_x, max_y, filename, format='pdf', xscale=xscale, yscale=yscale)
        headers = Headers()
        headers.add('Content-Disposition', 'attachment', filename=secure_filename(
            exp.name + "_scatter_" + str(solver_config) + "_" + ylabel + "_vs_" + xlabel + '.pdf'))
        response = Response(response=open(filename, 'rb').read(), mimetype='application/pdf', headers=headers)
        os.remove(filename)
        return response
    elif request.args.has_key('eps'):
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.eps'
        plots.scatter(points, xlabel, ylabel, title, max_x, max_y, filename, format='eps', xscale=xscale, yscale=yscale)
        headers = Headers()
        headers.add('Content-Disposition', 'attachment', filename=secure_filename(
            exp.name + "_scatter_" + str(solver_config) + "_" + ylabel + "_vs_" + xlabel + '.eps'))
        response = Response(response=open(filename, 'rb').read(), mimetype='application/eps', headers=headers)
        os.remove(filename)
        return response
    elif request.args.has_key('rscript'):
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.txt'
        plots.scatter(points, xlabel, ylabel, title, max_x, max_y, filename, format='rscript', xscale=xscale,
                      yscale=yscale, diagonal_line=True)
        headers = Headers()
        headers.add('Content-Disposition', 'attachment', filename=secure_filename(
            exp.name + "_scatter_" + str(solver_config) + "_" + ylabel + "_vs_" + xlabel + '.txt'))
        response = Response(response=open(filename, 'rb').read(), mimetype='text/plain', headers=headers)
        os.remove(filename)
        return response
    else:
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.png'
        pts = plots.scatter(points, xlabel, ylabel, title, max_x, max_y, filename, xscale=xscale, yscale=yscale)
        pts2 = []
        for j in xrange(len(points)):
            pts2 += [(pts[j][i][0], pts[j][i][1], points[j][i][0], points[j][i][1], points[j][i][2]) for i in
                     xrange(len(points[j]))]
        if request.args.has_key('imagemap'):
            return render('/analysis/imagemap_instance_vs_result.html', database=database, experiment=exp, points=pts2,
                          sc=solver_config)
        else:
            response = Response(response=open(filename, 'rb').read(), mimetype='image/png')
        os.remove(filename)
        return response


def scatter_1solver_result_vs_result_property_plot(db, exp, solver_config, instances, result_property1,
                                                   result_property2, run):
    instance_ids = [i.idInstance for i in instances]
    results = db.session.query(db.ExperimentResult)
    results = results.enable_eagerloads(True).options(joinedload(db.ExperimentResult.solver_configuration)).options(
        joinedload(db.ExperimentResult.instance))
    results = results.filter_by(experiment=exp, solver_configuration=solver_config).order_by(db.ExperimentResult.run) \
        .filter(db.ExperimentResult.Instances_idInstance.in_(instance_ids)).all()

    jobs_by_instance_id = dict((i, list()) for i in instance_ids)
    for res in results:
        jobs_by_instance_id[res.Instances_idInstance].append(res)

    points = []
    if run == 'average':
        for instance in instances:
            r1 = [j.get_property_value(result_property1, db) for j in jobs_by_instance_id[instance.idInstance]]
            r2 = [j.get_property_value(result_property2, db) for j in jobs_by_instance_id[instance.idInstance]]
            r1, r2 = filter_results(r1, r2)
            if len(r1) > 0 and len(r2) > 0:
                s1_avg = numpy.average(r1)
                s2_avg = numpy.average(r2)
                points.append((s1_avg, s2_avg, instance))
    elif run == 'median':
        for instance in instances:
            r1 = [j.get_property_value(result_property1, db) for j in jobs_by_instance_id[instance.idInstance]]
            r2 = [j.get_property_value(result_property2, db) for j in jobs_by_instance_id[instance.idInstance]]
            r1, r2 = filter_results(r1, r2)
            if len(r1) > 0 and len(r2) > 0:
                x = numpy.median(r1)
                y = numpy.median(r2)
                points.append((x, y, instance))
    elif run == 'all':
        for instance in instances:
            xs = [j.get_property_value(result_property1, db) for j in jobs_by_instance_id[instance.idInstance]]
            ys = [j.get_property_value(result_property2, db) for j in jobs_by_instance_id[instance.idInstance]]
            xs, ys = filter_results(xs, ys)
            if len(xs) > 0 and len(ys) > 0:
                points += zip(xs, ys, [instance] * len(xs))
    else:
        for instance in instances:
            res = ([j for j in jobs_by_instance_id[instance.idInstance] if j.run == int(run)] or [None])[0]
            if res is None: continue
            if res.get_property_value(result_property1, db) is not None and res.get_property_value(result_property2,
                                                                                                   db) is not None:
                points.append((
                    res.get_property_value(result_property1, db),
                    res.get_property_value(result_property2, db),
                    instance
                ))

    return points


@plot.route('/<database>/experiment/<int:experiment_id>/scatter-plot-2properties/')
@require_phase(phases=ANALYSIS2)
@require_login
def scatter_1solver_result_vs_result_property(database, experiment_id):
    """ Returns an image with the result property values against
    other result property values.
    """
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    solver_config = int(request.args['solver_config'])
    run = request.args['run']
    xscale = request.args['xscale']
    yscale = request.args['yscale']
    result_property1 = request.args['result_property1']
    result_property2 = request.args['result_property2']

    instances = [
        db.session.query(db.Instance).filter(db.Instance.idInstance.in_(map(int, request.args.getlist('i')))).all()]
    instance_groups_count = int(request.args.get('instance_groups_count', 1))
    for i in xrange(1, instance_groups_count):
        instances.append(db.session.query(db.Instance).filter(
            db.Instance.idInstance.in_(map(int, request.args.getlist('i' + str(i))))).all())

    if result_property1 not in ('resultTime', 'wallTime', 'cost'):
        solver_prop1 = db.session.query(db.Property).get(int(result_property1))

    if result_property2 not in ('resultTime', 'wallTime', 'cost'):
        solver_prop2 = db.session.query(db.Property).get(int(result_property2))

    solver_config = db.session.query(db.SolverConfiguration).get(solver_config) or abort(404)

    points = []
    for instance_group in instances:
        points.append(
            scatter_1solver_result_vs_result_property_plot(db, exp, solver_config, instance_group, result_property1,
                                                           result_property2, run))

    if result_property1 == 'resultTime':
        xlabel = 'CPU Time'
    elif result_property1 == 'wallTime':
        xlabel = 'Wall Clock Time'
    elif result_property1 == 'cost':
        xlabel = 'Cost Time'
    else:
        xlabel = solver_prop1.name

    if result_property2 == 'resultTime':
        ylabel = 'CPU Time'
    elif result_property2 == 'wallTime':
        ylabel = 'Wall Clock Time'
    elif result_property2 == 'cost':
        ylabel = 'Cost'
    else:
        ylabel = solver_prop2.name

    title = str(solver_config)

    max_x = max([max([p[0] for p in ig] or [0]) for ig in points] or [0]) * 1.1
    max_y = max([max([p[1] for p in ig] or [0]) for ig in points] or [0]) * 1.1

    if request.args.has_key('csv'):
        csv_response = StringIO.StringIO()
        csv_writer = csv.writer(csv_response)
        csv_writer.writerow(['Instance', xlabel, ylabel])
        for x, y, i in points:
            csv_writer.writerow([str(i), x, y])
        csv_response.seek(0)

        headers = Headers()
        headers.add('Content-Type', 'text/csv')
        headers.add('Content-Disposition', 'attachment', filename=secure_filename(
            exp.name + "_scatter_" + str(solver_config) + "_" + ylabel + "_vs_" + xlabel + '.csv'))
        return Response(response=csv_response.read(), headers=headers)
    elif request.args.has_key('pdf'):
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.pdf'
        plots.scatter(points, xlabel, ylabel, title, max_x, max_y, filename, format='pdf', xscale=xscale, yscale=yscale)
        headers = Headers()
        headers.add('Content-Disposition', 'attachment', filename=secure_filename(
            exp.name + "_scatter_" + str(solver_config) + "_" + ylabel + "_vs_" + xlabel + '.pdf'))
        response = Response(response=open(filename, 'rb').read(), mimetype='application/pdf', headers=headers)
        os.remove(filename)
        return response
    elif request.args.has_key('eps'):
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.eps'
        plots.scatter(points, xlabel, ylabel, title, max_x, max_y, filename, format='eps', xscale=xscale, yscale=yscale)
        headers = Headers()
        headers.add('Content-Disposition', 'attachment', filename=secure_filename(
            exp.name + "_scatter_" + str(solver_config) + "_" + ylabel + "_vs_" + xlabel + '.eps'))
        response = Response(response=open(filename, 'rb').read(), mimetype='application/eps', headers=headers)
        os.remove(filename)
        return response
    elif request.args.has_key('rscript'):
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.txt'
        plots.scatter(points, xlabel, ylabel, title, max_x, max_y, filename, format='rscript', xscale=xscale,
                      yscale=yscale, diagonal_line=True)
        headers = Headers()
        headers.add('Content-Disposition', 'attachment', filename=secure_filename(
            exp.name + "_scatter_" + str(solver_config) + "_" + ylabel + "_vs_" + xlabel + '.txt'))
        response = Response(response=open(filename, 'rb').read(), mimetype='text/plain', headers=headers)
        os.remove(filename)
        return response
    else:
        filename = os.path.join(config.TEMP_DIR, g.unique_id) + '.png'
        pts = plots.scatter(points, xlabel, ylabel, title, max_x, max_y, filename, xscale=xscale, yscale=yscale)
        pts2 = []
        for j in xrange(len(points)):
            pts2 += [(pts[j][i][0], pts[j][i][1], points[j][i][0], points[j][i][1], points[j][i][2]) for i in
                     xrange(len(points[j]))]
        if request.args.has_key('imagemap'):
            return render('/analysis/imagemap_result_vs_result.html', database=database, experiment=exp, points=pts2,
                          sc=solver_config)
        else:
            response = Response(response=open(filename, 'rb').read(), mimetype='image/png')
        os.remove(filename)
        return response


@plot.route('/<database>/experiment/<int:experiment_id>/cactus-plot/')
@require_phase(phases=ANALYSIS1)
@require_login
def cactus_plot(database, experiment_id):
    """ Renders a cactus plot of the instances solved within a given "amount" of
        a result property of all solver configurations of the specified
        experiment
    """
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    last_modified_job = db.session.query(func.max(db.ExperimentResult.date_modified)) \
        .filter_by(experiment=exp).first()
    job_count = db.session.query(db.ExperimentResult).filter_by(experiment=exp).count()

    @cache.memoize(6 * 24 * 60 * 60)
    def cached_cactus_plot(database, experiment_id, request_args, job_count, last_modified_job, plot_type):
        instance_groups_count = int(request.args.get('instance_groups_count', 0))
        use_colors_for = request.args.get('use_colors_for', 'solvers')
        colored_instance_groups = (use_colors_for == 'instance_groups')
        log_property = request.args.has_key('log_property')
        flip_axes = request.args.has_key('flip_axes')
        run = request.args.get('run', 'all')
        result_property = request.args.get('result_property') or 'resultTime'

        results = db.session.query(db.ExperimentResult)
        results = results.enable_eagerloads(True).options(joinedload(db.ExperimentResult.solver_configuration))
        results = results.options(joinedload(db.ExperimentResult.properties))
        results = results.filter_by(experiment=exp)
        instances = [[int(id) for id in request.args.getlist('i')]]
        for i in xrange(1, instance_groups_count):
            instances.append([int(id) for id in request.args.getlist('i' + str(i))])

        if result_property not in ('resultTime', 'wallTime', 'cost'):
            solver_prop = db.session.query(db.Property).get(int(result_property))

        solver_configs = [db.session.query(db.SolverConfiguration).get(int(id)) for id in request.args.getlist('sc')]

        solvers = []
        num_solved = dict()

        random_run = random.randint(0, exp.get_max_num_runs(db) - 1)

        for instance_group in xrange(instance_groups_count):
            for sc in solver_configs:
                s = {'xs': [], 'ys': [], 'name': sc.get_name(), 'instance_group': instance_group, 'solver_config': sc}
                sc_res = results.filter_by(solver_configuration=sc, status=1).filter(
                    db.ExperimentResult.resultCode.like('1%')) \
                    .filter(db.ExperimentResult.Instances_idInstance.in_(instances[instance_group]))
                num_solved[sc] = sc_res.count()
                if run == 'all':
                    sc_results = filter(lambda j: j is not None,
                                        [r.get_property_value(result_property, db) for r in sc_res.all()])
                elif run in ('average', 'median'):
                    sc_results = []
                    for id in instances[instance_group]:
                        res = sc_res.filter(db.ExperimentResult.Instances_idInstance == id).all()
                        res = [r.get_property_value(result_property, db) for r in res]
                        res = filter(lambda r: r is not None, res)
                        if len(res) > 0:
                            if run == 'average':
                                sc_results.append(numpy.average(res))
                            elif run == 'median':
                                sc_results.append(numpy.median(res or [0]))
                elif run == 'random':
                    sc_results = [r.get_property_value(result_property, db) for r in
                                  sc_res.filter_by(run=random_run).all()]
                    sc_results = filter(lambda r: r is not None, sc_results)
                elif run == 'penalized_average':
                    sc_results = []
                    for id in instances[instance_group]:
                        res = sc_res.filter(db.ExperimentResult.Instances_idInstance == id).all()
                        num_penalized = results.filter_by(solver_configuration=sc) \
                            .filter(db.ExperimentResult.Instances_idInstance == id) \
                            .filter(or_(db.ExperimentResult.status != 1,
                                        not_(db.ExperimentResult.resultCode.like('1%')))).count()
                        if result_property == 'resultTime':
                            penalized_time = sum(
                                [j.get_penalized_time(10) for j in res if not str(j.resultCode).startswith('1')])
                            res_vals = [r.get_property_value(result_property, db) for r in res if
                                        str(r.resultCode.startswith('1'))]
                        elif result_property == 'wallTime':
                            penalized_time = sum(
                                [j.wallClockTimeLimit * 10 for j in res if not str(j.resultCode).startswith('1')])
                            res_vals = [r.get_property_value(result_property, db) for r in res if
                                        str(r.resultCode.startswith('1'))]
                        else:
                            penalized_time = 0
                            res_vals = [r.get_property_value(result_property, db) for r in res]
                        penalized_avg = (sum(res_vals) + penalized_time) / (num_penalized + len(res_vals))
                        sc_results.append(penalized_avg)
                else:
                    run_number = int(run)
                    res = sc_res.filter_by(run=run_number).all()
                    res = [r.get_property_value(result_property, db) for r in res]
                    sc_results = filter(lambda r: r is not None, res)

                sc_results = sorted(sc_results)
                if not log_property:
                    s['ys'].append(0)
                    s['xs'].append(0)

                # sc_results = (y_1, y_2, ..., y_n) : y_1 <= y_2 <= ... <= y_n
                # s = {(x, y) \in R² : y = sc_results[x], x = 1, ..., n }
                i = 1
                for r in sc_results:
                    s['ys'].append(r)
                    s['xs'].append(i)
                    i += 1
                solvers.append(s)

        solvers.sort(key=lambda x: num_solved[x['solver_config']], reverse=True)

        min_y = min([min(s['ys'] or [0.01]) for s in solvers] or [0.01])
        max_x = max([max(s['xs'] or [0]) for s in solvers] or [0]) + 10
        max_y = max([max(s['ys'] or [0]) for s in solvers] or [0]) * 1.1

        if result_property == 'resultTime':
            ylabel = 'CPU Time (s)'
            title = 'Number of solved instances within a given amount of CPU time'
        elif result_property == 'wallTime':
            ylabel = 'Wall Clock Time (s)'
            title = 'Number of solved instances within a given amount of wall clock time'
        elif result_property == 'cost':
            ylabel = 'Cost'
            title = 'Number of solved instances within a given amount of cost value'
        else:
            ylabel = solver_prop.name
            title = 'Number of solved instances within a given amount of ' + solver_prop.name

        if plot_type == 'csv':
            csv_response = StringIO.StringIO()
            csv_writer = csv.writer(csv_response)
            for s in solvers:
                csv_writer.writerow(['%s (G%d)' % (s['name'], s['instance_group'])])
                csv_writer.writerow(['number of solved instances'] + map(str, s['xs']))
                csv_writer.writerow(['Cost'] + map(str, s['ys']))
            csv_response.seek(0)

            headers = Headers()
            headers.add('Content-Type', 'text/csv')
            headers.add('Content-Disposition', 'attachment', filename=secure_filename(exp.name + "_cactus.csv"))
            return Response(response=csv_response.read(), headers=headers)
        else:
            return make_plot_response(plots.cactus, solvers, instance_groups_count, colored_instance_groups,
                                      max_x, max_y, min_y, log_property, flip_axes, ylabel, title)

    return cached_cactus_plot(database, experiment_id, request.args, job_count, last_modified_job,
                              get_request_plot_type())


@plot.route('/<database>/experiment/<int:experiment_id>/rp-comparison-plot/')
@require_phase(phases=ANALYSIS2)
@require_login
def result_property_comparison_plot(database, experiment_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    instance_ids = [int(id) for id in request.args.getlist('i')] or abort(404)
    s1 = db.session.query(db.SolverConfiguration).get(int(request.args['solver_config1'])) or abort(404)
    s2 = db.session.query(db.SolverConfiguration).get(int(request.args['solver_config2'])) or abort(404)
    dim = int(request.args.get('dim', 700))

    log_property = request.args.has_key('log_property')
    result_property = request.args.get('result_property')
    if result_property == 'resultTime':
        result_property_name = 'CPU time (s)'
    elif result_property == 'wallTime':
        result_property_name = 'Wall Clock time (s)'
    elif result_property == 'cost':
        result_property_name = 'Cost'
    else:
        result_property = db.session.query(db.Property).get(int(result_property)).idProperty
        result_property_name = db.session.query(db.Property).get(int(result_property)).name

    results1 = [r.get_property_value(result_property, db) for r in db.session.query(db.ExperimentResult)
    .filter_by(experiment=exp,
               solver_configuration=s1)
    .filter(db.ExperimentResult.Instances_idInstance.in_(instance_ids))
    .order_by(db.ExperimentResult.Instances_idInstance, db.ExperimentResult.run).all()]

    results2 = [r.get_property_value(result_property, db) for r in db.session.query(db.ExperimentResult)
    .filter_by(experiment=exp,
               solver_configuration=s2)
    .filter(db.ExperimentResult.Instances_idInstance.in_(instance_ids))
    .order_by(db.ExperimentResult.Instances_idInstance, db.ExperimentResult.run).all()]

    results1 = filter(lambda r: r is not None, results1)
    results2 = filter(lambda r: r is not None, results2)

    if request.args.has_key('csv'):
        csv_response = StringIO.StringIO()
        csv_writer = csv.writer(csv_response)
        csv_writer.writerow([result_property_name + ' results of the two solver configurations'])
        csv_writer.writerow([str(s1), str(s2)])
        for i in xrange(min(len(results1), len(results2))):
            csv_writer.writerow(map(str, [results1[i], results2[i]]))
        csv_response.seek(0)

        headers = Headers()
        headers.add('Content-Type', 'text/csv')
        headers.add('Content-Disposition', 'attachment',
                    filename=secure_filename(exp.name + "_" + str(s1) + "_" + str(s2) + "result_comparison.csv"))
        return Response(response=csv_response.read(), headers=headers)
    else:
        return make_plot_response(plots.result_property_comparison, results1, results2, str(s1), str(s2),
                                  result_property_name, log_property, dim)


@plot.route('/<database>/experiment/<int:experiment_id>/rps-plot/')
@require_phase(phases=ANALYSIS2)
@require_login
def property_distributions_plot(database, experiment_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    instance = db.session.query(db.Instance).filter_by(idInstance=int(request.args['instance'])).first() or abort(404)
    solver_configs = [db.session.query(db.SolverConfiguration).get(int(id)) for id in request.args.getlist('sc')]

    log_property = request.args.has_key('log_property')
    result_property = request.args.get('result_property')
    if result_property == 'resultTime':
        result_property_name = 'CPU time (s)'
    elif result_property == 'wallTime':
        result_property_name = 'Wall Clock time (s)'
    elif result_property == 'cost':
        result_property_name = 'Cost'
    else:
        result_property = db.session.query(db.Property).get(int(result_property)).idProperty
        result_property_name = db.session.query(db.Property).get(int(result_property)).name

    results = []
    for sc in solver_configs:
        sc_results = db.session.query(db.ExperimentResult) \
            .options(joinedload_all('properties')) \
            .filter_by(experiment=exp, instance=instance,
                       solver_configuration=sc).all()
        results.append(
            (sc, filter(lambda i: i is not None, [j.get_property_value(result_property, db) for j in sc_results])))

    if request.args.has_key('csv'):
        csv_response = StringIO.StringIO()
        csv_writer = csv.writer(csv_response)
        csv_writer.writerow([result_property_name + ' values of the listed solver configurations on ' + str(instance)])
        for res in results:
            csv_writer.writerow([str(res[0])] + map(str, res[1]))
        csv_response.seek(0)

        headers = Headers()
        headers.add('Content-Type', 'text/csv')
        headers.add('Content-Disposition', 'attachment', filename=secure_filename(exp.name + "_rtds.csv"))
        return Response(response=csv_response.read(), headers=headers)
    else:
        return make_plot_response(plots.property_distributions, results, result_property_name, log_property)


@plot.route('/<database>/experiment/<int:experiment_id>/rp-plot/')
@require_phase(phases=ANALYSIS2)
@require_login
def property_distribution(database, experiment_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    #sc = db.session.query(db.SolverConfiguration).get(int(request.args['solver_config'])) or abort(404)
    solver_configs = db.session.query(db.SolverConfiguration).filter(
        db.SolverConfiguration.idSolverConfig.in_(int(id) for id in request.args.getlist('sc'))).all()
    solver_config_ids = [sc.idSolverConfig for sc in solver_configs]
    instances = db.session.query(db.Instance).filter(
        db.Instance.idInstance.in_(int(id) for id in request.args.getlist('i'))).all()
    instance_ids = [i.idInstance for i in instances]
    #instance = db.session.query(db.Instance).filter_by(idInstance=int(request.args['instance'])).first() or abort(404)

    log_property = request.args.has_key('log_property')
    restart_strategy = request.args.has_key('restart_strategy')
    result_property = request.args.get('result_property')
    if result_property == 'resultTime':
        result_property_name = 'CPU time (s)'
    elif result_property == 'wallTime':
        result_property_name = 'Wall Clock time (s)'
    elif result_property == 'cost':
        result_property_name = 'Cost'
    else:
        result_property = db.session.query(db.Property).get(int(result_property)).idProperty
        result_property_name = db.session.query(db.Property).get(int(result_property)).name

    results_by_sc = dict()
    for sc in solver_configs:
        results_by_sc[sc] = [r.get_property_value(result_property, db) for r in db.session.query(db.ExperimentResult) \
            .options(joinedload_all('properties')) \
            .filter_by(experiment=exp,
                       solver_configuration=sc).filter(
            db.ExperimentResult.Instances_idInstance.in_(instance_ids)).all()]
        results_by_sc[sc] = filter(lambda r: r is not None, results_by_sc[sc])

    if request.args.has_key('csv'):
        csv_response = StringIO.StringIO()
        csv_writer = csv.writer(csv_response)
        for sc in solver_configs:
            csv_writer.writerow([result_property_name + ' of ' + str(sc)])
            csv_writer.writerow(map(str, results_by_sc[sc]))
        csv_response.seek(0)

        headers = Headers()
        headers.add('Content-Type', 'text/csv')
        headers.add('Content-Disposition', 'attachment', filename=secure_filename(exp.name + "_rtd.csv"))
        return Response(response=csv_response.read(), headers=headers)
    else:
        return make_plot_response(plots.property_distribution, results_by_sc, result_property_name, log_property,
                                  restart_strategy)


@plot.route('/<database>/experiment/<int:experiment_id>/kerneldensity-plot/')
@require_phase(phases=ANALYSIS2)
@require_login
def kerneldensity(database, experiment_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    solver_configs = db.session.query(db.SolverConfiguration).filter(
        db.SolverConfiguration.idSolverConfig.in_(int(id) for id in request.args.getlist('sc'))).all()
    instances = db.session.query(db.Instance).filter(
        db.Instance.idInstance.in_(int(id) for id in request.args.getlist('i'))).all()
    instance_ids = [i.idInstance for i in instances]

    log_property = request.args.has_key('log_property')
    restart_strategy = request.args.has_key('restart_strategy')
    result_property = request.args.get('result_property')
    if result_property == 'resultTime':
        result_property_name = 'CPU time (s)'
    elif result_property == 'wallTime':
        result_property_name = 'Wall Clock time (s)'
    elif result_property == 'cost':
        result_property_name = 'Cost'
    else:
        result_property = db.session.query(db.Property).get(int(result_property)).idProperty
        result_property_name = db.session.query(db.Property).get(int(result_property)).name

    results_by_sc = dict()
    for sc in solver_configs:
        results_by_sc[sc] = [r.get_property_value(result_property, db) for r in db.session.query(db.ExperimentResult) \
            .options(joinedload_all('properties')) \
            .filter_by(experiment=exp,
                       solver_configuration=sc).filter(
            db.ExperimentResult.Instances_idInstance.in_(instance_ids)).all()]
        results_by_sc[sc] = filter(lambda r: r is not None, results_by_sc[sc])

    if request.args.has_key('csv'):
        csv_response = StringIO.StringIO()
        csv_writer = csv.writer(csv_response)
        for sc in results_by_sc:
            csv_writer.writerow([result_property_name + ' of ' + str(sc)])
            csv_writer.writerow(map(str, results_by_sc[sc]))
        csv_response.seek(0)

        headers = Headers()
        headers.add('Content-Type', 'text/csv')
        headers.add('Content-Disposition', 'attachment', filename=secure_filename(exp.name + "_kerneldensity.csv"))
        return Response(response=csv_response.read(), headers=headers)
    else:
        return make_plot_response(plots.kerneldensity, results_by_sc, result_property_name, log_property,
                                  restart_strategy)


@plot.route('/<database>/experiment/<int:experiment_id>/box-plots-plot/')
@require_phase(phases=ANALYSIS2)
@require_login
def box_plots(database, experiment_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    instance_ids = map(int, request.args.getlist('i'))
    solver_config_ids = map(int, request.args.getlist('solver_configs'))

    last_modified_job = db.session.query(func.max(db.ExperimentResult.date_modified)) \
        .filter_by(experiment=exp).first()
    job_count = db.session.query(db.ExperimentResult).filter_by(experiment=exp).count()

    @cache.memoize(7 * 24 * 60 * 60)
    def cached_box_plot(database, experiment_id, instance_ids, solver_config_ids, job_count, last_modified_job,
                        result_property, plot_type):
        instances = db.session.query(db.Instance).filter(db.Instance.idInstance.in_(instance_ids)).all()
        solver_configs = db.session.query(db.SolverConfiguration).filter(
            db.SolverConfiguration.idSolverConfig.in_(solver_config_ids)).all()

        if result_property == 'resultTime':
            result_property_name = 'CPU time (s)'
        elif result_property == 'wallTime':
            result_property_name = 'Wall Clock Time (s)'
        elif result_property == 'cost':
            result_property_name = 'Cost'
        else:
            result_property = db.session.query(db.Property).get(int(result_property)).idProperty
            result_property_name = db.session.query(db.Property).get(int(result_property)).name

        prop_value = dict((sc.idSolverConfig, dict()) for sc in solver_configs)
        for run in db.session.query(db.ExperimentResult).options(joinedload_all('properties')) \
            .filter_by(experiment=exp).filter(db.ExperimentResult.Instances_idInstance.in_(instance_ids)) \
            .filter(db.ExperimentResult.SolverConfig_idSolverConfig.in_(solver_config_ids)).all():
            if not run.Instances_idInstance in prop_value[run.SolverConfig_idSolverConfig]:
                prop_value[run.SolverConfig_idSolverConfig][run.Instances_idInstance] = list()
            prop_value[run.SolverConfig_idSolverConfig][run.Instances_idInstance].append(
                run.get_property_value(result_property, db))

        results = {}
        for sc in solver_configs:
            points = []
            for instance in instances:
                points += filter(lambda r: r is not None, prop_value[sc.idSolverConfig][instance.idInstance])
            results[sc.name] = points

        if plot_type == 'csv':
            csv_response = StringIO.StringIO()
            csv_writer = csv.writer(csv_response)
            for k, v in results.iteritems():
                csv_writer.writerow([k] + map(str, v))
            csv_response.seek(0)

            headers = Headers()
            headers.add('Content-Type', 'text/csv')
            headers.add('Content-Disposition', 'attachment', filename=secure_filename(exp.name + "_box_plots.csv"))
            return Response(response=csv_response.read(), headers=headers)
        else:
            return make_plot_response(plots.box_plot, results, result_property_name)

    return cached_box_plot(database, experiment_id, instance_ids, solver_config_ids, job_count, last_modified_job,
                           request.args.get('result_property'), get_request_plot_type())


@plot.route('/<database>/experiment/<int:experiment_id>/barplot/<int:gt>/<int:eq>/<int:lt>')
@require_phase(phases=ANALYSIS2)
@require_login
def barplot(database, experiment_id, gt, eq, lt):
    return make_plot_response(plots.barplot, [gt, eq, lt])


@plot.route('/<database>/experiment/<int:experiment_id>/runtime-matrix-plot-img/')
@require_phase(phases=ANALYSIS2)
@require_login
def runtime_matrix_plot(database, experiment_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    measure = request.args.get('measure', 'par10') or abort(404)
    last_modified_job = db.session.query(func.max(db.ExperimentResult.date_modified)) \
        .filter_by(experiment=exp).first()
    cost = request.args.get('result_property', 'resultTime')

    #CACHE_TIME = 14*24*60*60
    #@cache.memoize(timeout=CACHE_TIME)
    def make_rtm_response(experiment_id, last_modified_job, measure, num_jobs, cost, csv=False, type='png'):
        solver_configs = sorted(exp.solver_configurations, key=lambda sc: sc.idSolverConfig)
        instances = sorted(exp.instances, key=lambda i: i.idInstance)
        solver_configs_dict = dict((sc.idSolverConfig, sc) for sc in solver_configs)

        table = db.metadata.tables['ExperimentResults']
        from_table = table
        table_has_prop = db.metadata.tables['ExperimentResult_has_Property']
        table_has_prop_value = db.metadata.tables['ExperimentResult_has_PropertyValue']
        cost_limit = table.c['CPUTimeLimit'] if cost == 'resultTime' else table.c[
            'wallClockTimeLimit'] if cost == 'wallTime' else exp.cost_penalty if cost == 'cost' else None

        if cost in ('resultTime', 'wallTime', 'cost'):
            cost_c = table.c[cost]
        else:
            cost_c = table_has_prop_value.c['value']
            from_table = table.join(table_has_prop, and_(table_has_prop.c['idProperty'] == int(cost),
                                                         table_has_prop.c['idExperimentResults'] == table.c[
                                                             'idJob'])).join(table_has_prop_value)

        if cost not in ('resultTime', 'wallTime', 'cost'):
            s = select([func.max(expression.cast(cost_c, sqlalchemy.types.Float))],
                       table.c['Experiment_idExperiment'] == experiment_id).select_from(from_table)
            cost_limit = float(db.session.connection().execute(s).fetchone()[0])

        if measure == 'par10':
            time_case = expression.case([
                                            (table.c['resultCode'].like(u'1%'),
                                             expression.cast(cost_c, sqlalchemy.types.Float))],
                                        else_=cost_limit * 10.0)
        else:
            time_case = cost_c

        s = select([time_case,
                    table.c['resultCode'],
                    table.c['SolverConfig_idSolverConfig'],
                    table.c['Instances_idInstance']],
                   table.c['Experiment_idExperiment'] == experiment_id).select_from(from_table)
        runs = db.session.connection().execute(s)

        if measure == 'mean':
            aggregate_func = func.AVG(time_case)
        elif measure == 'min':
            aggregate_func = func.MIN(time_case)
        elif measure == 'max':
            aggregate_func = func.MAX(time_case)
        elif measure == 'par10' or measure is None:
            aggregate_func = func.AVG(time_case)

        s = select([table.c['SolverConfig_idSolverConfig'],
                    aggregate_func], table.c['Experiment_idExperiment'] == experiment_id) \
            .group_by(table.c['SolverConfig_idSolverConfig']) \
            .select_from(from_table)
        solver_score = dict((sc[0], float(sc[1])) for sc in db.session.connection().execute(s))

        # throw out all solver configs for which there are no runs
        solver_configs = filter(lambda sc: sc.idSolverConfig in solver_score.keys(), solver_configs)

        s = select([table.c['Instances_idInstance'],
                    aggregate_func], table.c['Experiment_idExperiment'] == experiment_id) \
            .group_by(table.c['Instances_idInstance']) \
            .select_from(from_table)
        instance_hardness = dict((inst[0], float(inst[1])) for inst in db.session.connection().execute(s))

        results_by_instance = {}
        for r in runs:
            c = float(r[0])
            if r.Instances_idInstance not in results_by_instance:
                results_by_instance[r.Instances_idInstance] = {r.SolverConfig_idSolverConfig: [c]}
            else:
                rs = results_by_instance[r.Instances_idInstance]
                if r.SolverConfig_idSolverConfig not in rs:
                    rs[r.SolverConfig_idSolverConfig] = [c]
                else:
                    rs[r.SolverConfig_idSolverConfig].append(c)

        sorted_solver_configs = sorted(solver_configs, key=lambda sc: solver_score[sc.idSolverConfig])
        sorted_instances = sorted(instances, key=lambda i: instance_hardness[i.idInstance])

        rt_matrix = dict((sc.idSolverConfig, dict((i.idInstance, None) for i in instances)) for sc in solver_configs)
        flattened_rt_matrix = []
        for instance in sorted_instances:
            if instance.idInstance not in results_by_instance: continue
            rs = results_by_instance[instance.idInstance]
            for solver_config in sorted_solver_configs:
                jobs = rs.get(solver_config.idSolverConfig, [])
                runtimes = filter(lambda r: r is not None, jobs)
                time_measure = None
                if len(runtimes) > 0:
                    if measure == 'mean':
                        time_measure = numpy.average(runtimes)
                    elif measure == 'median':
                        time_measure = numpy.median(runtimes)
                    elif measure == 'min':
                        time_measure = min(runtimes)
                    elif measure == 'max':
                        time_measure = max(runtimes)
                    elif measure == 'par10' or measure is None:
                        time_measure = numpy.average(jobs or [0])
                if request.args.has_key('csv'): rt_matrix[solver_config.idSolverConfig][
                    instance.idInstance] = time_measure
                flattened_rt_matrix.append(time_measure + 0.0000001)

        if csv:
            csv_response = StringIO.StringIO()
            csv_writer = csv.writer(csv_response)
            csv_writer.writerow([''] + map(str, sorted_solver_configs))
            for instance in sorted_instances:
                row = [str(instance)]
                for sc in sorted_solver_configs:
                    row.append(str(rt_matrix[sc.idSolverConfig][instance.idInstance]))
                csv_writer.writerow(row)
            csv_response.seek(0)

            headers = Headers()
            headers.add('Content-Type', 'text/csv')
            headers.add('Content-Disposition', 'attachment', filename=secure_filename(exp.name + "_runtime_matrix.csv"))
            return Response(response=csv_response.read(), headers=headers)
        else:
            return make_plot_response(plots.runtime_matrix_plot, flattened_rt_matrix, len(sorted_solver_configs),
                                      len(sorted_instances),
                                      measure)

    if request.args.has_key('pdf'):
        type = 'pdf'
    elif request.args.has_key('eps'):
        type = 'eps'
    elif request.args.has_key('rscript'):
        type = 'rscript'
    else:
        type = 'png'
    return make_rtm_response(experiment_id, last_modified_job, measure, exp.get_num_jobs(db), cost,
                             request.args.has_key('csv'), type)


@plot.route('/<database>/experiment/<int:experiment_id>/parameter-plot-1d-img/')
@require_phase(phases=ANALYSIS2)
@require_login
def parameter_plot_1d(database, experiment_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    parameter_id = int(request.args.get('parameter'))
    parameter_name = db.session.query(db.Parameter).get(parameter_id).name
    measure = request.args.get('measure', 'par10')
    instance_ids = map(int, request.args.getlist('i'))
    runtime_cap = float(request.args.get('runtime_cap'))
    log_param = request.args.has_key('log_x')
    log_cost = request.args.has_key('log_y')

    last_modified_job = db.session.query(func.max(db.ExperimentResult.date_modified)) \
        .filter_by(experiment=exp).first()

    CACHE_TIME = 14 * 24 * 60 * 60

    @cache.memoize(timeout=CACHE_TIME)
    def plot_image(experiment_id, parameter_id, measure, instance_ids, runtime_cap, last_modified_job, type, num_jobs,
                   log_param, log_cost):
        table = db.metadata.tables['ExperimentResults']
        table_sc = db.metadata.tables['SolverConfig']
        if measure == 'par10':
            to_expr = (exp.costPenalty if exp.defaultCost == 'cost' else table.c['CPUTimeLimit'] if exp.defaultCost == 'resultTime' else table.c['wallClockTimeLimit'])
            time_case = expression.case([
                                            (table.c['resultCode'].like(u'1%'), table.c[exp.defaultCost])],
                                        else_=to_expr * 10.0)
        else:
            time_case = table.c[exp.defaultCost]

        s = select([time_case,
                    table.c['SolverConfig_idSolverConfig']],
                   and_(table.c['Experiment_idExperiment'] == experiment_id,
                        table_sc.c[
                            'SolverBinaries_idSolverBinary'] == exp.configuration_scenario.SolverBinaries_idSolverBinary,
                        not_(table.c['status'].in_((-1, 0,))),
                        table.c['Instances_idInstance'].in_(instance_ids)
                   ), from_obj=table.join(table_sc))
        runs = db.session.connection().execute(s)

        table_sc = db.metadata.tables['SolverConfig']
        table_sc_params = db.metadata.tables['SolverConfig_has_Parameters']
        s = select(['idSolverConfig', 'value'],
                   and_(table_sc.c['Experiment_idExperiment'] == experiment_id,
                        table_sc_params.c['Parameters_idParameter'] == parameter_id),
                   from_obj=table_sc.join(table_sc_params))
        param_values = db.session.connection().execute(s)

        solver_configs = db.session.query(db.SolverConfiguration).filter_by(experiment=exp).all()
        sc_dict = dict((sc.idSolverConfig, sc) for sc in solver_configs)
        sc_param_values = dict((sc.idSolverConfig, None) for sc in solver_configs)
        for pv in param_values: sc_param_values[pv.idSolverConfig] = float(pv.value)

        solver_config_times = dict((sc.idSolverConfig, list()) for sc in solver_configs)
        sc_run_count = dict((sc.idSolverConfig, 0) for sc in solver_configs)
        for run in runs:
            solver_config_times[run.SolverConfig_idSolverConfig].append(run[0])

        data = []
        for sc in solver_config_times.keys():
            if len(solver_config_times[sc]) == 0: continue
            if measure == "par10" or measure == "mean":
                cost = sum(solver_config_times[sc]) / len(solver_config_times[sc])
            elif measure == "max":
                cost = max(solver_config_times[sc])
            elif measure == "min":
                cost = min(solver_config_times[sc])
            elif measure == "median":
                cost = numpy.median(solver_config_times[sc])
            data.append((sc_param_values[sc], cost))

        return make_plot_response(plots.parameter_plot_1d, data, parameter_name, measure, runtime_cap, log_param,
                                  log_cost)

    if request.args.has_key('pdf'):
        type = 'pdf'
    elif request.args.has_key('eps'):
        type = 'eps'
    elif request.args.has_key('rscript'):
        type = 'rscript'
    else:
        type = 'png'
    return plot_image(experiment_id, parameter_id, measure, instance_ids, runtime_cap, last_modified_job, type,
                      exp.get_num_jobs(db), log_param, log_cost)


@plot.route('/<database>/experiment/<int:experiment_id>/parameter-plot-2d-img/')
@require_phase(phases=ANALYSIS2)
@require_login
def parameter_plot_2d(database, experiment_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    surface_interpolation = request.args.has_key('surface_interpolation')
    parameter1_id = int(request.args.get('parameter1'))
    parameter2_id = int(request.args.get('parameter2'))
    parameter1_name = db.session.query(db.Parameter).get(parameter1_id).name
    parameter2_name = db.session.query(db.Parameter).get(parameter2_id).name
    measure = request.args.get('measure', 'par10')
    log_x = request.args.has_key('log_x')
    log_y = request.args.has_key('log_y')
    log_cost = request.args.has_key('log_cost')
    instance_ids = map(int, request.args.getlist('i'))
    runtime_cap = float(request.args.get('runtime_cap'))

    last_modified_job = db.session.query(func.max(db.ExperimentResult.date_modified)) \
        .filter_by(experiment=exp).first()

    CACHE_TIME = 14 * 24 * 60 * 60

    @cache.memoize(timeout=CACHE_TIME)
    def plot_image(experiment_id, parameter1_id, parameter2_id, measure, instance_ids,
                   runtime_cap, last_modified_job, surface_interpolation, type, num_jobs,
                   log_x, log_y, log_cost):
        table = db.metadata.tables['ExperimentResults']
        table_sc = db.metadata.tables['SolverConfig']
        table_sc_params1 = alias(db.metadata.tables['SolverConfig_has_Parameters'], "param1")
        table_sc_params2 = alias(db.metadata.tables['SolverConfig_has_Parameters'], "param2")

        if measure == 'par10':
            to_expr = (exp.costPenalty if exp.defaultCost == 'cost' else table.c['CPUTimeLimit'] if exp.defaultCost == 'resultTime' else table.c['wallClockTimeLimit'])
            time_case = expression.case([
                                            (table.c['resultCode'].like(u'1%'), table.c[exp.defaultCost])],
                                        else_=to_expr * 10.0)
        else:
            time_case = table.c[exp.defaultCost]

        s = select([time_case,
                    table.c['SolverConfig_idSolverConfig']],
                   and_(table.c['Experiment_idExperiment'] == experiment_id,
                        table_sc.c[
                            'SolverBinaries_idSolverBinary'] == exp.configuration_scenario.SolverBinaries_idSolverBinary,
                        not_(table.c['status'].in_((-1, 0,))),
                        table.c['Instances_idInstance'].in_(instance_ids)
                   ), from_obj=table.join(table_sc))
        runs = db.session.connection().execute(s)

        s = select(['idSolverConfig', table_sc_params1.c['value'], table_sc_params2.c['value']],
                   and_(table_sc.c['Experiment_idExperiment'] == experiment_id,
                        table_sc_params1.c['Parameters_idParameter'] == parameter1_id,
                        table_sc_params2.c['Parameters_idParameter'] == parameter2_id,
                        table_sc_params1.c['value'] != None, table_sc_params2.c['value'] != None),
                   from_obj=table_sc.join(table_sc_params1).join(table_sc_params2))
        param_values = db.session.connection().execute(s)

        solver_configs = db.session.query(db.SolverConfiguration).filter_by(experiment=exp).all()
        sc_dict = dict((sc.idSolverConfig, sc) for sc in solver_configs)
        sc_param_values = dict((sc.idSolverConfig, None) for sc in solver_configs)
        for pv in param_values: sc_param_values[pv.idSolverConfig] = (float(pv[1]), float(pv[2]))

        solver_config_times = dict((sc.idSolverConfig, list()) for sc in solver_configs)
        sc_run_count = dict((sc.idSolverConfig, 0) for sc in solver_configs)
        for run in runs:
            solver_config_times[run.SolverConfig_idSolverConfig].append(run[0])

        data = []
        for sc in solver_config_times.keys():
            if len(solver_config_times[sc]) == 0: continue
            if sc_param_values[sc] is None: continue
            if measure == "par10" or measure == "mean":
                cost = sum(solver_config_times[sc]) / len(solver_config_times[sc])
            elif measure == "max":
                cost = max(solver_config_times[sc])
            elif measure == "min":
                cost = min(solver_config_times[sc])
            elif measure == "median":
                cost = numpy.median(solver_config_times[sc])

            data.append(sc_param_values[sc] + (cost,))

        return make_plot_response(plots.parameter_plot_2d, data, parameter1_name, parameter2_name, measure,
                                  surface_interpolation, runtime_cap=runtime_cap, log_x=log_x, log_y=log_y,
                                  log_cost=log_cost)

    if request.args.has_key('pdf'):
        type = 'pdf'
    elif request.args.has_key('eps'):
        type = 'eps'
    elif request.args.has_key('rscript'):
        type = 'rscript'
    else:
        type = 'png'
    return plot_image(experiment_id, parameter1_id, parameter2_id, measure, instance_ids, runtime_cap,
                      last_modified_job, surface_interpolation, type, exp.get_num_jobs(db), log_x, log_y, log_cost)


@plot.route('/<database>/experiment/<int:experiment_id>/perc-solved-alone/')
@require_phase(phases=ANALYSIS2)
@require_login
def perc_solved_alone(database, experiment_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    instance_ids = map(int, request.args.getlist('i'))
    solver_config_ids = map(int, request.args.getlist('sc'))
    solver_configs = [sc for sc in exp.solver_configurations if sc.idSolverConfig in solver_config_ids]

    table = db.metadata.tables['ExperimentResults']
    s = select([table.c['SolverConfig_idSolverConfig'],
                table.c['Instances_idInstance']],
               and_(table.c['resultCode'].like(u'1%'),
                    table.c['Instances_idInstance'].in_(instance_ids),
                    table.c['SolverConfig_idSolverConfig'].in_(solver_config_ids),
                    table.c['Experiment_idExperiment'] == exp.idExperiment,
                    table.c['status'] == 1)).select_from(table)
    successful_runs = db.session.connection().execute(s)

    solved_instances = set()
    solved_instances_by_solver = dict((sc, set()) for sc in solver_config_ids)
    for run in successful_runs:
        solved_instances.add(run.Instances_idInstance)
        solved_instances_by_solver[run.SolverConfig_idSolverConfig].add(run.Instances_idInstance)

    perc_solved_by_solver = dict()
    for sc in solver_configs:
        perc_solved_by_solver[sc] = len(solved_instances_by_solver[sc.idSolverConfig]) / float(
            len(solved_instances)) if len(solved_instances) != 0 else 0

    return make_plot_response(plots.perc_solved_alone, perc_solved_by_solver)


@plot.route('/<database>/experiment/<int:experiment_id>/correlation-matrix-plot/')
@require_phase(phases=ANALYSIS2)
@require_login
def correlation_matrix_plot(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    instances = db.session.query(db.Instance).filter(
        db.Instance.idInstance.in_(map(int, request.args.getlist('i')))).all()
    solver_configs = db.session.query(db.SolverConfiguration).filter(
        db.SolverConfiguration.idSolverConfig.in_(map(int, request.args.getlist('sc')))).all()

    @cache.memoize(7 * 24 * 60 * 60)
    def cached_correlation_matrix_plot(database, experiment_id, sc_names, request_args, job_count, last_modified_job):
        result_matrix, _, _ = experiment.get_result_matrix(db, solver_configs, instances,
                                                           request.args.get('cost', 'resultTime'))
        sc_correlation = dict((sc, dict()) for sc in solver_configs)
        for sc1 in solver_configs:
            for sc2 in solver_configs:
                if sc1 == sc2: sc_correlation[sc1][sc2] = sc_correlation[sc2][sc1] = 1.0; continue
                if sc1 in sc_correlation and sc2 in sc_correlation[sc1]: continue
                v1 = []
                v2 = []
                for instance in instances:
                    for sc1run, sc2run in zip(result_matrix[instance.idInstance][sc1.idSolverConfig],
                                              result_matrix[instance.idInstance][sc2.idSolverConfig]):
                        v1.append(sc1run.penalized_time1)
                        v2.append(sc2run.penalized_time1)
                sc_correlation[sc1][sc2] = statistics.spearman_correlation(v1, v2)[0]
                sc_correlation[sc2][sc1] = sc_correlation[sc1][sc2]

        return make_plot_response(plots.correlation_matrix_plot, sc_correlation)


    last_modified_job = db.session.query(func.max(db.ExperimentResult.date_modified)) \
        .filter_by(experiment=experiment).first()
    job_count = db.session.query(db.ExperimentResult).filter_by(experiment=experiment).count()

    return cached_correlation_matrix_plot(database, experiment_id, ''.join(sc.name for sc in solver_configs),
                                          request.args, job_count, last_modified_job)
