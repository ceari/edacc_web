# -*- coding: utf-8 -*-
"""
    edacc.views.frontend
    --------------------

    This module defines request handler functions for the main functionality
    of the web application.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

import csv
import datetime
try:
    from cjson import encode as json_dumps
except:
    try:
        from simplejson import dumps as json_dumps
    except ImportError:
        from json import dumps as json_dumps

import numpy
import StringIO
import tempfile
import tarfile
import Image
import time
import os
from scipy.stats.mstats import mquantiles

from flask import Blueprint
from flask import render_template as render
from flask import Response, abort, g, request, redirect, url_for
from werkzeug import Headers, secure_filename

from edacc import utils, models
from sqlalchemy.orm import joinedload, joinedload_all
from sqlalchemy import func, text as sqla_text
from edacc.constants import *
from edacc.views.helpers import require_phase, require_competition
from edacc.views.helpers import require_login, is_admin
from edacc import forms
from edacc.forms import EmptyQuery
from edacc import monitor, clientMonitor
from edacc import config
from edacc import config_visualisation

frontend = Blueprint('frontend', __name__, template_folder='static')

@frontend.route('/impressum/<lang>')
@frontend.route('/impressum')
def impressum(lang=None):
    if lang == "en":
        return render('/impressum_en.html')
    else:
        return render('/impressum.html')


@frontend.route('/privacy')
def privacy():
    return render('/privacy.html')

@frontend.route('/')
def index():
    """ Show a list of all served databases """
    databases = list(models.get_databases().itervalues())
    databases.sort(key=lambda db: db.database.lower())

    return render('/databases.html', databases=databases)

@frontend.route('/<database>/index')
@frontend.route('/<database>/experiments/')
@require_phase(phases=(1, 2, 3, 4, 5, 6, 7))
def experiments_index(database):
    """Show a list of all experiments in the database."""
    db = models.get_database(database) or abort(404)

    if db.is_competition() and db.competition_phase() not in OWN_RESULTS.union(ALL_RESULTS):
        # Experiments are only visible in phases 3 through 7 in a competition database
        experiments = []
    else:
        experiments = db.session.query(db.Experiment).all()
        experiments.sort(key=lambda e: e.date)

    return render('experiments.html', experiments=experiments, db=db, database=database)

@frontend.route('/<database>/categories')
@require_competition
def categories(database):
    """Displays a static categories page."""
    db = models.get_database(database) or abort(404)

    try:
        return render('/competitions/%s/categories.html' % (database,), db=db, database=database)
    except:
        abort(404)


@frontend.route('/<database>/overview/')
@require_competition
def competition_overview(database):
    """Displays a static overview page."""
    db = models.get_database(database) or abort(404)

    try:
        return render('/competitions/%s/overview.html' % (database,), db=db, database=database)
    except:
        abort(404)


@frontend.route('/<database>/schedule/')
@require_competition
def competition_schedule(database):
    """Displays a static schedule page."""
    db = models.get_database(database) or abort(404)

    try:
        return render('/competitions/%s/schedule.html' % (database,), db=db, database=database)
    except:
        abort(404)


@frontend.route('/<database>/rules/')
@require_competition
def competition_rules(database):
    """Displays a static rules page."""
    db = models.get_database(database) or abort(404)

    try:
        return render('/competitions/%s/rules.html' % (database,), db=db, database=database)
    except:
        abort(404)


@frontend.route('/<database>/experiment/<int:experiment_id>/')
@require_phase(phases=(2, 3, 4, 5, 6, 7))
@require_login
def experiment(database, experiment_id):
    """ Show menu with links to info and evaluation pages """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    return render('experiment.html', experiment=experiment, database=database,
                  db=db, OWN_RESULTS=OWN_RESULTS, ALL_RESULTS=ALL_RESULTS,
                  ANALYSIS1=ANALYSIS1, ANALYSIS2=ANALYSIS2, RANKING=RANKING, is_admin=is_admin)


@frontend.route('/<database>/experiment/<int:experiment_id>/solver-configurations')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def experiment_solver_configurations(database, experiment_id):
    """ List all solver configurations (solver + parameter set) used in the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    solver_configurations = db.session.query(db.SolverConfiguration) \
                                .filter_by(experiment=experiment).all()
    
    # if competition db, show only own solvers if the phase is in OWN_RESULTS
    if not is_admin() and db.is_competition() and db.competition_phase() in OWN_RESULTS:
        solver_configurations = filter(lambda sc: sc.solver_binary.solver.user == g.User, solver_configurations)

    return render('experiment_solver_configurations.html', experiment=experiment,
                  solver_configurations=solver_configurations,
                  database=database, db=db)


