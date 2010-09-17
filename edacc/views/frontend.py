# -*- coding: utf-8 -*-
"""
    edacc.views.frontend
    --------------------

    This module defines request handler functions for the main functionality
    of the web application.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

import json
import csv
import StringIO
import numpy

from flask import Module
from flask import render_template
from flask import Response, abort, g, request
from werkzeug import Headers

from edacc import utils, models
from sqlalchemy.orm import joinedload
from edacc.constants import JOB_FINISHED, JOB_ERROR
from edacc.views.helpers import require_phase, require_competition
from edacc.views.helpers import require_login, is_admin
from edacc import forms

frontend = Module(__name__)


def render(*args, **kwargs):
    from tidylib import tidy_document
    res = render_template(*args, **kwargs)
    doc, errs = tidy_document(res)
    return doc


@frontend.route('/')
def index():
    """ Show a list of all served databases """
    databases = list(models.get_databases().itervalues())
    databases.sort(key=lambda db: db.database.lower())

    return render('/databases.html', databases=databases)

@frontend.route('/<database>/index')
@frontend.route('/<database>/experiments/')
@require_phase(phases=(2, 3, 4, 5, 6, 7))
def experiments_index(database):
    """ Show a list of all experiments in the database """
    db = models.get_database(database) or abort(404)

    if db.is_competition() and db.competition_phase() not in (3, 4, 5, 6, 7):
        # Experiments are only visible in phases 3 through 7 in a competition database
        experiments = []
    else:
        experiments = db.session.query(db.Experiment).all()
        experiments.sort(key=lambda e: e.name.lower())

    return render('experiments.html', experiments=experiments, db=db, database=database)


@frontend.route('/<database>/categories')
@require_competition
def categories(database):
    return 'categories'


@frontend.route('/<database>/overview/')
@require_competition
def competition_overview(database):
    db = models.get_database(database) or abort(404)

    try:
        return render('/competitions/%s/overview.html' % (database,), db=db, database=database)
    except:
        abort(404)


@frontend.route('/<database>/schedule/')
@require_competition
def competition_schedule(database):
    db = models.get_database(database) or abort(404)

    try:
        return render('/competitions/%s/schedule.html' % (database,), db=db, database=database)
    except:
        abort(404)


@frontend.route('/<database>/rules/')
@require_competition
def competition_rules(database):
    db = models.get_database(database) or abort(404)

    try:
        return render('/competitions/%s/rules.html' % (database,), db=db, database=database)
    except:
        abort(404)


@frontend.route('/<database>/experiment/<int:experiment_id>/')
@require_phase(phases=(3, 4, 5, 6, 7))
@require_login
def experiment(database, experiment_id):
    """ Show menu with links to info and evaluation pages """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    return render('experiment.html', experiment=experiment, database=database, db=db)


@frontend.route('/<database>/experiment/<int:experiment_id>/solvers')
@require_phase(phases=(3, 4, 5, 6, 7))
@require_login
def experiment_solvers(database, experiment_id):
    """ Show a list of all solvers used in the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    # remove duplicates introduced by a solver being used with more than one configuration
    solvers = list(set(sc.solver for sc in experiment.solver_configurations))
    solvers.sort(key=lambda s: s.name)

    # if competition db, show only own solvers unless phase is 6 or 7
    if not is_admin() and db.is_competition() and not db.competition_phase() in (6, 7):
        solvers = filter(lambda s: s.user == g.User, solvers)

    return render('experiment_solvers.html', solvers=solvers, experiment=experiment, database=database, db=db)


@frontend.route('/<database>/experiment/<int:experiment_id>/solver-configurations')
@require_phase(phases=(3, 4, 5, 6, 7))
@require_login
def experiment_solver_configurations(database, experiment_id):
    """ List all solver configurations (solver + parameter set) used in the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    solver_configurations = experiment.solver_configurations
    solver_configurations.sort(key=lambda sc: sc.solver.name.lower())

    # if competition db, show only own solvers unless phase is 6 or 7
    if not is_admin() and db.is_competition() and not db.competition_phase() in (6, 7):
        solver_configurations = filter(lambda sc: sc.solver.user == g.User, solver_configurations)

    return render('experiment_solver_configurations.html', experiment=experiment, solver_configurations=solver_configurations, database=database, db=db)


@frontend.route('/<database>/experiment/<int:experiment_id>/instances')
@require_phase(phases=(3, 4, 5, 6, 7))
@require_login
def experiment_instances(database, experiment_id):
    """ Show information about all instances used in the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    instances = experiment.instances
    instances.sort(key=lambda i: i.name)

    return render('experiment_instances.html', instances=instances, experiment=experiment, database=database, db=db)


