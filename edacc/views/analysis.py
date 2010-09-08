# -*- coding: utf-8 -*-
"""
    edacc.views.analysis
    --------------------

    Defines request handler functions for the analysis pages.

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

analysis = Module(__name__)


def render(*args, **kwargs):
    from tidylib import tidy_document
    res = render_template(*args, **kwargs)
    doc, errs = tidy_document(res)
    return doc


@analysis.route('/<database>/experiment/<int:experiment_id>/ranking/')
@require_phase(phases=(6, 7))
@require_login
def solver_ranking(database, experiment_id):
    """ Display a page with the ranking of the solvers of
        the experiment.
    """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    ranked_solvers = ranking.rank_solvers(experiment)

    return render('/analysis/ranking.html', database=database, db=db,
                  experiment=experiment, ranked_solvers=ranked_solvers)

@analysis.route('/<database>/experiment/<int:experiment_id>/evaluation-solved-instances/')
@require_phase(phases=(5, 6, 7))
@require_login
def cactus_plot(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    return render('/analysis/solved_instances.html', database=database, experiment=experiment, db=db)


@analysis.route('/<database>/experiment/<int:experiment_id>/evaluation-cputime/')
@require_phase(phases=(5, 6, 7))
@require_login
def scatter_2solver_1property(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    form = forms.CPUTimeComparisonForm(request.args)
    form.solver1.query = experiment.solver_configurations
    form.solver2.query = experiment.solver_configurations
    numRuns = len(experiment.results) / len(experiment.solver_configurations) / len(experiment.instances)
    runs = zip(range(numRuns), ["#" + str(i) for i in range(numRuns)])
    form.run.choices = [('average', 'All runs - average time'),
                        ('median', 'All runs - median time'),
                        ('all', 'All runs')
                        ] + runs

    return render('/analysis/cputime.html', database=database, experiment=experiment, db=db, form=form)

def scatter_1solver_instance_vs_result_property():
    pass

def scatter_1solver_result_vs_result_property():
    pass