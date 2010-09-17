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

from edacc import plots, config, models, forms, ranking, statistics
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
    result_properties = db.get_result_properties()
    result_properties = zip([p.idSolverProperty for p in result_properties], [p.name for p in result_properties])
    form.solver_property.choices = [('cputime', 'CPU Time')] + result_properties

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


@analysis.route('/<database>/experiment/<int:experiment_id>/rtds/')
@require_phase(phases=(5, 6, 7))
@require_login
def rtds(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    form = forms.RTDPlotsForm(request.args)
    form.instance.query = experiment.instances
    form.sc.query = experiment.solver_configurations
    GET_data = "&".join(['='.join(list(t)) for t in request.args.items(multi=True)])

    return render('/analysis/rtds.html', database=database,
                  experiment=experiment, db=db, form=form, GET_data=GET_data)


@analysis.route('/<database>/experiment/<int:experiment_id>/scatter-two-solvers/')
@require_phase(phases=(5, 6, 7))
@require_login
def scatter_2solver_1property(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    result_properties = db.get_result_properties()
    result_properties = zip([p.idSolverProperty for p in result_properties], [p.name for p in result_properties])
    numRuns = experiment.get_num_runs(db)
    runs = zip(range(numRuns), ["#" + str(i) for i in range(numRuns)])

    form = forms.TwoSolversOnePropertyScatterPlotForm(request.args)
    form.solver_config1.query = experiment.solver_configurations
    form.solver_config2.query = experiment.solver_configurations
    form.instances.query = sorted(experiment.instances, key=lambda i: i.name)
    form.run.choices = [('average', 'All runs - average'),
                        ('median', 'All runs - median'),
                        ('all', 'All runs')
                        ] + runs
    form.solver_property.choices = [('cputime', 'CPU Time')] + result_properties

    GET_data = ""
    if form.solver_config1.data and form.solver_config2.data:
        GET_data = "solver_config1=" + str(form.solver_config1.data.idSolverConfig)
        GET_data += "&solver_config2=" + str(form.solver_config2.data.idSolverConfig)
        GET_data += "&run=" + form.run.data + "&" + "&".join(["instances=%s" % (str(i.idInstance),) for i in form.instances.data])
        GET_data += "&solver_property=" + form.solver_property.data
        GET_data += "&scaling=" + (form.scaling.data if form.scaling.data != 'None' else 'none')

    return render('/analysis/scatter_2solver_1property.html', database=database,
                  experiment=experiment, db=db, form=form, GET_data=GET_data)


@analysis.route('/<database>/experiment/<int:experiment_id>/scatter-one-solver-instance-vs-result/')
@require_phase(phases=(5, 6, 7))
@require_login
def scatter_1solver_instance_vs_result_property(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    result_properties = db.get_result_properties()
    result_properties = zip([p.idSolverProperty for p in result_properties], [p.name for p in result_properties])
    instance_properties = db.get_instance_properties()
    instance_properties = zip([p.name for p in instance_properties], [p.name for p in instance_properties])
    numRuns = experiment.get_num_runs(db)
    runs = zip(range(numRuns), ["#" + str(i) for i in range(numRuns)])

    form = forms.OneSolverInstanceAgainstResultPropertyPlotForm(request.args)
    form.solver_config.query = experiment.solver_configurations
    form.solver_property.choices = [('cputime', 'CPU Time')] + result_properties
    form.instance_property.choices = [('numAtoms', 'Number of Atoms')] + instance_properties
    form.instances.query = sorted(experiment.instances, key=lambda i: i.name)
    form.run.choices = [('average', 'All runs - average'),
                        ('median', 'All runs - median'),
                        ('all', 'All runs')
                        ] + runs

    GET_data = ""
    if form.solver_config.data:
        GET_data = "solver_config=" + str(form.solver_config.data.idSolverConfig)
        GET_data += "&run=" + form.run.data + "&" + "&".join(["instances=%s" % (str(i.idInstance),) for i in form.instances.data])
        GET_data += "&solver_property=" + form.solver_property.data
        GET_data += "&instance_property=" + form.instance_property.data
        GET_data += "&scaling=" + (form.scaling.data if form.scaling.data != 'None' else 'none')

    return render('/analysis/scatter_solver_instance_vs_result.html', database=database,
                  experiment=experiment, db=db, form=form, GET_data=GET_data)


@analysis.route('/<database>/experiment/<int:experiment_id>/scatter-one-solver-result-vs-result/')
@require_phase(phases=(5, 6, 7))
@require_login
def scatter_1solver_result_vs_result_property(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    result_properties = db.get_result_properties()
    result_properties = zip([p.idSolverProperty for p in result_properties], [p.name for p in result_properties])
    numRuns = experiment.get_num_runs(db)
    runs = zip(range(numRuns), ["#" + str(i) for i in range(numRuns)])

    form = forms.OneSolverTwoResultPropertiesPlotForm(request.args)
    form.solver_config.query = experiment.solver_configurations
    form.solver_property1.choices = [('cputime', 'CPU Time')] + result_properties
    form.solver_property2.choices = [('cputime', 'CPU Time')] + result_properties
    form.instances.query = sorted(experiment.instances, key=lambda i: i.name)
    form.run.choices = [('average', 'All runs - average'),
                        ('median', 'All runs - median'),
                        ('all', 'All runs')
                        ] + runs

    GET_data = ""
    if form.solver_config.data:
        GET_data = "solver_config=" + str(form.solver_config.data.idSolverConfig)
        GET_data += "&run=" + form.run.data + "&" + "&".join(["instances=%s" % (str(i.idInstance),) for i in form.instances.data])
        GET_data += "&solver_property1=" + form.solver_property1.data
        GET_data += "&solver_property2=" + form.solver_property2.data
        GET_data += "&scaling=" + (form.scaling.data if form.scaling.data != 'None' else 'none')

    return render('/analysis/scatter_solver_result_vs_result.html', database=database,
                  experiment=experiment, db=db, form=form, GET_data=GET_data)

@analysis.route('/<database>/experiment/<int:experiment_id>/rtd/')
@require_phase(phases=(5, 6, 7))
@require_login
def rtd(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    form = forms.RTDPlotForm(request.args)
    form.instance.query = experiment.instances
    form.solver_config.query = experiment.solver_configurations
    GET_data = "&".join(['='.join(list(t)) for t in request.args.items(multi=True)])

    return render('/analysis/rtd.html', database=database, experiment=experiment,
                  db=db, form=form, GET_data=GET_data)


@analysis.route('/<database>/experiment/<int:experiment_id>/probabilistic-domination/')
@require_phase(phases=(5, 6, 7))
@require_login
def probabilistic_domination(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    form = forms.ProbabilisticDominationForm(request.args)
    form.solver_config1.query = experiment.solver_configurations
    form.solver_config2.query = experiment.solver_configurations
    if form.solver_config1.data and form.solver_config2.data:
        sc1 = form.solver_config1.data
        sc2 = form.solver_config2.data

        sc1_dom_sc2 = set()
        sc2_dom_sc1 = set()
        no_dom = set()

        for instance in experiment.instances:
            res1 = [r.get_time() for r in db.session.query(db.ExperimentResult).filter_by(experiment=experiment, instance=instance, solver_configuration=sc1).all()]
            res2 = [r.get_time() for r in db.session.query(db.ExperimentResult).filter_by(experiment=experiment, instance=instance, solver_configuration=sc2).all()]
            d = statistics.prob_domination(res1, res2)
            if d == 1:
                sc1_dom_sc2.add(instance)
            elif d == -1:
                sc2_dom_sc1.add(instance)
            else:
                no_dom.add(instance)

        return render('/analysis/probabilistic_domination.html',
                      database=database, db=db, experiment=experiment,
                      form=form, sc1_dom_sc2=sc1_dom_sc2, sc2_dom_sc1=sc2_dom_sc1,
                      no_dom=no_dom)

    return render('/analysis/probabilistic_domination.html', database=database, db=db,
                  experiment=experiment, form=form)