@frontend.route('/<database>/experiment/<int:experiment_id>/results/')
@require_phase(phases=(3, 4, 5, 6, 7))
@require_login
def experiment_results(database, experiment_id):
    """ Show a table with the solver configurations and their results on the instances of the experiment """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    instances = experiment.instances
    solver_configs = experiment.solver_configurations

    # if competition db, show only own solvers unless phase is 6 or 7
    if not is_admin() and db.is_competition() and db.competition_phase() not in (6, 7):
        solver_configs = filter(lambda sc: sc.solver.user == g.User, solver_configs)

    results = []
    for instance in instances:
        row = []
        for solver_config in solver_configs:
            query = db.session.query(db.ExperimentResult)
            query.enable_eagerloads(True).options(joinedload(db.ExperimentResult.instance, db.ExperimentResult.solver_configuration))
            jobs = query.filter_by(experiment=experiment) \
                        .filter_by(solver_configuration=solver_config) \
                        .filter_by(instance=instance) \
                        .all()
            completed = len(filter(lambda j: j.status in JOB_FINISHED or j.status in JOB_ERROR, jobs))
            runtimes = [j.time for j in jobs]
            time_max = max(runtimes)
            time_min = min(runtimes)
            row.append({'time_avg': numpy.average(runtimes),
                        'time_median': numpy.median(runtimes),
                        'time_max': time_max,
                        'time_min': time_min,
                        'time_stddev': numpy.std(runtimes),
                        'var_coeff': numpy.std(runtimes) / numpy.average(runtimes),
                        'completed': completed,
                        'total': len(jobs),
                        'solver_config': solver_config
                        })
        results.append({'instance': instance, 'times': row})

    return render('experiment_results.html', experiment=experiment,
                    instances=instances, solver_configs=solver_configs,
                    results=results, database=database, db=db)


@frontend.route('/<database>/experiment/<int:experiment_id>/results-by-solver/')
@require_phase(phases=(3, 4, 5, 6, 7))
@require_login
def experiment_results_by_solver(database, experiment_id):
    """ Show the results of the experiment by solver configuration """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    solver_configs = experiment.solver_configurations

    if not is_admin() and db.is_competition() and db.competition_phase() not in (6, 7):
        solver_configs = filter(lambda sc: sc.solver.user == g.User, solver_configs)

    form = forms.ResultBySolverForm(request.args)
    form.solver_config.query = solver_configs

    results = []
    if form.solver_config.data:
        solver_config = form.solver_config.data
        instances = experiment.instances
        for i in instances:
            runs = db.session.query(db.ExperimentResult).filter_by(experiment=experiment, solver_configuration=solver_config).filter_by(instance=i).all()
            results.append((i, runs))

        if 'csv' in request.args:
            csv_response = StringIO.StringIO()
            csv_writer = csv.writer(csv_response)
            csv_writer.writerow(['Instance', 'Runs'])
            for res in results:
                csv_writer.writerow([res[0].name] + [r.time for r in res[1]])
            csv_response.seek(0)

            headers = Headers()
            headers.add('Content-Type', 'text/csv')
            headers.add('Content-Disposition', 'attachment', filename=("results_%s.csv" % (str(solver_config),)))
            return Response(response=csv_response.read(), headers=headers)

    return render('experiment_results_by_solver.html', db=db, database=database,
                  solver_configs=solver_configs, experiment=experiment,
                  form=form, results=results)


@frontend.route('/<database>/experiment/<int:experiment_id>/results-by-instance')
@require_phase(phases=(3, 4, 5, 6, 7))
@require_login
def experiment_results_by_instance(database, experiment_id):
    """ Show the results of the experiment by instance """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    instances = experiment.instances
    solver_configs = experiment.solver_configurations

    if not is_admin() and db.is_competition() and db.competition_phase() not in (6, 7):
        solver_configs = filter(lambda sc: sc.solver.user == g.User, solver_configs)

    form = forms.ResultByInstanceForm(request.args)
    form.instance.query = instances

    results = []
    if form.instance.data:
        instance = form.instance.data
        for sc in solver_configs:
            runs = db.session.query(db.ExperimentResult) \
                        .filter_by(experiment=experiment,
                                   instance=instance,
                                   solver_configuration=sc).all()
            results.append((sc, runs))

        if 'csv' in request.args:
            csv_response = StringIO.StringIO()
            csv_writer = csv.writer(csv_response)
            csv_writer.writerow(['Solver', 'Runs'])
            for res in results:
                csv_writer.writerow([str(res[0])] + [r.time for r in res[1]])
            csv_response.seek(0)

            headers = Headers()
            headers.add('Content-Type', 'text/csv')
            headers.add('Content-Disposition', 'attachment', filename=("results_%s.csv" % (str(instance),)))
            return Response(response=csv_response.read(), headers=headers)


    return render('experiment_results_by_instance.html', db=db, database=database,
                  instances=instances, experiment=experiment,
                  form=form, results=results)


