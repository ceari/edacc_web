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

    form = forms.CactusPlotForm(request.args)
    form.instances.query = sorted(experiment.instances, key=lambda i: i.name)
    GET_data = "&".join(['='.join(list(t)) for t in request.args.items(multi=True)])

    return render('/analysis/solved_instances.html', database=database,
                  experiment=experiment, db=db, form=form, GET_data=GET_data)

@analysis.route('/<database>/experiment/<int:experiment_id>/rtd-comparison/')
@require_phase(phases=(5, 6, 7))
@require_login
def rtd_comparison(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    form = forms.RTDComparisonForm(request.args)
    form.instance.query = experiment.instances
    form.solver_config1.query = experiment.solver_configurations
    form.solver_config2.query = experiment.solver_configurations
    GET_data = "&".join(['='.join(list(t)) for t in request.args.items(multi=True)])

    if form.solver_config1.data and form.solver_config2.data and form.instance.data:
        instance = db.session.query(db.Instance).filter_by(idInstance=int(request.args['instance'])).first() or abort(404)
        s1 = db.session.query(db.SolverConfiguration).get(int(request.args['solver_config1'])) or abort(404)
        s2 = db.session.query(db.SolverConfiguration).get(int(request.args['solver_config2'])) or abort(404)

        results1 = [r.get_time() for r in db.session.query(db.ExperimentResult)
                                        .filter_by(experiment=experiment,
                                                   solver_configuration=s1,
                                                   instance=instance).all()]
        results2 = [r.get_time() for r in db.session.query(db.ExperimentResult)
                                        .filter_by(experiment=experiment,
                                                   solver_configuration=s2,
                                                   instance=instance).all()]

        from scipy import stats
        ks_statistic, ks_p_value = stats.ks_2samp(results1, results2)
        try:
            wx_statistic, wx_p_value = stats.mannwhitneyu(results1, results2)
            wx_error = None
        except ValueError as e:
            wx_statistic, wx_p_value = None, None
            wx_error = str(e)


        return render('/analysis/rtd_comparison.html', database=database,
              experiment=experiment, db=db, form=form, GET_data=GET_data,
              ks_statistic=ks_statistic, ks_p_value=ks_p_value,
              wx_statistic=wx_statistic, wx_p_value=wx_p_value,
              wx_error=wx_error)


    return render('/analysis/rtd_comparison.html', database=database,
                  experiment=experiment, db=db, form=form, GET_data=GET_data)


@analysis.route('/<database>/experiment/<int:experiment_id>/evaluation-cputime/')
@require_phase(phases=(5, 6, 7))
@require_login
def scatter_2solver_1property(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    form = forms.TwoSolversOnePropertyScatterPlotForm(request.args)
    form.solver_config1.query = experiment.solver_configurations
    form.solver_config2.query = experiment.solver_configurations
    form.instances.query = sorted(experiment.instances, key=lambda i: i.name)
    numRuns = len(experiment.results) / len(experiment.solver_configurations) / len(experiment.instances)
    runs = zip(range(numRuns), ["#" + str(i) for i in range(numRuns)])
    form.run.choices = [('average', 'All runs - average time'),
                        ('median', 'All runs - median time'),
                        ('all', 'All runs')
                        ] + runs

    GET_data = ""
    if form.solver_config1.data and form.solver_config2.data:
        GET_data = "solver_config1=" + str(form.solver_config1.data.idSolverConfig)
        GET_data += "&solver_config2=" + str(form.solver_config2.data.idSolverConfig)
        GET_data += "&run=" + form.run.data + "&" + "&".join(["instances=%s" % (str(i.idInstance),) for i in form.instances.data])
        GET_data += "&scaling=" + (form.scaling.data if form.scaling.data != 'None' else 'none')

    return render('/analysis/scatter_2solver_1property.html', database=database,
                  experiment=experiment, db=db, form=form, GET_data=GET_data)

def scatter_1solver_instance_vs_result_property():
    pass

def scatter_1solver_result_vs_result_property():
    pass