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

from sqlalchemy import func

from flask import abort, Module, g

from edacc import models

api = Module(__name__)

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