@frontend.route('/<database>/experiment/<int:experiment_id>/progress/')
@require_phase(phases=(3, 4, 5, 6, 7))
@require_login
def experiment_progress(database, experiment_id):
    """ Show a live information table of the experiment's progress """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    return render('experiment_progress.html', experiment=experiment, database=database, db=db)


@frontend.route('/<database>/experiment/<int:experiment_id>/progress-ajax')
@require_phase(phases=(3, 4, 5, 6, 7))
@require_login
def experiment_progress_ajax(database, experiment_id):
    """ Returns JSON-serialized data of the experiment results. Used by the jQuery datatable as ajax data source """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    query = db.session.query(db.ExperimentResult).enable_eagerloads(True).options(joinedload(db.ExperimentResult.instance))
    query.options(joinedload(db.ExperimentResult.solver_configuration))

    import time
    start = time.clock()
    jobs = query.filter_by(experiment=experiment).all()
    print "db: ", time.clock() - start, 's'
    # if competition db, show only own solvers unless phase is 6 or 7
    if not is_admin() and db.is_competition() and db.competition_phase() not in (6, 7):
        jobs = filter(lambda j: j.solver_configuration.solver.user == g.User, jobs)

    start = time.clock()
    aaData = []
    for job in jobs:
        iname = job.instance.name
        if len(iname) > 30: iname = iname[0:30] + '...'
        aaData.append([job.idJob, job.solver_configuration.get_name(), utils.parameter_string(job.solver_configuration),
               iname, job.run, job.time, job.seed, utils.job_status(job.status)])
    print "conversion: ", time.clock() - start, 's'

    start = time.clock()
    dump = json.dumps({'aaData': aaData})
    print "json: ", time.clock() - start, 's'
    return dump


@frontend.route('/<database>/experiment/<int:experiment_id>/result/<int:solver_configuration_id>/<int:instance_id>')
@require_phase(phases=(3, 4, 5, 6, 7))
@require_login
def solver_config_results(database, experiment_id, solver_configuration_id, instance_id):
    """ Displays list of results (all jobs) of a solver configuration on an instance """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    solver_configuration = db.session.query(db.SolverConfiguration).get(solver_configuration_id) or abort(404)
    instance = db.session.query(db.Instance).filter_by(idInstance=instance_id).first() or abort(404)
    if solver_configuration not in experiment.solver_configurations: abort(404)
    if instance not in experiment.instances: abort(404)

    if not is_admin() and db.is_competition() and not db.competition_phase() in (6, 7):
        if not solver_configuration.solver.user == g.User: abort(401)

    jobs = db.session.query(db.ExperimentResult) \
                    .filter_by(experiment=experiment) \
                    .filter_by(solver_configuration=solver_configuration) \
                    .filter_by(instance=instance) \
                    .all()

    completed = len(filter(lambda j: j.status in JOB_FINISHED or j.status in JOB_ERROR, jobs))

    return render('solver_config_results.html', experiment=experiment, solver_configuration=solver_configuration,
                  instance=instance, results=jobs, completed=completed, database=database, db=db)


@frontend.route('/<database>/instance/<int:instance_id>')
@require_phase(phases=(6, 7))
@require_login
def instance_details(database, instance_id):
    """ Show instance details """
    db = models.get_database(database) or abort(404)
    instance = db.session.query(db.Instance).filter_by(idInstance=instance_id).first() or abort(404)

    instance_blob = instance.instance
    if len(instance_blob) > 1024:
        # show only the first and last 512 characters if the instance is larger than 1kB
        instance_text = instance_blob[:512] + "\n\n... [truncated " + utils.download_size(len(instance_blob) - 1024) + "]\n\n" + instance_blob[-512:]
    else:
        instance_text = instance_blob

    return render('instance_details.html', instance=instance, instance_text=instance_text, blob_size=len(instance.instance), database=database, db=db)