@frontend.route('/<database>/experiment/<int:experiment_id>/instances')
@require_phase(phases=(2, 3, 4, 5, 6, 7))
@require_login
def experiment_instances(database, experiment_id):
    """ Show information about all instances used in the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    instances = experiment.get_instances(db)

    return render('experiment_instances.html', instances=instances,
                  experiment=experiment, database=database, db=db,
                  instance_properties=db.get_instance_properties())


@frontend.route('/<database>/experiment/<int:experiment_id>/download-instances')
@require_phase(phases=(6,7))
@require_login
def download_instances(database, experiment_id):
    """ Lets users download all instances of the experiment as tarball. TODO: improve memory usage """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    instances = experiment.get_instances(db)

    tmp_file = tempfile.TemporaryFile("w+b")
    tar_file = tarfile.open(mode='w', fileobj=tmp_file)
    for instance in instances:
        instance_blob = instance.get_instance(db)
        instance_tar_info = tarfile.TarInfo(name=instance.name)
        instance_tar_info.size = len(instance_blob)
        instance_tar_info.type = tarfile.REGTYPE
        instance_tar_info.mtime = time.mktime(datetime.datetime.now().timetuple())
        tar_file.addfile(instance_tar_info, fileobj=StringIO.StringIO(instance_blob))
    tar_file.close()

    file_size = tmp_file.tell()
    tmp_file.seek(0)

    headers = Headers()
    headers.add('Content-Type', 'application/x-tar')
    headers.add('Content-Length', file_size)
    headers.add('Content-Disposition', 'attachment',
                filename=(secure_filename(experiment.name + "_instances.tar")))
    return Response(tmp_file, headers=headers, direct_passthrough=True)


@frontend.route('/<database>/experiment/<int:experiment_id>/results/')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def experiment_results(database, experiment_id):
    """ Show a table with the solver configurations and their results on the instances of the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    solver_configs = db.session.query(db.SolverConfiguration).options(joinedload_all('solver_binary'))\
                                        .filter_by(experiment=experiment).all()

    # if competition db, show only own solvers unless phase is 6 or 7
    if not is_admin() and db.is_competition() and db.competition_phase() in OWN_RESULTS:
        solver_configs = filter(lambda sc: sc.solver_binary.solver.user == g.User, solver_configs)

    form = forms.ResultsBySolverAndInstanceForm(request.args)
    form.i.query = sorted(experiment.get_instances(db), key=lambda i: i.get_name()) or EmptyQuery()
    form.solver_configs.query = solver_configs or EmptyQuery()

    if form.i.data:
        instances = form.i.data
    else:
        instances = experiment.instances

    if not form.cost.data:
        form.cost.data = 'cputime'

    if form.solver_configs.data:
        solver_configs = form.solver_configs.data
    else:
        solver_configs = []

    instances_dict = dict((i.idInstance, i) for i in instances)
    solver_configs_dict = dict((sc.idSolverConfig, sc) for sc in solver_configs)
    
    results_by_instance, S, C = experiment.get_result_matrix(db, solver_configs, instances, cost=form.cost.data)

    times_by_solver = dict((sc_id, list()) for sc_id in solver_configs_dict.iterkeys())
    cv_by_solver = dict((sc_id, list()) for sc_id in solver_configs_dict.iterkeys())
    qcd_by_solver = dict((sc_id, list()) for sc_id in solver_configs_dict.iterkeys())
    results = []
    best_sc_by_instance_id = {}
    for idInstance in instances_dict.iterkeys():
        row = []
        if idInstance not in results_by_instance: continue
        rs = results_by_instance[idInstance]
        best_sc_by_instance_id[idInstance] = None
        best_sc_time = None

        for solver_config in solver_configs:
            idSolverConfig = solver_config.idSolverConfig
            jobs = rs.get(idSolverConfig, [])

            completed = C[idInstance][idSolverConfig]
            successful = S[idInstance][idSolverConfig]
            runtimes = [j.resultTime for j in jobs if j.resultTime is not None]

            time_measure = None
            coeff_variation = None
            quartile_coeff_dispersion = None
            if len(runtimes) > 0:
                if form.display_measure.data == 'mean':
                    time_measure = numpy.average(runtimes)
                elif form.display_measure.data == 'median':
                    time_measure = numpy.median(runtimes)
                elif form.display_measure.data == 'min':
                    time_measure = min(runtimes)
                elif form.display_measure.data == 'max':
                    time_measure = max(runtimes)
                elif form.display_measure.data == 'par10' or form.display_measure.data is None:
                    time_measure = numpy.average([j.penalized_time10 for j in jobs] or [0])

                times_by_solver[idSolverConfig].append(time_measure)
                if form.calculate_dispersion.data:
                    coeff_variation = numpy.std(runtimes) / numpy.average(runtimes)
                    quantiles = mquantiles(runtimes, [0.25, 0.5, 0.75])
                    quartile_coeff_dispersion = (quantiles[2] - quantiles[0]) / quantiles[1]

                    cv_by_solver[idSolverConfig].append(coeff_variation)
                    qcd_by_solver[idSolverConfig].append(quartile_coeff_dispersion)

            if (best_sc_by_instance_id[idInstance] is None or time_measure < best_sc_time) and successful > 0:
                best_sc_time = time_measure
                best_sc_by_instance_id[idInstance] = solver_config.idSolverConfig

            if completed > 0:
                red = (1.0, 0, 0.0)
                green = (0.0, 0.8, 0.2) # darker green
                t = successful/float(completed)
                bg_color = ((green[0] - red[0]) * t + red[0], (green[1] - red[1]) * t + red[1], (green[2] - red[2]) * t + red[2])
                bg_color = hex((int(bg_color[0] * 255) << 16) + (int(bg_color[1] * 255) << 8) + (int(bg_color[2] * 255)))[2:].zfill(6) # remove leading 0x
            else:
                bg_color = 'FF8040' #orange

            row.append({'time_measure': time_measure ,
                        'coeff_variation': coeff_variation,
                        'quartile_coeff_dispersion': quartile_coeff_dispersion,
                        'successful': successful,
                        'completed': completed,
                        'bg_color': bg_color,
                        'total': len(jobs),
                        # needed for alternative presentation if there's only 1 run:
                        'first_job': (None if len(jobs) == 0 else jobs[0]),
                        'solver_config': solver_config,
                        })
        results.append({'instance': instances_dict[idInstance], 'times': row, 'best_time': best_sc_time})

    sum_by_solver = dict((sc_id, 0) for sc_id in solver_configs_dict.iterkeys())
    avg_by_solver = dict((sc_id, 0) for sc_id in solver_configs_dict.iterkeys())
    avg_cv_by_solver = dict((sc_id, 0) for sc_id in solver_configs_dict.iterkeys())
    avg_qcd_by_solver = dict((sc_id, 0) for sc_id in solver_configs_dict.iterkeys())

    for idSolverConfig in solver_configs_dict.iterkeys():
        sum_by_solver[idSolverConfig] = sum(times_by_solver[idSolverConfig])
        avg_by_solver[idSolverConfig] = numpy.average(times_by_solver[idSolverConfig])
        avg_cv_by_solver[idSolverConfig] = numpy.average(cv_by_solver[idSolverConfig])
        avg_qcd_by_solver[idSolverConfig] = numpy.average(qcd_by_solver[idSolverConfig])

    if request.args.has_key('csv'):
        csv_response = StringIO.StringIO()
        csv_writer = csv.writer(csv_response)

        csv_writer.writerow(['Measure: ' + (form.display_measure.data or 'par10')])
        head = ['Instance', 'Best time']
        for sc in solver_configs_dict.values():
            head += [str(sc)]
        csv_writer.writerow(head)

        for row in results:
            write_row = [row['instance'].name, str(row['best_time'])]
            for sc_results in row['times']:
                if form.calculate_dispersion.data:
                    write_row.append(str(round(sc_results['time_measure'], 4)) + " (%.4f, %.4f)" % (sc_results['coeff_variation'], sc_results['quartile_coeff_dispersion']))
                else:
                    write_row.append(round(sc_results['time_measure'], 4))
            csv_writer.writerow(write_row)

        csv_writer.writerow(['Average', ''] + map(lambda x: str(round(x, 4)), [avg_by_solver[sc.idSolverConfig] for sc in solver_configs]))
        csv_writer.writerow(['Sum', ''] + map(lambda x: str(round(x, 4)), [sum_by_solver[sc.idSolverConfig] for sc in solver_configs]))
        if form.calculate_dispersion.data:
            csv_writer.writerow(['Avg. coefficient of variation', ''] + map(lambda x: str(round(x, 4)), [avg_cv_by_solver[sc.idSolverConfig] for sc in solver_configs]))
            csv_writer.writerow(['Avg. quartile coefficient of dispersion', ''] + map(lambda x: str(round(x, 4)), [avg_qcd_by_solver[sc.idSolverConfig] for sc in solver_configs]))

        csv_response.seek(0)
        headers = Headers()
        headers.add('Content-Type', 'text/csv')
        headers.add('Content-Disposition', 'attachment',
                    filename=secure_filename(experiment.name + "_results.csv"))
        return Response(response=csv_response.read(), headers=headers)

    base_result_details_url = url_for('frontend.experiment_result', database=database, experiment_id=experiment_id)
    return render('experiment_results.html', experiment=experiment,
                    instances=instances, solver_configs=solver_configs,
                    solver_configs_dict=solver_configs_dict,
                    instance_properties=db.get_instance_properties(),
                    instances_dict=instances_dict, best_sc_by_instance_id=best_sc_by_instance_id,
                    results=results, database=database, db=db, form=form,
                    sum_by_solver=sum_by_solver, avg_by_solver=avg_by_solver,
                    avg_cv_by_solver=avg_cv_by_solver, avg_qcd_by_solver=avg_qcd_by_solver,
                    base_result_details_url=base_result_details_url)

