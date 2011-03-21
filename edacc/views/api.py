# -*- coding: utf-8 -*-
"""
    edacc.views.api
    ---------------

    This module defines request handler functions for
    a RESTful web service.

    Served at /api/<database>/*

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

try:
    import simplejson as json
except ImportError:
    import json

from flask import abort, Module

from edacc import models

api = Module(__name__)

@api.route('/api/<database>/experiment-result/<int:id>')
def get_experiment_result(database, id):
    db = models.get_database(database) or abort(404)
    er = db.session.query(db.ExperimentResult).get(id) or abort(404)
    return json.dumps(er.to_json())