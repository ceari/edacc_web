# -*- coding: utf-8 -*-
"""
    edacc.views.analysis
    --------------------

    Defines request handler functions for the analysis pages.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

import math
import numpy

from flask import Module
from flask import render_template
from flask import abort, request

from edacc import models, forms, ranking, statistics
from edacc.views.helpers import require_phase, require_login
from edacc.constants import RANKING, ANALYSIS1, ANALYSIS2
from edacc.views import plot
from edacc.forms import EmptyQuery

analysis = Module(__name__)

def render(*args, **kwargs):
    from tidylib import tidy_document
    res = render_template(*args, **kwargs)
    doc, errs = tidy_document(res)
    return doc


@analysis.route('/<database>/experiment/<int:experiment_id>/ranking/')
@require_phase(phases=RANKING)
@require_login
def solver_ranking(database, experiment_id):
    """ Display a page with the ranking of the solvers of
        the experiment.
    """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    num_runs = experiment.get_num_runs(db)
    num_runs_per_solver = num_runs * len(experiment.instances)

    vbs_num_solved = 0
    vbs_cumulated_cpu = 0
    for i in experiment.instances:
        best_solver_run = db.session.query(db.ExperimentResult).filter_by(experiment=experiment)\
                                    .filter(db.ExperimentResult.resultCode.like('1%')) \
                                    .filter_by(instance=i).order_by(db.ExperimentResult.resultTime) \
                                    .first()
        if best_solver_run:
            vbs_num_solved += num_runs
            vbs_cumulated_cpu += best_solver_run.resultTime * num_runs

    ranked_solvers = ranking.number_of_solved_instances_ranking(experiment)
    data = [('Virtual Best Solver (VBS)',           # name of the solver
             vbs_num_solved,                        # number of successful runs
             vbs_num_solved / float(num_runs_per_solver),  # % of all runs
             1.0,                                   # % of vbs runs
             vbs_cumulated_cpu,                     # cumulated CPU time
             (0.0 if vbs_num_solved == 0 else vbs_cumulated_cpu / vbs_num_solved),    # average CPU time per successful run
             )]
    for solver in ranked_solvers:
        successful_runs = db.session.query(db.ExperimentResult).filter(db.ExperimentResult.resultCode.like('1%')) \
                                    .filter_by(experiment=experiment, solver_configuration=solver, status=1).all()
        num_successful_runs = len(successful_runs)
        data.append((
            solver.get_name(),
            num_successful_runs,
            0 if num_runs_per_solver == 0 else num_successful_runs / float(num_runs_per_solver),
            0 if vbs_num_solved == 0 else num_successful_runs / float(vbs_num_solved),
            sum(j.get_time() for j in successful_runs),
            numpy.average([j.get_time() for j in successful_runs] or 0)
        ))

    return render('/analysis/ranking.html', database=database, db=db,
                  experiment=experiment, ranked_solvers=ranked_solvers,
                  data=data)


@analysis.route('/<database>/experiment/<int:experiment_id>/cactus/')
@require_phase(phases=ANALYSIS1)
@require_login
def cactus_plot(database, experiment_id):
    """ Displays a page where the user can select a set of instances and a
        result property and obtains a cactus plot of the number of instances
        solved within a given amount of the result property.

        For example: Number of instances the program can solve when given 100 seconds
        of CPU time.
    """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    form = forms.CactusPlotForm(request.args)
    form.instances.query = sorted(experiment.instances, key=lambda i: i.name)
    result_properties = db.get_plotable_result_properties()
    result_properties = zip([p.idProperty for p in result_properties], [p.name for p in result_properties])
    form.solver_property.choices = [('cputime', 'CPU Time')] + result_properties

    GET_data = "&".join(['='.join(list(t)) for t in request.args.items(multi=True)])

    return render('/analysis/solved_instances.html', database=database,
                  experiment=experiment, db=db, form=form, GET_data=GET_data)


@analysis.route('/<database>/experiment/<int:experiment_id>/rtd-comparison/')
@require_phase(phases=ANALYSIS2)
@require_login
def result_property_comparison(database, experiment_id):
    """
        Displays a page allowing the user to compare the result property distributions
        of two solvers on an instance. The solvers and instance can be selected
        in a form.
        The page then displays a plot with the two distributions
        aswell as statistical tests of hypothesis such as "The distribution of solver A
        is significantly different to the one of solver B".

        Statistical tests implemented:
        - Kolmogorow-Smirnow two-sample test (Distribution1 = Distribution2)
        - Mann-Whitney-U-test (Distribution1 = Distribution2 or Median1 = Median2)
    """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    form = forms.RTDComparisonForm(request.args)
    form.instance.query = experiment.instances or EmptyQuery()
    form.solver_config1.query = experiment.solver_configurations or EmptyQuery()
    form.solver_config2.query = experiment.solver_configurations or EmptyQuery()
    result_properties = db.get_plotable_result_properties()
    result_properties = zip([p.idProperty for p in result_properties], [p.name for p in result_properties])
    form.solver_property.choices = [('cputime', 'CPU Time')] + result_properties
    GET_data = "&".join(['='.join(list(t)) for t in request.args.items(multi=True)])

    if form.solver_config1.data and form.solver_config2.data and form.instance.data:
        instance = db.session.query(db.Instance).filter_by(idInstance=int(request.args['instance'])).first() or abort(404)
        s1 = db.session.query(db.SolverConfiguration).get(int(request.args['solver_config1'])) or abort(404)
        s2 = db.session.query(db.SolverConfiguration).get(int(request.args['solver_config2'])) or abort(404)

        result_property = request.args.get('solver_property')
        if result_property != 'cputime':
            result_property = db.session.query(db.Property).get(int(result_property)).idProperty

        results1 = [r.get_property_value(result_property, db) for r in db.session.query(db.ExperimentResult)
                                        .filter_by(experiment=experiment,
                                                   solver_configuration=s1,
                                                   instance=instance).all()]
        results2 = [r.get_property_value(result_property, db) for r in db.session.query(db.ExperimentResult)
                                        .filter_by(experiment=experiment,
                                                   solver_configuration=s2,
                                                   instance=instance).all()]

        results1 = filter(lambda r: r is not None, results1)
        results2 = filter(lambda r: r is not None, results2)

        median1 = numpy.median(results1)
        median2 = numpy.median(results2)
        sample_size1 = len(results1)
        sample_size2 = len(results2)

        try:
            ks_statistic, ks_p_value = statistics.kolmogorow_smirnow_2sample_test(results1, results2)
            ks_error = None
        except Exception as e:
            ks_statistic, ks_p_value = None, None
            ks_error = str(e)

        try:
            wx_statistic, wx_p_value = statistics.wilcox_test(results1, results2)
            wx_error = None
        except Exception as e:
            wx_statistic, wx_p_value = None, None
            wx_error = str(e)


        return render('/analysis/result_property_comparison.html', database=database,
              experiment=experiment, db=db, form=form, GET_data=GET_data,
              ks_statistic=ks_statistic, ks_p_value=ks_p_value,
              wx_statistic=wx_statistic, wx_p_value=wx_p_value,
              wx_error=wx_error, ks_error=ks_error, median1=median1, median2=median2)


    return render('/analysis/result_property_comparison.html', database=database,
                  experiment=experiment, db=db, form=form, GET_data=GET_data)


@analysis.route('/<database>/experiment/<int:experiment_id>/rtds/')
@require_phase(phases=ANALYSIS2)
@require_login
def rtds(database, experiment_id):
    """
        Displays a page allowing the user to choose several solver configurations
        and an instance and displays a plot with the runtime distributions (as
        cumulative empirical distribution functions) of the solvers on the
        chosen instance.
    """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    form = forms.RTDPlotsForm(request.args)
    form.instance.query = experiment.instances or EmptyQuery()
    form.sc.query = experiment.solver_configurations or EmptyQuery()
    GET_data = "&".join(['='.join(list(t)) for t in request.args.items(multi=True)])

    return render('/analysis/rtds.html', database=database,
                  experiment=experiment, db=db, form=form, GET_data=GET_data)


@analysis.route('/<database>/experiment/<int:experiment_id>/scatter-two-solvers/')
@require_phase(phases=ANALYSIS2)
@require_login
def scatter_2solver_1property(database, experiment_id):
    """
        Displays a page allowing the user to plot the results of two solvers
        on the instances against each other in a scatter plot.
    """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    result_properties = db.get_plotable_result_properties()
    result_properties = zip([p.idProperty for p in result_properties], [p.name for p in result_properties])
    numRuns = experiment.get_num_runs(db)
    runs = zip(range(numRuns), ["#" + str(i) for i in range(numRuns)])

    form = forms.TwoSolversOnePropertyScatterPlotForm(request.args)
    form.solver_config1.query = experiment.solver_configurations or EmptyQuery()
    form.solver_config2.query = experiment.solver_configurations or EmptyQuery()
    form.instances.query = sorted(experiment.instances, key=lambda i: i.name) or EmptyQuery()
    form.run.choices = [('average', 'All runs - average'),
                        ('median', 'All runs - median'),
                        ('all', 'All runs')
                        ] + runs
    form.solver_property.choices = [('cputime', 'CPU Time')] + result_properties

    GET_data = "&".join(['='.join(list(t)) for t in request.args.items(multi=True)])
    spearman_r, spearman_p_value = None, None
    pearson_r, pearson_p_value = None, None
    if form.solver_config1.data and form.solver_config2.data:
        points = plot.scatter_2solver_1property_points(db, experiment,
                        form.solver_config1.data, form.solver_config2.data,
                        form.instances.data, form.solver_property.data, form.run.data)

        # log transform data if axis scaling is enabled, only affects pearson's coeff.
        if form.xscale.data == 'log':
            points = map(lambda p: (math.log(p[0]) if p[0] != 0 else 0, p[1]), points)
        if form.yscale.data == 'log':
            points = map(lambda p: (p[0], math.log(p[1]) if p[1] != 0 else 0), points)

        spearman_r, spearman_p_value = statistics.spearman_correlation([p[0] for p in points], [p[1] for p in points])
        pearson_r, pearson_p_value = statistics.pearson_correlation([p[0] for p in points], [p[1] for p in points])

    return render('/analysis/scatter_2solver_1property.html', database=database,
                  experiment=experiment, db=db, form=form, GET_data=GET_data,
                  spearman_r=spearman_r, spearman_p_value=spearman_p_value,
                  pearson_r=pearson_r, pearson_p_value=pearson_p_value)


@analysis.route('/<database>/experiment/<int:experiment_id>/scatter-instance-vs-result/')
@require_phase(phases=ANALYSIS2)
@require_login
def scatter_1solver_instance_vs_result_property(database, experiment_id):
    """
        Displays a page allowing the user to plot a result property against
        an instance property of one solver's results on instances in a scatter
        plot.
        For example: Number of Atoms in the instance against CPU time needed
    """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    result_properties = db.get_plotable_result_properties()
    result_properties = zip([p.idProperty for p in result_properties], [p.name for p in result_properties])
    instance_properties = db.get_plotable_instance_properties()
    instance_properties = zip([p.idProperty for p in instance_properties], [p.name for p in instance_properties])
    numRuns = experiment.get_num_runs(db)
    runs = zip(range(numRuns), ["#" + str(i) for i in range(numRuns)])

    form = forms.OneSolverInstanceAgainstResultPropertyPlotForm(request.args)
    form.solver_config.query = experiment.solver_configurations or EmptyQuery()
    form.solver_property.choices = [('cputime', 'CPU Time')] + result_properties
    form.instance_property.choices = instance_properties
    form.instances.query = sorted(experiment.instances, key=lambda i: i.name) or EmptyQuery()
    form.run.choices = [('average', 'All runs - average'),
                        ('median', 'All runs - median'),
                        ('all', 'All runs')
                        ] + runs

    GET_data = "&".join(['='.join(list(t)) for t in request.args.items(multi=True)])
    spearman_r, spearman_p_value = None, None
    pearson_r, pearson_p_value = None, None
    if form.solver_config.data and form.instance_property.data:
        points = plot.scatter_1solver_instance_vs_result_property_points(db, experiment,
                        form.solver_config.data, form.instances.data,
                        form.instance_property.data, form.solver_property.data,
                        form.run.data)

        # log transform data if axis scaling is enabled, only affects pearson's coeff.
        if form.xscale.data == 'log':
            points = map(lambda p: (math.log(p[0]) if p[0] != 0 else 0, p[1]), points)
        if form.yscale.data == 'log':
            points = map(lambda p: (p[0], math.log(p[1]) if p[1] != 0 else 0), points)

        spearman_r, spearman_p_value = statistics.spearman_correlation([p[0] for p in points], [p[1] for p in points])
        pearson_r, pearson_p_value = statistics.pearson_correlation([p[0] for p in points], [p[1] for p in points])

    return render('/analysis/scatter_solver_instance_vs_result.html', database=database,
                  experiment=experiment, db=db, form=form, GET_data=GET_data,
                  spearman_r=spearman_r, spearman_p_value=spearman_p_value,
                  pearson_r=pearson_r, pearson_p_value=pearson_p_value)


@analysis.route('/<database>/experiment/<int:experiment_id>/scatter-result-vs-result/')
@require_phase(phases=ANALYSIS2)
@require_login
def scatter_1solver_result_vs_result_property(database, experiment_id):
    """
        Displays a page allowing the user to plot two result properties of one
        solver's results on instances in a scatter plot.
        For example: CPU time vs. Memory used
    """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    result_properties = db.get_plotable_result_properties()
    result_properties = zip([p.idProperty for p in result_properties], [p.name for p in result_properties])
    numRuns = experiment.get_num_runs(db)
    runs = zip(range(numRuns), ["#" + str(i) for i in range(numRuns)])

    form = forms.OneSolverTwoResultPropertiesPlotForm(request.args)
    form.solver_config.query = experiment.solver_configurations or EmptyQuery()
    form.solver_property1.choices = [('cputime', 'CPU Time')] + result_properties
    form.solver_property2.choices = [('cputime', 'CPU Time')] + result_properties
    form.instances.query = sorted(experiment.instances, key=lambda i: i.name) or EmptyQuery()
    form.run.choices = [('average', 'All runs - average'),
                        ('median', 'All runs - median'),
                        ('all', 'All runs')
                        ] + runs

    GET_data = "&".join(['='.join(list(t)) for t in request.args.items(multi=True)])
    spearman_r, spearman_p_value = None, None
    pearson_r, pearson_p_value = None, None
    if form.solver_config.data:
        points = plot.scatter_1solver_result_vs_result_property_plot(db, experiment,
                    form.solver_config.data, form.instances.data,
                    form.solver_property1.data, form.solver_property2.data, form.run.data)

        # log transform data if axis scaling is enabled, only affects pearson's coeff.
        if form.xscale.data == 'log':
            points = map(lambda p: (math.log(p[0]) if p[0] != 0 else 0, p[1]), points)
        if form.yscale.data == 'log':
            points = map(lambda p: (p[0], math.log(p[1]) if p[1] != 0 else 0), points)

        spearman_r, spearman_p_value = statistics.spearman_correlation([p[0] for p in points], [p[1] for p in points])
        pearson_r, pearson_p_value = statistics.pearson_correlation([p[0] for p in points], [p[1] for p in points])

    return render('/analysis/scatter_solver_result_vs_result.html', database=database,
                  experiment=experiment, db=db, form=form, GET_data=GET_data,
                  spearman_r=spearman_r, spearman_p_value=spearman_p_value,
                  pearson_r=pearson_r, pearson_p_value=pearson_p_value)


@analysis.route('/<database>/experiment/<int:experiment_id>/rtd/')
@require_phase(phases=ANALYSIS2)
@require_login
def rtd(database, experiment_id):
    """
        Displays a page with plots of the runtime distribution (as CDF) and
        the kernel density estimation of a chosen solver on a chosen instance.
    """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    form = forms.RTDPlotForm(request.args)
    form.instance.query = experiment.instances or EmptyQuery()
    form.solver_config.query = experiment.solver_configurations or EmptyQuery()
    GET_data = "&".join(['='.join(list(t)) for t in request.args.items(multi=True)])

    return render('/analysis/rtd.html', database=database, experiment=experiment,
                  db=db, form=form, GET_data=GET_data)


@analysis.route('/<database>/experiment/<int:experiment_id>/probabilistic-domination/')
@require_phase(phases=ANALYSIS2)
@require_login
def probabilistic_domination(database, experiment_id):
    """
        Displays a page allowing the user to choose two solver configurations and
        categorizing the instances of the experiment into three groups:
        - Instances where solver A prob. dominates solver B.
        - Instances where solver B prob. dominates solver A.
        - Instances with crossovers in the RTD's CDF
        See edacc.statistics for a definition of probabilistic domination
    """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    form = forms.ProbabilisticDominationForm(request.args)
    form.solver_config1.query = experiment.solver_configurations or EmptyQuery()
    form.solver_config2.query = experiment.solver_configurations or EmptyQuery()
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


@analysis.route('/<database>/experiment/<int:experiment_id>/box-plots/')
@require_phase(phases=ANALYSIS2)
@require_login
def box_plots(database, experiment_id):
    """ Displays a page allowing the user to plot box plots with the results of all runs
        of some solvers on some instances
    """
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    form = forms.BoxPlotForm(request.args)
    form.solver_configs.query = experiment.solver_configurations or EmptyQuery()
    form.instances.query = experiment.instances or EmptyQuery()
    GET_data = "&".join(['='.join(list(t)) for t in request.args.items(multi=True)])

    return render('/analysis/box_plots.html', database=database, db=db,
                  experiment=experiment, form=form, GET_data=GET_data)