@frontend.route('/<database>/experiment/<int:experiment_id>/results-by-solver/')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def experiment_results_by_solver(database, experiment_id):
    """ Show the results of the experiment by solver configuration """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    num_runs = experiment.get_max_num_runs(db)

    solver_configs = experiment.solver_configurations

    if not is_admin() and db.is_competition() and db.competition_phase() in OWN_RESULTS:
        solver_configs = filter(lambda sc: sc.solver_binary.solver.user == g.User, solver_configs)

    form = forms.ResultBySolverForm(request.args)
    form.solver_config.query = solver_configs or EmptyQuery()

    results = []
    if form.solver_config.data:
        solver_config = form.solver_config.data
        if 'details' in request.args:
            return redirect(url_for('frontend.solver_configuration_details',
                                    database=database, experiment_id=experiment.idExperiment,
                                    solver_configuration_id=solver_config.idSolverConfig))

        ers = db.session.query(db.ExperimentResult).options(joinedload_all('instance.properties')) \
                                .filter_by(experiment=experiment,
                                    solver_configuration=solver_config) \
                                .order_by('ExperimentResults.Instances_idInstance', 'run').all()

        mean_by_instance = {}
        par10_by_instance = {} # penalized average runtime (timeout * 10 for unsuccessful runs) by instance
        var_by_instance = {} # variance over the runs per instance
        std_by_instance = {}
        runs_by_instance = {}
        jobs_by_instance = {}
        for r in ers:
            if not r.instance in runs_by_instance:
                runs_by_instance[r.instance] = [r]
            else:
                runs_by_instance[r.instance].append(r)

        for instance in runs_by_instance.keys():
            total_time, count = 0.0, 0
            runtimes = []
            for run in runs_by_instance[instance]:
                count += 1
                if run.status != 1 or not str(run.resultCode).startswith('1'):
                    runtimes.append(run.get_penalized_time(10))
                else:
                    runtimes.append(run.resultTime)
            total_time = sum(runtimes)

            var_by_instance[instance.idInstance] = numpy.var(runtimes) if runtimes else 'n/a'
            std_by_instance[instance.idInstance] = numpy.std(runtimes) if runtimes else 'n/a'
            mean_by_instance[instance.idInstance] = total_time / count if count > 0 else 'n/a'
            # fill up runs_by_instance with None's up to num_runs
            runs_by_instance[instance] += [None] * (num_runs - count)
            par10_by_instance[instance.idInstance] = total_time / float(count) if count != 0 else 0

        results = sorted(runs_by_instance.items(), key=lambda i: i[0].idInstance)

        if 'csv' in request.args:
            csv_response = StringIO.StringIO()
            csv_writer = csv.writer(csv_response)
            csv_writer.writerow(['Instance'] + ['Run'] * num_runs + ['penalized avg. runtime'] + ['Variance'])
            results = [[res[0].name] + [('' if r.get_time() is None else round(r.get_time(), 3)) for r in res[1]] +
                       ['' if par10_by_instance[res[0].idInstance] is None else round(par10_by_instance[res[0].idInstance], 4)] +
                       ['' if mean_by_instance[res[0].idInstance] is None else round(mean_by_instance[res[0].idInstance], 4)] +
                       ['' if var_by_instance[res[0].idInstance] is None else round(var_by_instance[res[0].idInstance], 4)] +
                       ['' if std_by_instance[res[0].idInstance] is None else round(std_by_instance[res[0].idInstance], 4)] for res in results]

            if request.args.get('sort_by_instance_name', None):
                sort_dir = request.args.get('sort_by_instance_name_dir', 'asc')
                results.sort(key=lambda r: r[0], reverse=sort_dir=='desc')

            if request.args.get('sort_by_par10', None):
                sort_dir = request.args.get('sort_by_par10_dir', 'asc')
                results.sort(key=lambda r: r[num_runs+1], reverse=sort_dir=='desc')

            search = request.args.get('search', "")
            if search:
                results = filter(lambda r: search in r[0], results)

            for res in results:
                csv_writer.writerow(res)
            csv_response.seek(0)

            headers = Headers()
            headers.add('Content-Type', 'text/csv')
            headers.add('Content-Disposition', 'attachment',
                        filename=(experiment.name + "_results_by_solver_%s.csv" % (str(solver_config),)))
            return Response(response=csv_response.read(), headers=headers)

        return render('experiment_results_by_solver.html', db=db, database=database,
                  solver_configs=solver_configs, experiment=experiment,
                  form=form, results=results, par10_by_instance=par10_by_instance, num_runs=num_runs,
                  var_by_instance=var_by_instance, std_by_instance=std_by_instance, mean_by_instance=mean_by_instance,
                  instance_properties=db.get_instance_properties())

    return render('experiment_results_by_solver.html', db=db, database=database,
                  solver_configs=solver_configs, experiment=experiment,
                  form=form, results=results, num_runs=num_runs,
                  instance_properties=db.get_instance_properties())


@frontend.route('/<database>/experiment/<int:experiment_id>/results-by-instance')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def experiment_results_by_instance(database, experiment_id):
    """ Show the results of the experiment by instance """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    instances = experiment.instances
    solver_configs = experiment.solver_configurations

    if not is_admin() and db.is_competition() and db.competition_phase() in OWN_RESULTS:
        solver_configs = filter(lambda sc: sc.solver_binary.solver.user == g.User, solver_configs)

    form = forms.ResultByInstanceForm(request.args)
    form.instance.query = sorted(experiment.get_instances(db), key=lambda i: i.get_name()) or EmptyQuery()
    num_runs = experiment.get_max_num_runs(db)

    results = []
    if form.instance.data:
        instance = form.instance.data
        if 'details' in request.args:
            return redirect(url_for('frontend.instance_details',
                                    database=database, instance_id=instance.idInstance))

        solver_config_ids = [sc.idSolverConfig for sc in solver_configs]
        results_by_sc = dict((id, list()) for id in solver_config_ids)
        for run in db.session.query(db.ExperimentResult).filter_by(experiment=experiment, instance=instance) \
                    .filter(db.ExperimentResult.SolverConfig_idSolverConfig.in_(solver_config_ids)) \
                    .order_by('Instances_idInstance', 'run').all():
            results_by_sc[run.SolverConfig_idSolverConfig].append(run)

        min_mean_sc, min_mean = None, 0
        min_median_sc, min_median = None, 0
        min_par10_sc, min_par10 = None, 0
        min_cv_sc, min_cv = None, 0
        min_qcd_sc, min_qcd = None, 0

        for sc in solver_configs:
            runs = results_by_sc[sc.idSolverConfig]

            mean, median, par10, cv, qcd = None, None, None, None, None
            successful = len([j for j in runs if str(j.resultCode).startswith("1")])
            if len(runs) > 0:
                runtimes = [j.get_time() for j in runs]
                runtimes = filter(lambda t: t is not None, runtimes)
                count = 0
                if len(runtimes) > 0:
                    par10 = 0.0
                for j in runs:
                    if j.get_time() is not None:
                        count += 1
                        if not str(j.resultCode).startswith('1') or j.status != 1:
                            par10 += j.get_penalized_time(10)
                        else:
                            par10 += j.get_time()
                if count > 0:
                    par10 /= count
                if len(runtimes) > 0:
                    mean = numpy.average(runtimes)
                    median = numpy.median(runtimes)
                    cv = numpy.std(runtimes) / mean
                    quantiles = mquantiles(runtimes, [0.25, 0.5, 0.75])
                    qcd = (quantiles[2] - quantiles[0]) / quantiles[1]


            results.append((sc, runs + [None] * (num_runs - len(runs)), mean, median, par10, successful, cv, qcd))
            for r in results:
                if r[2] is None or r[5] == 0: continue
                if min_mean_sc is None or r[2] < min_mean:
                    min_mean_sc, min_mean = r[0], r[2]
                if min_median_sc is None or r[3] < min_median:
                    min_median_sc, min_median = r[0], r[3]
                if min_par10_sc is None or r[4] < min_par10:
                    min_par10_sc, min_par10 = r[0], r[4]
                if min_cv_sc is None or r[6] < min_cv:
                    min_cv_sc, min_cv = r[0], r[6]
                if min_qcd_sc is None or r[7] < min_qcd:
                    min_qcd_sc, min_qcd = r[0], r[7]

        if 'csv' in request.args:
            csv_response = StringIO.StringIO()
            csv_writer = csv.writer(csv_response)
            csv_writer.writerow(['Solver'] + ['Run %d' % r for r in xrange(num_runs)] + ['Mean', 'Median', 'penalized avg. runtime', 'coeff. of variation', 'quartile coeff. of dispersion'])
            for res in results:
                csv_writer.writerow([str(res[0])] + [('' if r.get_time() is None else round(r.get_time(),4)) for r in res[1]] + map(lambda x: '' if x is None else round(x, 3), [res[2], res[3], res[4], res[6], res[7]]))
            csv_response.seek(0)

            headers = Headers()
            headers.add('Content-Type', 'text/csv')
            headers.add('Content-Disposition', 'attachment',
                        filename=(experiment.name + "_results_by_instance_%s.csv" % (str(instance),)))
            return Response(response=csv_response.read(), headers=headers)

        return render('experiment_results_by_instance.html', db=db, database=database,
                  instances=instances, experiment=experiment,
                  form=form, results=results, min_mean_sc=min_mean_sc,
                  min_median_sc=min_median_sc, min_par10_sc=min_par10_sc,
                  min_cv_sc=min_cv_sc, min_qcd_sc=min_qcd_sc,
                  num_runs=num_runs)


    return render('experiment_results_by_instance.html', db=db, database=database,
                  instances=instances, experiment=experiment,
                  form=form, results=results, num_runs=num_runs)