@frontend.route('/<database>/instance/<int:instance_id>/download')
@require_phase(phases=(6, 7))
@require_login
def instance_download(database, instance_id):
    """ Return HTTP-Response containing the instance blob """
    db = models.get_database(database) or abort(404)
    instance = db.session.query(db.Instance).filter_by(idInstance=instance_id).first() or abort(404)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename=instance.name)

    return Response(response=instance.instance, headers=headers)


@frontend.route('/<database>/solver/<int:solver_id>')
@require_phase(phases=(2, 3, 4, 5, 6, 7))
@require_login
def solver_details(database, solver_id):
    """ Show solver details """
    db = models.get_database(database) or abort(404)
    solver = db.session.query(db.Solver).get(solver_id) or abort(404)

    if not is_admin() and db.is_competition() and not db.competition_phase() in (6, 7):
        if solver.user != g.User and not is_admin(): abort(401)

    return render('solver_details.html', solver=solver, database=database, db=db)


@frontend.route('/<database>/experiment/<int:experiment_id>/solver-configurations/<int:solver_configuration_id>')
@require_phase(phases=(3, 4, 5, 6, 7))
@require_login
def solver_configuration_details(database, experiment_id, solver_configuration_id):
    """ Show solver configuration details """
    db = models.get_database(database) or abort(404)
    solver_config = db.session.query(db.SolverConfiguration).get(solver_configuration_id) or abort(404)
    solver = solver_config.solver

    if not is_admin() and db.is_competition() and not db.competition_phase() in (6, 7):
        if solver.user != g.User: abort(401)

    parameters = solver_config.parameter_instances
    parameters.sort(key=lambda p: p.parameter.order)

    return render('solver_configuration_details.html', solver_config=solver_config, solver=solver, parameters=parameters, database=database, db=db)


@frontend.route('/<database>/experiment/<int:experiment_id>/result/<int:result_id>')
@require_phase(phases=(3, 4, 5, 6, 7))
@require_login
def experiment_result(database, experiment_id, result_id):
    """ Displays information about a single result (job) """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    result = db.session.query(db.ExperimentResult).get(result_id) or abort(404)

    if not is_admin() and db.is_competition() and not db.competition_phase() in (6, 7):
        if result.solver_configuration.solver.user != g.User: abort(401)

    resultFile = result.resultFile
    clientOutput = result.clientOutput

    if clientOutput is not None:
        if len(clientOutput) > 4*1024:
            # show only the first and last 2048 characters if the resultFile is larger than 4kB
            clientOutput_text = clientOutput[:2048] + "\n\n... [truncated " + str(int((len(clientOutput) - 4096) / 1024.0)) + " kB]\n\n" + clientOutput[-2048:]
        else:
            clientOutput_text = clientOutput
    else: clientOutput_text = "No output"

    if resultFile is not None:
        if len(resultFile) > 4*1024:
            # show only the first and last 2048 characters if the resultFile is larger than 4kB
            resultFile_text = resultFile[:2048] + "\n\n... [truncated " + str(int((len(resultFile) - 4096) / 1024.0)) + " kB]\n\n" + resultFile[-2048:]
        else:
            resultFile_text = resultFile
    else: resultFile_text = "No result"

    return render('result_details.html', experiment=experiment, result=result, solver=result.solver_configuration.solver,
                  solver_config=result.solver_configuration, instance=result.instance, resultFile_text=resultFile_text,
                  clientOutput_text=clientOutput_text, database=database, db=db)


@frontend.route('/<database>/experiment/<int:experiment_id>/result/<int:result_id>/download')
@require_phase(phases=(3, 4, 5, 6, 7))
@require_login
def experiment_result_download(database, experiment_id, result_id):
    """ Returns the specified job client output file as HTTP response """
    db = models.get_database(database) or abort(404)
    result = db.session.query(db.ExperimentResult).get(result_id) or abort(404)

    if not is_admin() and db.is_competition() and not db.competition_phase() in (6, 7):
        if result.solver_configuration.solver.user != g.User: abort(401)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename=result.resultFileName)

    return Response(response=result.resultFile, headers=headers)


@frontend.route('/<database>/experiment/<int:experiment_id>/result/<int:result_id>/download-client-output')
@require_phase(phases=(3, 4, 5, 6, 7))
@require_login
def experiment_result_download_client_output(database, experiment_id, result_id):
    """ Returns the specified job client output as HTTP response """
    db = models.get_database(database) or abort(404)
    result = db.session.query(db.ExperimentResult).get(result_id) or abort(404)

    if not is_admin() and db.is_competition() and not db.competition_phase() in (6, 7):
        if result.solver_configuration.solver.user != g.User: abort(401)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename="client_output_"+result.resultFileName)

    return Response(response=result.clientOutput, headers=headers)