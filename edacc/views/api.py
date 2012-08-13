# -*- coding: utf-8 -*-
"""
    edacc.views.api
    ---------------

    This module defines request handler functions for
    a RESTful web service.

    Served at /api.

    The service is pretty much read-only. (GET/HEAD)

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

try:
    from cjson import encode as json_dumps
except:
    try:
        from simplejson import dumps as json_dumps
    except ImportError:
        from json import dumps as json_dumps

import StringIO
import csv
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from werkzeug import Headers, secure_filename
from flask import abort, Blueprint, g, Response

from edacc import models

api = Blueprint('api', __name__, template_folder='static')

# TODO: restricted access

@api.route('/api/<database>/experiment-result/<int:id>/')
def get_experiment_result(database, id):
    db = models.get_database(database) or abort(404)
    er = db.session.query(db.ExperimentResult).get(id) or abort(404)
    return json_dumps(er.to_json())

@api.route('/api/<database>/experiment-results/<int:experiment_id>/')
def get_experiment_results(database, experiment_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    results = db.session.query(db.ExperimentResult).filter_by(experiment=exp).all()
    return json_dumps({
        "experiment_id": experiment_id,
        "results": [j.to_json() for j in results]
    })
    
@api.route('/api/<database>/statistics/<int:experiment_id>')
def experiment_statistics(database, experiment_id):
    db = models.get_database(database) or abort(404)
    exp = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    total_time = db.session.query(func.sum(db.ExperimentResult.resultTime)).filter_by(experiment=exp).first()[0]
    return json_dumps({
        'total_time': total_time,
        'total_time_hours': total_time / 60 / 60,
    })

@api.route('/api/<database>/statistics/')
def statistics(database):
    db = models.get_database(database) or abort(404)
    jobs_running = db.session.query(db.ExperimentResult).filter_by(status=0).count()
    total_time = db.session.query(func.sum(db.ExperimentResult.resultTime)).first()[0]
    return json_dumps({
        'jobs_running': jobs_running,
        'total_time': total_time,
        'total_time_days': total_time / 60 / 60 / 24,
    })

@api.route('/api/<database>/result-codes/')
def result_codes(database):
    db = models.get_database(database) or abort(404)
    return json_dumps([rc.to_json() for rc in db.session.query(db.ResultCodes).all()])

@api.route('/api/<database>/status-codes/')
def status_codes(database):
    db = models.get_database(database) or abort(404)
    return json_dumps([sc.to_json() for sc in db.session.query(db.StatusCodes).all()])

@api.route('/api/<database>/configuration-runs/<int:experiment_id>/')
def configuration_runs(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)
    if not experiment.configuration_scenario: abort(404)

    solver_configs = [sc for sc in experiment.solver_configurations if sc.solver_binary == experiment.configuration_scenario.solver_binary]
    solver_config_ids = [sc.idSolverConfig for sc in solver_configs]
    configurable_parameters = [p.parameter for p in experiment.configuration_scenario.parameters if p.configurable and p.parameter.name not in ('instance', 'seed')]
    configurable_parameters_ids = [p.idParameter for p in configurable_parameters]
    parameter_instances = db.session.query(db.ParameterInstance).options(joinedload('parameter')).filter(db.ParameterInstance.SolverConfig_idSolverConfig.in_(solver_config_ids)).all()

    instances_by_id = dict((i.idInstance, i) for i in experiment.get_instances(db))
    instance_properties = [p for p in db.session.query(db.Property) if p.is_instance_property()]

    parameter_values = dict()
    for pv in parameter_instances:
        if pv.Parameters_idParameter not in configurable_parameters_ids: continue
        if pv.SolverConfig_idSolverConfig not in parameter_values:
            parameter_values[pv.SolverConfig_idSolverConfig] = dict()
        parameter_values[pv.SolverConfig_idSolverConfig][pv.Parameters_idParameter] = pv.value

    results, _, _ = experiment.get_result_matrix(db, experiment.solver_configurations, experiment.get_instances(db), cost=experiment.defaultCost)

    csv_response = StringIO.StringIO()
    csv_writer = csv.writer(csv_response)
    csv_writer.writerow([p.name for p in configurable_parameters] + [p.name for p in instance_properties] + ['par1', 'censored'])
    for idInstance in results:
        for idSolverConfig in results[idInstance]:
            for run in results[idInstance][idSolverConfig]:
                csv_writer.writerow([parameter_values[idSolverConfig].get(p.idParameter, '') for p in configurable_parameters] + \
                                    [instances_by_id[idInstance].get_property_value(p.idProperty, db) for p in instance_properties] + \
                                    [run.penalized_time1, 1 if run.censored else 0])

    csv_response.seek(0)
    headers = Headers()
    headers.add('Content-Type', 'text/csv')
    headers.add('Content-Disposition', 'attachment', filename=secure_filename(experiment.name) + "_configuration_runs.csv")
    return Response(response=csv_response.read(), headers=headers)

"""
URIs that should eventually be implemented (all starting with /api)

/databases - List of databases (that can be used for the <database> parts of other URIs)
/<database>/experiments - List of experiments
/<database>/experiments/<int:experiment_id> - Experiment parameters, list of instances and solver configs used
/<database>/solver-configurations/<int:solver_configuration_id> - Solver configuration details
/<database>/instances/<int:instance_id> - Instance details
/<database>/experiment-results/by-experiment/<id:experiment_id>
                              /by-solver-configuration/<int:solver_configuration_id> - List of experiment result ids
                                                                                       of the solver configuration's results
/<database>/experiment-results/by-experiment/<id:experiment_id>
                              /by-instance/<int:instance_id>    - List of experiment results ids of the instances' results
"""