@frontend.route('/<database>/experiment/<int:experiment_id>/progress/')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def experiment_progress(database, experiment_id):
    """ Show a live information table of the experiment's progress """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    JS_colors = ','.join(["'%d': '%s'" % (k, v) for k, v in JOB_STATUS_COLOR.iteritems()])

    return render('experiment_progress.html', experiment=experiment,
                  database=database, db=db, JS_colors=JS_colors)

@frontend.route('/<database>/experiment/<int:experiment_id>/experiment-list-stats-ajax/')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def experiment_list_stats_ajax(database, experiment_id):
    """ Returns JSON-serialized stats about the experiment's progress
    such as number of jobs, instances, solvers, crashes, ...
    """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    num_jobs = db.session.query(db.ExperimentResult).filter_by(experiment=experiment).count()
    num_instances = experiment.get_num_instances(db)
    num_solver_configs = experiment.get_num_solver_configs(db)

    experiment_running = db.session.query(db.ExperimentResult.Experiment_idExperiment,
        func.count(db.ExperimentResult))\
                         .filter_by(status=STATUS_RUNNING)\
                         .filter_by(experiment=experiment)\
                         .filter(func.timestampdiff(sqla_text("SECOND"),
        db.ExperimentResult.startTime, func.now()) < db.ExperimentResult.CPUTimeLimit + 100)\
                         .filter(db.ExperimentResult.priority>=0).first()[1] > 0

    experiment_crashes = db.session.query(db.ExperimentResult.Experiment_idExperiment,
        func.count(db.ExperimentResult))\
                         .filter_by(experiment=experiment)\
                         .filter(db.ExperimentResult.status<=-2)\
                         .filter(db.ExperimentResult.priority>=0).first()[1] > 0

    return json_dumps({
        'num_jobs': num_jobs,
        'num_instances': num_instances,
        'num_solver_configs': num_solver_configs,
        'is_running': experiment_running,
        'has_crashed_jobs': experiment_crashes,
        })


@frontend.route('/<database>/experiment/<int:experiment_id>/experiment-stats-ajax/')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def experiment_stats_ajax(database, experiment_id):
    """ Returns JSON-serialized stats about the experiment's progress
    such as number of jobs, number of running jobs, ...
    """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    num_jobs = db.session.query(db.ExperimentResult).filter_by(experiment=experiment).count()
    num_jobs_active = db.session.query(db.ExperimentResult) \
                            .filter_by(experiment=experiment) \
                            .filter(db.ExperimentResult.priority>=0).count()
    num_jobs_not_started = db.session.query(db.ExperimentResult) \
            .filter_by(experiment=experiment, status=STATUS_NOT_STARTED) \
            .filter(db.ExperimentResult.priority>=0).count()
    num_jobs_running = db.session.query(db.ExperimentResult) \
            .filter_by(experiment=experiment, status=STATUS_RUNNING) \
            .filter(db.ExperimentResult.priority>=0).count()
    num_jobs_finished = db.session.query(db.ExperimentResult) \
            .filter_by(experiment=experiment).filter(db.ExperimentResult.status>=1) \
            .filter(db.ExperimentResult.priority>=0).count()
    num_jobs_error = db.session.query(db.ExperimentResult) \
            .filter_by(experiment=experiment).filter(db.ExperimentResult.status<=-2) \
            .filter(db.ExperimentResult.priority>=0).count()

    num_instances = experiment.get_num_instances(db)
    num_solver_configs = experiment.get_num_solver_configs(db)

    experiment_running = db.session.query(db.ExperimentResult.Experiment_idExperiment,
        func.count(db.ExperimentResult)) \
            .filter_by(status=STATUS_RUNNING) \
            .filter_by(experiment=experiment) \
            .filter(func.timestampdiff(sqla_text("SECOND"),
            db.ExperimentResult.startTime, func.now()) < db.ExperimentResult.CPUTimeLimit + 100) \
        .filter(db.ExperimentResult.priority>=0).first()[1] > 0

    experiment_crashes = db.session.query(db.ExperimentResult.Experiment_idExperiment,
        func.count(db.ExperimentResult))\
            .filter_by(experiment=experiment) \
            .filter(db.ExperimentResult.status<=-2)\
            .filter(db.ExperimentResult.priority>=0).first()[1] > 0

    avg_time = db.session.query(func.avg(db.ExperimentResult.resultTime)) \
                .filter_by(experiment=experiment) \
                .filter(db.ExperimentResult.status>=1) \
                .first()
    if avg_time is None or avg_time[0] is None: avg_time = 0.0
    else: avg_time = avg_time[0]
    
    avg_running_time = db.session.query(func.avg(func.timestampdiff(sqla_text("SECOND"),
                                        db.ExperimentResult.startTime, func.now()))) \
                .filter_by(experiment=experiment) \
                .filter(db.ExperimentResult.status==0) \
                .first()
    
    if avg_running_time[0] is not None:
        if num_jobs_finished + num_jobs_running != 0:
            avg_time = ((num_jobs_finished * avg_time) + (num_jobs_running * float(avg_running_time[0]))) / (num_jobs_finished + num_jobs_running) 
                
    if num_jobs_running != 0:
        timeleft = datetime.timedelta(seconds = int((num_jobs_not_started + num_jobs_running) * avg_time / float(num_jobs_running)))
    else:
        timeleft = datetime.timedelta(seconds = 0)

    return json_dumps({
        'num_jobs': num_jobs,
        'num_jobs_active': num_jobs_active,
        'num_jobs_not_started': num_jobs_not_started,
        'num_jobs_running': num_jobs_running,
        'num_jobs_finished': num_jobs_finished,
        'num_jobs_error': num_jobs_error,
        'num_instances': num_instances,
        'num_solver_configs': num_solver_configs,
        'is_running': experiment_running,
        'has_crashed_jobs': experiment_crashes,
        'eta': str(timeleft),
    })

