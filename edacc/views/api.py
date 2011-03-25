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
    import simplejson as json
except ImportError:
    import json

from sqlalchemy import func

from flask import abort, Module

from edacc import models
from edacc.views.helpers import require_admin

api = Module(__name__)

@api.route('/api/<database>/experiment-results/<int:id>')
def get_experiment_result(database, id):
    db = models.get_database(database) or abort(404)
    er = db.session.query(db.ExperimentResult).get(id) or abort(404)
    return json.dumps(er.to_json())

@api.route('/api/<database>/statistics')
def statistics(database):
    db = models.get_database(database) or abort(404)
    jobs_running = db.session.query(db.ExperimentResult).filter_by(status=0).count()
    total_time = db.session.query(func.sum(db.ExperimentResult.resultTime)).first()[0]
    return json.dumps({
        'jobs_running': jobs_running,
        'total_time': total_time,
        'total_time_days': total_time / 60 / 60 / 24,
    })


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