@frontend.route('/<database>/experiment/<int:experiment_id>/experiment-results-csv/')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def experiment_results_csv(database, experiment_id):
    """ CSV download of all job data of an experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    result_properties = db.get_result_properties()
    instance_properties = db.get_instance_properties()

    # build the query part for result properties
    prop_columns = ','.join(["CASE WHEN `"+prop.name.replace("%", "%%")+"_value`.value IS NULL THEN 'not yet calculated' ELSE `"+
                             prop.name.replace("%", "%%")+"_value`.value END" for prop in result_properties])
    prop_joins = ""
    for prop in result_properties:
        prop_joins += """LEFT JOIN ExperimentResult_has_Property as `%s_hasP` ON
                         `%s_hasP`.idExperimentResults= idJob AND
                         `%s_hasP`.idProperty = %d
                      """ % (prop.name.replace("%", "%%"), prop.name.replace("%", "%%"), prop.name.replace("%", "%%"), prop.idProperty)
        prop_joins += """LEFT JOIN ExperimentResult_has_PropertyValue as `%s_value` ON
                        `%s_value`.idExperimentResult_has_Property = `%s_hasP`.idExperimentResult_has_Property
                      """ % (prop.name.replace("%", "%%"), prop.name.replace("%", "%%"), prop.name.replace("%", "%%"))

    # build the query part for instance properties
    inst_prop_columns = ','.join(["CASE WHEN `"+prop.name.replace("%", "%%")+"_value`.value IS NULL THEN 'not yet calculated' ELSE `"+
                             prop.name.replace("%", "%%")+"_value`.value END" for prop in instance_properties])
    inst_prop_joins = ""
    for prop in instance_properties:
        inst_prop_joins += """LEFT JOIN Instance_has_Property as `%s_value` ON
                        (`%s_value`.idInstance = Instances.idInstance
                        AND `%s_value`.idProperty = %d)
                      """ % (prop.name.replace("%", "%%"), prop.name.replace("%", "%%"), prop.name.replace("%", "%%"), prop.idProperty)

    conn = db.session.connection()
    base_query = """SELECT SQL_CALC_FOUND_ROWS ExperimentResults.idJob,
                       SolverConfig.name, Instances.name,
                       ExperimentResults.run, ExperimentResults.resultTime,
                       ExperimentResults.seed, ExperimentResults.status,
                       ExperimentResults.resultCode,
                       StatusCodes.description, ResultCodes.description,
                       CASE
                           WHEN status=0 THEN TIMESTAMPDIFF(SECOND, ExperimentResults.startTime, NOW())
                           ELSE 0
                       END as runningTime,
                       ExperimentResults.CPUTimeLimit, ExperimentResults.wallClockTimeLimit, ExperimentResults.memoryLimit,
                       ExperimentResults.stackSizeLimit,
                       ExperimentResults.computeNode, ExperimentResults.computeNodeIP, ExperimentResults.priority,
                       gridQueue.name
                       """ + (',' if prop_columns else '') + prop_columns + """
                       """ + (',' if inst_prop_columns else '') + inst_prop_columns + """
                 FROM ExperimentResults
                    LEFT JOIN ResultCodes ON ExperimentResults.resultCode=ResultCodes.resultCode
                    LEFT JOIN StatusCodes ON ExperimentResults.status=StatusCodes.statusCode
                    LEFT JOIN SolverConfig ON ExperimentResults.SolverConfig_idSolverConfig = SolverConfig.idSolverConfig
                    LEFT JOIN SolverBinaries ON SolverBinaries.idSolverBinary = SolverConfig.SolverBinaries_idSolverBinary
                    LEFT JOIN Solver ON Solver.idSolver = SolverBinaries.idSolver
                    LEFT JOIN Instances ON ExperimentResults.Instances_idInstance = Instances.idInstance
                    LEFT JOIN gridQueue ON gridQueue.idgridQueue=ExperimentResults.computeQueue
                    """+prop_joins+""" """ + inst_prop_joins + """
                 WHERE ExperimentResults.Experiment_idExperiment = %s """

    # if competition db, show only own solvers unless phase is 6 or 7
    if not is_admin() and db.is_competition() and db.competition_phase() in OWN_RESULTS:
        res = conn.execute(base_query + """ AND Solver.User_idUser = %s """ , (experiment_id, g.User.idUser))
        jobs = res.fetchall()
    else:
        res = conn.execute(base_query , (experiment_id, ))
        jobs = res.fetchall()

    csv_response = StringIO.StringIO()
    csv_writer = csv.writer(csv_response)
    csv_writer.writerow(['id', 'Solver', 'Instance', 'Run', 'Time', 'Seed', 'status code', 'result code', 'Status'] +
                        ['Result', 'running time', 'CPUTimeLimit', 'wallClockTimeLimit', 'memoryLimit'] +
                        ['stackSizeLimit', 'computeNode', 'computeNodeIP',
                         'priority', 'computeQueue ID'] +
                        [p.name for p in result_properties] + [p.name for p in instance_properties])
    csv_writer.writerows(jobs)
    csv_response.seek(0)
    headers = Headers()
    headers.add('Content-Type', 'text/csv')
    headers.add('Content-Disposition', 'attachment', filename=secure_filename(experiment.name) + "_data.csv")
    return Response(response=csv_response.read(), headers=headers)

@frontend.route('/<database>/experiment/<int:experiment_id>/progress-ajax/')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def experiment_progress_ajax(database, experiment_id):
    """ Returns JSON-serialized data of the experiment results.
        Used by the jQuery datatable as ajax data source with server side processing.
        Parses the GET parameters and constructs an appropriate SQL query to fetch
        the data.
    """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    if not request.args.has_key('csv') and not request.args.has_key('iDisplayStart'):
        # catch malformed datatable updates (jquery datatables sends 2 requests for some reason per refresh)
        return json_dumps({'aaData': []})

    result_properties = db.get_result_properties()
    #instance_properties = db.get_instance_properties()

    # list of columns of the SQL query
    # dummy column ("") in the middle for correct indexing in the ORDER part since
    # that column is hidden in the jquery table
    columns = ["ExperimentResults.idJob", "SolverConfig.name", "Instances.name",
               "ExperimentResults.run", "ExperimentResults.resultTime", "ExperimentResults.seed",
               "StatusCodes.description",
               "runningTime",
               "ResultCodes.description", "ExperimentResults.status",
               "ExperimentResults.CPUTimeLimit", "ExperimentResults.wallClockTimeLimit",
               "ExperimentResults.memoryLimit", "ExperimentResults.stackSizeLimit",
               "ExperimentResults.computeNode", "ExperimentResults.computeNodeIP",
               "ExperimentResults.priority", "gridQueue.name"] + \
              ["`"+prop.name.replace("%", "%%")+"_value`.value" for prop in result_properties]
    #["`"+iprop.name.replace("%", "%%")+"_value`.value" for iprop in instance_properties]

    # build the query part for the result properties that should be included
    prop_columns = ','.join(["CASE WHEN `"+prop.name.replace("%", "%%")+"_value`.value IS NULL THEN 'not yet calculated' ELSE `"+
                             prop.name.replace("%", "%%")+"_value`.value END" for prop in result_properties])
    prop_joins = ""
    for prop in result_properties:
        prop_joins += """LEFT JOIN ExperimentResult_has_Property as `%s_hasP` ON
                         `%s_hasP`.idExperimentResults= idJob AND
                         `%s_hasP`.idProperty = %d
                      """ % (prop.name.replace("%", "%%"), prop.name.replace("%", "%%"), prop.name.replace("%", "%%"), prop.idProperty)
        prop_joins += """LEFT JOIN ExperimentResult_has_PropertyValue as `%s_value` ON
                        `%s_value`.idExperimentResult_has_Property = `%s_hasP`.idExperimentResult_has_Property
                      """ % (prop.name.replace("%", "%%"), prop.name.replace("%", "%%"), prop.name.replace("%", "%%"))

    # build the query part for the instance properties that should be included
    #inst_prop_columns = ','.join(["CASE WHEN `"+prop.name+"_value`.value IS NULL THEN 'not yet calculated' ELSE `"+
    #                         prop.name+"_value`.value END" for prop in instance_properties])
    #inst_prop_joins = ""
    #for prop in instance_properties:
    #    inst_prop_joins += """LEFT JOIN Instance_has_Property as `%s_value` ON
    #                    (`%s_value`.idInstance = Instances.idInstance
    #                    AND `%s_value`.idProperty = %d)
    #                  """ % (prop.name, prop.name, prop.name, prop.idProperty)

    params = []
    where_clause = ""
    if request.args.has_key('sSearch') and request.args.get('sSearch') != '':
        where_clause += "(ExperimentResults.idJob LIKE %s OR "
        where_clause += "Instances.name LIKE %s OR "
        where_clause += "SolverConfig.name LIKE %s OR "
        where_clause += "ResultCodes.description LIKE %s OR "
        where_clause += "StatusCodes.description LIKE %s OR "
        where_clause += "ExperimentResults.run LIKE %s OR "
        where_clause += "ExperimentResults.resultTime LIKE %s OR "
        where_clause += "ExperimentResults.seed LIKE %s OR "
        where_clause += "ExperimentResults.computeNode LIKE %s OR "
        where_clause += "ExperimentResults.computeNodeIP LIKE %s OR "
        where_clause += "gridQueue.name LIKE %s OR "
        where_clause += "SolverConfig.name LIKE %s ) """
        params += ['%' + request.args.get('sSearch') + '%'] * 12 # 12 conditions

    if where_clause != "": where_clause += " AND "
    where_clause += "ExperimentResults.Experiment_idExperiment = %s "
    params.append(experiment.idExperiment)

    # if competition db, show only own solvers unless phase is 6 or 7
    if not is_admin() and db.is_competition() and db.competition_phase() in OWN_RESULTS:
        where_clause += " AND Solver.User_idUser = %s "
        params.append(g.User.idUser)

    order = ""
    if request.args.get('iSortCol_0', '') != '' and int(request.args.get('iSortingCols', 0)) > 0:
        order = "ORDER BY "
        for i in xrange(int(request.args.get('iSortingCols', 0))):
            order += columns[int(request.args.get('iSortCol_' + str(i)))] + " "
            direction = request.args.get('sSortDir_' + str(i))
            if direction in ('asc', 'desc'):
                order += direction + ", "
        order = order[:-2]
    print order
    limit = ""
    if request.args.get('iDisplayStart', '') != '' and int(request.args.get('iDisplayLength', -1)) != -1:
        limit = "LIMIT %s, %s"
        params.append(int(request.args.get('iDisplayStart')))
        params.append(int(request.args.get('iDisplayLength')))

    conn = db.session.connection()
    res = conn.execute("""SELECT SQL_CALC_FOUND_ROWS ExperimentResults.idJob,
                       SolverConfig.name, Instances.name,
                       ExperimentResults.run, ExperimentResults.resultTime,
                       ExperimentResults.seed,
                       StatusCodes.description,
                       CASE
                           WHEN status=0 THEN TIMESTAMPDIFF(SECOND, ExperimentResults.startTime, NOW())
                           ELSE 0
                       END as runningTime,
                       ResultCodes.description, ExperimentResults.status,
                       ExperimentResults.CPUTimeLimit, ExperimentResults.wallClockTimeLimit, ExperimentResults.memoryLimit,
                       ExperimentResults.stackSizeLimit,
                       ExperimentResults.computeNode, ExperimentResults.computeNodeIP, ExperimentResults.priority,
                       gridQueue.name
                       """ + (',' if prop_columns else '') + prop_columns + """
                 FROM ExperimentResults
                    LEFT JOIN ResultCodes ON ExperimentResults.resultCode=ResultCodes.resultCode
                    LEFT JOIN StatusCodes ON ExperimentResults.status=StatusCodes.statusCode
                    LEFT JOIN SolverConfig ON ExperimentResults.SolverConfig_idSolverConfig = SolverConfig.idSolverConfig
                    LEFT JOIN SolverBinaries ON SolverBinaries.idSolverBinary = SolverConfig.SolverBinaries_idSolverBinary
                    LEFT JOIN Solver ON Solver.idSolver = SolverBinaries.idSolver
                    LEFT JOIN Instances ON ExperimentResults.Instances_idInstance = Instances.idInstance
                    LEFT JOIN gridQueue ON gridQueue.idgridQueue=ExperimentResults.computeQueue
                    """+prop_joins+"""
                 WHERE """ + where_clause + " " + order + " " + limit, tuple(params))

    jobs = res.fetchall()

    res = conn.execute("SELECT FOUND_ROWS()")
    numFiltered = res.fetchone()[0]
    res = conn.execute("""SELECT COUNT(ExperimentResults.idJob)
                       FROM ExperimentResults WHERE Experiment_idExperiment = %s""",
                       experiment.idExperiment)
    numTotal = res.fetchone()[0]

    aaData = []
    for job in jobs:
        if job.status == 0: # status == running
            running = job.runningTime
        else:
            running = "not running"

        aaData.append([job.idJob, job[1], job[2], job[3],
                job[4], job[5], job[6], running, job[8], job[9], \
                job[10], job[11], job[12], job[13], job[14], job[15], job[16], job[17] ] \
                + [job[i] for i in xrange(18, 18+len(result_properties))]
                #+ [job[i] for i in xrange(20+len(result_properties), 19+len(result_properties)+len(instance_properties))]
            )

    if request.args.has_key('csv'):
        csv_response = StringIO.StringIO()
        csv_writer = csv.writer(csv_response)
        csv_writer.writerow(['id', 'Solver', 'Instance', 'Run', 'Time', 'Seed', 'status code', 'Status'] +
                            ['Result', 'running time', 'CPUTimeLimit', 'wallClockTimeLimit', 'memoryLimit'] +
                            ['stackSizeLimit', 'computeNode', 'computeNodeIP', 'priority', 'computeQueue ID'] +
                            [p.name for p in result_properties]) # +  [p.name for p in instance_properties])
        for d in aaData:
            csv_writer.writerow(d)
        csv_response.seek(0)
        headers = Headers()
        headers.add('Content-Type', 'text/csv')
        headers.add('Content-Disposition', 'attachment', filename=secure_filename(experiment.name) + "_data.csv")
        return Response(response=csv_response.read(), headers=headers)

    return json_dumps({
        'aaData': aaData,
        'sEcho': request.args.get('sEcho'),
        'iTotalRecords': str(numTotal),
        'iTotalDisplayRecords': str(numFiltered),
    })

@frontend.route('/<database>/experiment/<int:experiment_id>/result/<int:solver_configuration_id>/<int:instance_id>')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def solver_config_results(database, experiment_id, solver_configuration_id, instance_id):
    """ Displays list of results (all jobs) of a solver configuration on an instance """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    solver_configuration = db.session.query(db.SolverConfiguration).get(solver_configuration_id) or abort(404)
    instance = db.session.query(db.Instance).filter_by(idInstance=instance_id).first() or abort(404)
    if solver_configuration not in experiment.solver_configurations: abort(404)
    if instance not in experiment.instances: abort(404)

    if not is_admin() and db.is_competition() and db.competition_phase() in OWN_RESULTS:
        if not solver_configuration.solver_binary.solver.user == g.User: abort(401)

    jobs = db.session.query(db.ExperimentResult) \
                    .filter_by(experiment=experiment) \
                    .filter_by(solver_configuration=solver_configuration) \
                    .filter_by(instance=instance) \
                    .all()

    completed = len(filter(lambda j: j.status not in STATUS_PROCESSING, jobs))
    correct = len(filter(lambda j: j.status == STATUS_FINISHED and str(j.resultCode).startswith('1'), jobs))

    return render('solver_config_results.html', experiment=experiment,
                  solver_configuration=solver_configuration, instance=instance,
                  correct=correct, results=jobs, completed=completed,
                  database=database, db=db)


@frontend.route('/<database>/instance/<int:instance_id>')
@require_login
def instance_details(database, instance_id):
    """ Show instance details """
    db = models.get_database(database) or abort(404)
    instance = db.session.query(db.Instance).filter_by(idInstance=instance_id).first() or abort(404)

    if db.is_competition() and db.competition_phase() not in INSTANCE_DETAILS and not is_admin():
        abort(403)

    instance_blob = instance.get_instance(db)
    if len(instance_blob) > 1024:
        # show only the first and last 512 characters if the instance is larger than 1kB
        instance_text = instance_blob[:512] + "\n\n... [truncated " + \
                         utils.download_size(len(instance_blob) - 1024) + \
                        "]\n\n" + instance_blob[-512:]
    else:
        instance_text = instance_blob

    instance_properties = db.get_instance_properties()

    return render('instance_details.html', instance=instance,
                  instance_text=instance_text, blob_size=len(instance_blob),
                  database=database, db=db,
                  instance_properties=instance_properties)


@frontend.route('/<database>/instance/<int:instance_id>/download')
@require_login
def instance_download(database, instance_id):
    """ Return HTTP-Response containing the instance blob """
    db = models.get_database(database) or abort(404)
    instance = db.session.query(db.Instance).filter_by(idInstance=instance_id).first() or abort(404)

    if db.is_competition() and db.competition_phase() not in INSTANCE_DETAILS and not is_admin():
        abort(403)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename=instance.name)

    return Response(response=instance.get_instance(db), headers=headers)


@frontend.route('/<database>/experiment/<int:experiment_id>/solver-configurations/<int:solver_configuration_id>')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def solver_configuration_details(database, experiment_id, solver_configuration_id):
    """ Show solver configuration details """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id)
    solver_config = db.session.query(db.SolverConfiguration).get(solver_configuration_id) or abort(404)
    solver = solver_config.solver_binary.solver

    if not is_admin() and db.is_competition() and db.competition_phase() in OWN_RESULTS:
        if solver.user != g.User: abort(401)

    parameters = solver_config.parameter_instances
    parameters.sort(key=lambda p: p.parameter.order)

    return render('solver_configuration_details.html', solver_config=solver_config,
                  solver=solver, parameters=parameters, database=database, db=db,
                  experiment=experiment)


@frontend.route('/<database>/solver/<int:solver_id>')
@require_competition
@require_login
def solver_details(database, solver_id):
    db = models.get_database(database) or abort(404)
    solver = db.session.query(db.Solver).get(solver_id) or abort(404)
    categories = map(str, solver.competition_categories)

    if not is_admin() and solver.user != g.User: abort(401)

    return render('solver_details.html', database=database, db=db, solver=solver, categories=categories)

@frontend.route('/<database>/solver-binary-download/<int:solver_binary_id>')
@require_competition
@require_login
def solver_binary_download(database, solver_binary_id):
    db = models.get_database(database) or abort(404)
    solver_binary = db.session.query(db.SolverBinary).get(solver_binary_id) or abort(404)

    if not is_admin() and solver_binary.solver.user != g.User: abort(401)

    headers = Headers()
    headers.add('Content-Type', 'application/zip')
    headers.add('Content-Disposition', 'attachment', filename=secure_filename(solver_binary.binaryName + '.zip'))

    return Response(response=solver_binary.binaryArchive, headers=headers)

@frontend.route('/<database>/solver-code-download/<int:solver_id>')
@require_competition
@require_login
def solver_code_download(database, solver_id):
    db = models.get_database(database) or abort(404)
    solver = db.session.query(db.Solver).get(solver_id) or abort(404)

    if not is_admin() and solver.user != g.User: abort(401)

    headers = Headers()
    headers.add('Content-Type', 'application/zip')
    headers.add('Content-Disposition', 'attachment', filename=secure_filename(solver.name + '_code.zip'))

    return Response(response=solver.code, headers=headers)

@frontend.route('/<database>/solver-description-download/<int:solver_id>')
@require_competition
@require_login
def solver_description_download(database, solver_id):
    db = models.get_database(database) or abort(404)
    solver = db.session.query(db.Solver).get(solver_id) or abort(404)

    if not is_admin() and solver.user != g.User: abort(401)

    headers = Headers()
    headers.add('Content-Type', 'application/pdf')
    headers.add('Content-Disposition', 'attachment', filename=secure_filename(solver.name + '_description.pdf'))

    return Response(response=solver.description_pdf, headers=headers)


@frontend.route('/<database>/experiment/<int:experiment_id>/result/')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def experiment_result(database, experiment_id):
    """ Displays information about a single result (job) """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    result = db.session.query(db.ExperimentResult).get(request.args.get('id', 0)) or abort(404)

    if not is_admin() and db.is_competition() and db.competition_phase() in OWN_RESULTS:
        if result.solver_configuration.solver_binary.solver.user != g.User: abort(401)

    solverOutput = result.output.solverOutput
    launcherOutput = result.output.launcherOutput
    watcherOutput = result.output.watcherOutput
    verifierOutput = result.output.verifierOutput

    solverOutput_text = utils.formatOutputFile(solverOutput)
    launcherOutput_text = utils.formatOutputFile(launcherOutput)
    watcherOutput_text = utils.formatOutputFile(watcherOutput)
    verifierOutput_text = utils.formatOutputFile(verifierOutput)

    return render('result_details.html', experiment=experiment, result=result, solver=result.solver_configuration,
                  solver_config=result.solver_configuration, instance=result.instance, solverOutput_text=solverOutput_text,
                  launcherOutput_text=launcherOutput_text, watcherOutput_text=watcherOutput_text,
                  verifierOutput_text=verifierOutput_text, database=database, db=db)


@frontend.route('/<database>/experiment/<int:experiment_id>/unsolved-instances/')
@require_phase(phases=[5,6,7])
@require_login
def unsolved_instances(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    unsolved_instances = experiment.get_unsolved_instances(db)

    return render('unsolved_instances.html', database=database, db=db, experiment=experiment,
                  unsolved_instances=unsolved_instances, instance_properties=db.get_instance_properties())

@frontend.route('/<database>/experiment/<int:experiment_id>/solved-instances/')
@require_phase(phases=[5,6,7])
@require_login
def solved_instances(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    solved_instances = experiment.get_solved_instances(db)

    return render('solved_instances.html', database=database, db=db, experiment=experiment,
                  solved_instances=solved_instances, instance_properties=db.get_instance_properties())


@frontend.route('/<database>/experiment/<int:experiment_id>/result/<int:result_id>/download-solver-output')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def solver_output_download(database, experiment_id, result_id):
    """ Returns the specified job client output file as HTTP response """
    db = models.get_database(database) or abort(404)
    result = db.session.query(db.ExperimentResult).get(result_id) or abort(404)

    if not is_admin() and db.is_competition() and db.competition_phase() in OWN_RESULTS:
        if result.solver_configuration.solver_binary.solver.user != g.User: abort(401)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename="result.txt")

    return Response(response=result.output.solverOutput, headers=headers)


@frontend.route('/<database>/experiment/<int:experiment_id>/result/<int:result_id>/download-launcher-output')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def launcher_output_download(database, experiment_id, result_id):
    """ Returns the specified job client output file as HTTP response """
    db = models.get_database(database) or abort(404)
    result = db.session.query(db.ExperimentResult).get(result_id) or abort(404)

    if not is_admin() and db.is_competition() and db.competition_phase() in OWN_RESULTS:
        if result.solver_configuration.solver_binary.solver.user != g.User: abort(401)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename="result.txt")

    return Response(response=result.output.launcherOutput, headers=headers)


@frontend.route('/<database>/experiment/<int:experiment_id>/result/<int:result_id>/download-watcher-output')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def watcher_output_download(database, experiment_id, result_id):
    """ Returns the specified job client output file as HTTP response """
    db = models.get_database(database) or abort(404)
    result = db.session.query(db.ExperimentResult).get(result_id) or abort(404)

    if not is_admin() and db.is_competition() and db.competition_phase() in OWN_RESULTS:
        if result.solver_configuration.solver_binary.solver.user != g.User: abort(401)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename="result.txt")

    return Response(response=result.output.watcherOutput, headers=headers)


@frontend.route('/<database>/experiment/<int:experiment_id>/result/<int:result_id>/download-verifier-output')
@require_phase(phases=OWN_RESULTS.union(ALL_RESULTS))
@require_login
def verifier_output_download(database, experiment_id, result_id):
    """ Returns the specified job client output file as HTTP response """
    db = models.get_database(database) or abort(404)
    result = db.session.query(db.ExperimentResult).get(result_id) or abort(404)

    if not is_admin() and db.is_competition() and db.competition_phase() in OWN_RESULTS:
        if result.solver_configuration.solver_binary.solver.user != g.User: abort(401)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename="result.txt")

    return Response(response=result.output.verifierOutput, headers=headers)

@frontend.route('/<database>/power/')
def power(database):
    """ Reports the estimated power consumption and cost of the jobs that were run
        in the database on a computer cluster in Germany."""
    db = models.get_database(database) or abort(404)

    total_time = db.session.query(func.sum(db.ExperimentResult.resultTime)).first()[0]
    power_consumed = 30.0 * total_time / 60.0 / 60.0 / 1000.0 # in kWh
    cost = 0.2 * power_consumed # in Euro

    return render('power.html', database=database, db=db, total_time=total_time,
                                power_consumed=power_consumed, cost=cost)

@frontend.route('/<database>/monitor')
def choose_monitor_mode(database):
    db = models.get_database(database) or abort(404)
    return render('choose_monitor_mode.html', database=database, db = db)

@frontend.route('/<database>/monitor/clients', methods = ['GET', 'POST'])
def client_mode(database):
    db = models.get_database(database) or abort(404)
    form = forms.ClientForm()
    form.experiments.query = db.session.query(db.Experiment).join(db.Experiment_has_Client) or EmptyQuery()
    expID = []
    if form.experiments.data:
        url_param = "&".join(['e=' + str(exp.idExperiment) for exp in form.experiments.data])
        for eID in form.experiments.data:
            expID.append(eID.idExperiment)        
        m = clientMonitor.ClientMonitor(database, expID)
        coordinates = m.getImageMap()
        return render('client_mode.html', database = database, db = db, form = form, url_param = url_param, coordinates = coordinates)
    for exp in form.experiments.query:
        expID.append(str(exp.idExperiment))
    m = clientMonitor.ClientMonitor(database, expID)
    coordinates = m.getImageMap()
    return render('client_mode.html', database = database, db = db, form = form, coordinates = coordinates)

@frontend.route('/<database>/client_pic')
def show_clientMonitor(database):  
    db = models.get_database(database) or abort(404)
    expID = map(int, request.args.getlist('e')) 
    if (len(expID) == 0):
        #TODO: kann ich dass auch ohne db abfragen?
        for exp in db.session.query(db.Experiment).join(db.Experiment_has_Client):
            expID.append(str(exp.idExperiment))
    m = clientMonitor.ClientMonitor(database, expID)
    m.save(file = os.path.join(config.TEMP_DIR, g.unique_id) + ".png")
    im = Image.open(os.path.join(config.TEMP_DIR, g.unique_id) + ".png")
    f = StringIO.StringIO()
    im.save(f, "PNG")
    return f.getvalue()

@frontend.route('/<database>/monitor/nodes', methods = ['GET', 'POST'])
def monitor_formular(database):
    form = forms.MonitorForm()
    db = models.get_database(database) or abort(404)
    form.experiments.query = db.session.query(db.Experiment).all() or EmptyQuery()
    form.status.query = db.session.query(db.StatusCodes) or EmptyQuery()
    if form.experiments.data:
        exp_param = "&".join(['e=' + str(exp.idExperiment) for exp in form.experiments.data])
        if request.form.get("submit") == "problem mode": stat_param = 's=pm' 
        else:
            stat_param = "&".join(['s=' + str(stat.statusCode) for stat in form.status.data])
        url_param = "&".join((exp_param, stat_param))
        status = []
        for st in form.status.data:
            status.append(st.statusCode)
        expID = []
        for eID in form.experiments.data:
            expID.append(eID.idExperiment)        
        m = monitor.Monitor(database, status, expID)
        coordinates = m.getImageMap()
        tableview = False
        if request.form.get("submit") == "table view":
            tableview = True
        refresh = False
        if request.form.get("submit") == "refresh":
            refresh = True

        return render('node_mode.html', database = database, db = db, form = form, url_param = url_param, coordinates = coordinates, tableview=tableview, refresh=refresh)
    return render('node_mode.html', database = database, db = db, form = form)

@frontend.route('/<database>/monitor_pic')
def show_monitor(database):  
    status = map(str, request.args.getlist('s'))
    expID = map(int, request.args.getlist('e')) 
    m = monitor.Monitor(database, status, expID)
    m.save(file = os.path.join(config.TEMP_DIR, g.unique_id) + ".png")
    im = Image.open(os.path.join(config.TEMP_DIR, g.unique_id) + ".png")
    f = StringIO.StringIO()
    im.save(f, "PNG")
    return f.getvalue()

@frontend.route('/<database>/monitor_tabelle')
def ajax_monitor_tabelle(database):
    status = map(str, request.args.getlist('amp;s'))
    expID = map(int, request.args.getlist('e'))
    expID2 = map(int, request.args.getlist('amp;e'))
    for eID in expID2:
        expID.append(eID)
    m = monitor.Monitor(database, status, expID)    
    table = m.getTable()
    return json_dumps(table)

@frontend.route('/<database>/experiment/<int:experiment_id>/configurator_visualisation', methods = ['GET', 'POST'])
@require_login
def configurator_visualisation(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    standardize = 0
    if request.method == 'POST' and request.form.get("submit") != "reset":
        if (request.form.get("submit")== "standardized data"):
            standardize = 1
        elif (request.form.get("submit")== "original data"):
            standardize = 0
        else:
            standardize = map(int, request.form.get("standardize"))[0]
        cv = config_visualisation.config_vis(database, experiment_id, request.form, standardize)
        configuration = cv.getConfiguration()
    else:
        cv = config_visualisation.config_vis(database, experiment_id, None, standardize)
        configuration = cv.getConfiguration()

    render_res = render('configurator_visualisation.html', experiment=experiment, database=database, db=db, configuration = configuration)
    return render_res
 
        
