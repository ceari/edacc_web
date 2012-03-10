# -*- coding: utf-8 -*-
"""
    edacc.ranking
    -------------

    This module implements some possible ranking schemes that can be used
    by the ranking view in the analysis module.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""
import numpy
from scipy.stats.mstats import mquantiles

from sqlalchemy.sql import select, and_, functions, not_, expression


def avg_point_biserial_correlation_ranking(db, experiment, instances):
    """ Ranking through comparison of the RTDs of the solvers on the instances.
        This ranking only makes sense if the there were multiple runs of each
        solver on each instance.
        See the paper "Statistical Methodology for Comparison of SAT Solvers"
        by M. Nikolić for details.
    """
    instance_ids = [i.idInstance for i in instances]

    table = db.metadata.tables['ExperimentResults']
    c_solver_config_id = table.c['SolverConfig_idSolverConfig']
    c_result_time = table.c['resultTime']
    c_experiment_id = table.c['Experiment_idExperiment']
    c_result_code = table.c['resultCode']
    c_status = table.c['status']
    c_instance_id = table.c['Instances_idInstance']

    s = select([c_solver_config_id, c_instance_id, c_result_time], \
        and_(c_experiment_id==experiment.idExperiment, c_instance_id.in_(instance_ids),
             c_result_code.in_([1,-21,-22]),
              c_status.in_([1,21,22]),
             )) \
        .select_from(table)


    query_results = db.session.connection().execute(s)
    solver_config_results = dict([(s.idSolverConfig, dict([(i, list()) for i in instance_ids])) for s in experiment.solver_configurations])
    for row in query_results:
        solver_config_results[row[0]][row[1]].append(row[2])

    def rank_simple(vector):
        return sorted(range(len(vector)), key=vector.__getitem__)

    def rankdata(a):
        n = len(a)
        ivec=rank_simple(a)
        svec=[a[rank] for rank in ivec]
        sumranks = 0
        dupcount = 0
        newarray = [0]*n
        for i in xrange(n):
            sumranks += i
            dupcount += 1
            if i==n-1 or svec[i] != svec[i+1]:
                averank = sumranks / float(dupcount) + 1
                for j in xrange(i-dupcount+1,i+1):
                    newarray[ivec[j]] = averank
                sumranks = 0
                dupcount = 0
        return newarray

    def pointbiserialcorr(s1, s2):
        """ Calculate the mean point biserial correlation of the RTDs of
            the two given solvers on all instances of the experiment.
            Only consider values where the statistical significance is large
            enough (p-value < alpha = 0.05)
        """
        alpha = 0.05 # level of statistical significant difference
        d = 0.0
        num = 0
        for i in instance_ids:
            res1 = solver_config_results[s1.idSolverConfig][i]
            res2 = solver_config_results[s2.idSolverConfig][i]
            ranked_data = list(rankdata(res1 + res2))

            r, p = stats.pointbiserialr([1] * len(res1) + [0] * len(res2), ranked_data)
            # only take instances with significant differences into account
            if p < alpha:
                #print str(s1), str(s2), str(i), r, p
                d += r
                num += 1

        if num > 0:
            return d / num # return mean difference
        else:
            return 0 # s1 == s2

    def comp(s1, s2):
        """ Comparator function for point biserial correlation based ranking."""
        r = pointbiserialcorr(s1, s2)
        if r < 0: return 1
        elif r > 0: return -1
        else: return 0

    # List of solvers sorted by their rank. Best solver first.
    return list(sorted(experiment.solver_configurations, cmp=comp))

def number_of_solved_instances_ranking(db, experiment, instances, solver_configs, cost='resultTime'):
    """ Ranking by the number of instances correctly solved.
        This is determined by an resultCode that starts with '1' and a 'finished' status
        of a job.
    """
    instance_ids = [i.idInstance for i in instances]
    solver_config_ids = [i.idSolverConfig for i in solver_configs]

    if not solver_config_ids: return []

    table = db.metadata.tables['ExperimentResults']
    c_solver_config_id = table.c['SolverConfig_idSolverConfig']
    c_result_time = table.c['resultTime']
    c_experiment_id = table.c['Experiment_idExperiment']
    c_result_code = table.c['resultCode']
    c_status = table.c['status']
    c_instance_id = table.c['Instances_idInstance']
    c_solver_config_id = table.c['SolverConfig_idSolverConfig']
    if cost == 'resultTime':
        cost_column = 'resultTime'
        cost_limit_column = table.c['CPUTimeLimit']
    elif cost == 'wallTime':
        cost_column = 'wallTime'
        cost_limit_column = table.c['wallClockTimeLimit']
    else:
        cost_column = 'cost'
        inf = float('inf')
        cost_limit_column = table.c['CPUTimeLimit']

    s = select([c_solver_config_id, functions.sum(table.c[cost_column]), functions.count()], \
        and_(c_experiment_id==experiment.idExperiment, c_result_code.like(u'1%'), c_status==1,
             c_instance_id.in_(instance_ids), c_solver_config_id.in_(solver_config_ids))) \
        .select_from(table) \
        .group_by(c_solver_config_id)

    results = {}
    query_results = db.session.connection().execute(s)
    for row in query_results:
        results[row[0]] = (row[1], row[2])
        
    def sgn(x):
        if x > 0: return 1
        elif x < 0: return -1
        else: return 0

    def comp(s1, s2):
        num_solved_s1, num_solved_s2 = 0, 0
        if results.has_key(s1.idSolverConfig):
            num_solved_s1 = results[s1.idSolverConfig][1]
        if results.has_key(s2.idSolverConfig):
            num_solved_s2 = results[s2.idSolverConfig][1]

        if num_solved_s1 > num_solved_s2: return 1
        elif num_solved_s1 < num_solved_s2: return -1
        else:
            # break ties by cumulative cost over all solved instances
            if results.has_key(s1.idSolverConfig) and results.has_key(s2.idSolverConfig):
                return sgn(results[s2.idSolverConfig][0] - results[s1.idSolverConfig][0])
            else:
                return 0

    return list(sorted(experiment.solver_configurations,cmp=comp,reverse=True))

def get_ranking_data(db, experiment, ranked_solvers, instances, calculate_par10, calculate_avg_stddev, cost):
    instance_ids = [i.idInstance for i in instances]
    solver_config_ids = [s.idSolverConfig for s in ranked_solvers]
    if not solver_config_ids: return []
    
    max_num_runs = experiment.get_max_num_runs(db)
    max_num_runs_per_solver = max_num_runs * len(instance_ids)

    table = db.metadata.tables['ExperimentResults']
    if cost == 'resultTime':
        cost_column = table.c['resultTime']
        cost_property = db.ExperimentResult.resultTime
        cost_limit_column = table.c['CPUTimeLimit']
    elif cost == 'wallTime':
        cost_column = table.c['wallTime']
        cost_property = db.ExperimentResult.wallTime
        cost_limit_column = table.c['wallClockTimeLimit']
    else:
        cost_column = table.c['cost']
        cost_property = db.ExperimentResult.cost
        inf = float('inf')
        cost_limit_column = table.c['CPUTimeLimit']

    vbs_num_solved = 0
    vbs_cumulated_cpu = 0
    from sqlalchemy import func, or_, not_
    best_instance_runtimes = db.session.query(func.min(cost_property)) \
        .filter_by(experiment=experiment) \
        .filter(db.ExperimentResult.resultCode.like(u'1%')) \
        .filter(db.ExperimentResult.Instances_idInstance.in_(instance_ids)) \
        .group_by(db.ExperimentResult.Instances_idInstance).all()

    vbs_num_solved = len(best_instance_runtimes) * max_num_runs
    vbs_cumulated_cpu = sum(r[0] for r in best_instance_runtimes) * max_num_runs

    #num_unsolved_instances = len(instances) - len(best_instance_runtimes)

    vbs_par10 = 0.0

    # Virtual best solver data
    data = [('Virtual Best Solver (VBS)',                   # name of the solver
             vbs_num_solved,                                # number of successful runs
             0.0 if max_num_runs_per_solver == 0 else
                    vbs_num_solved / float(max_num_runs_per_solver) ,  # % of all runs
             1.0,                                           # % of vbs runs
             vbs_cumulated_cpu,                             # cumulated CPU time
             (0.0 if vbs_num_solved == 0 else
                     vbs_cumulated_cpu / vbs_num_solved),   # average CPU time per successful run
             0.0, # avg stddev
             0.0,
             0.0,
             vbs_par10
             )]

    # single query fetch of all/most required data
    table = db.metadata.tables['ExperimentResults']
    s = select([expression.label('cost', cost_column),
                table.c['SolverConfig_idSolverConfig'],
                table.c['Instances_idInstance']],
                and_(table.c['resultCode'].like(u'1%'),
                    table.c['Instances_idInstance'].in_(instance_ids),
                    table.c['SolverConfig_idSolverConfig'].in_(solver_config_ids),
                    table.c['Experiment_idExperiment']==experiment.idExperiment,
                    table.c['status']==1)).select_from(table)
    successful_runs = db.session.connection().execute(s)

    runs_by_solver_and_instance = {}
    for run in successful_runs:
        if not runs_by_solver_and_instance.has_key(run.SolverConfig_idSolverConfig):
            runs_by_solver_and_instance[run.SolverConfig_idSolverConfig] = {}
        if not runs_by_solver_and_instance[run.SolverConfig_idSolverConfig].has_key(run.Instances_idInstance):
            runs_by_solver_and_instance[run.SolverConfig_idSolverConfig][run.Instances_idInstance] = []
        runs_by_solver_and_instance[run.SolverConfig_idSolverConfig][run.Instances_idInstance].append(run)

    if calculate_avg_stddev:
        finished_runs_by_solver_and_instance = {}
        s = select([expression.label('cost', cost_column),
                    table.c['SolverConfig_idSolverConfig'],
                    table.c['Instances_idInstance']],
            and_(table.c['Instances_idInstance'].in_(instance_ids),
                table.c['SolverConfig_idSolverConfig'].in_(solver_config_ids),
                table.c['Experiment_idExperiment']==experiment.idExperiment,
                not_(table.c['status'].in_((-1,0))))).select_from(table)
        finished_runs = db.session.connection().execute(s)
        for run in finished_runs:
            if not finished_runs_by_solver_and_instance.has_key(run.SolverConfig_idSolverConfig):
                finished_runs_by_solver_and_instance[run.SolverConfig_idSolverConfig] = {}
            if not finished_runs_by_solver_and_instance[run.SolverConfig_idSolverConfig].has_key(run.Instances_idInstance):
                finished_runs_by_solver_and_instance[run.SolverConfig_idSolverConfig][run.Instances_idInstance] = []
            finished_runs_by_solver_and_instance[run.SolverConfig_idSolverConfig][run.Instances_idInstance].append(run)

    if calculate_par10:
        failed_runs_by_solver = dict((sc.idSolverConfig, list()) for sc in ranked_solvers)
        s = select([expression.label('cost_limit', cost_limit_column), table.c['SolverConfig_idSolverConfig']],
                    and_(table.c['Experiment_idExperiment']==experiment.idExperiment,
                        table.c['Instances_idInstance'].in_(instance_ids),
                        table.c['SolverConfig_idSolverConfig'].in_(solver_config_ids),
                        and_(
                            or_(
                                table.c['status']!=1,
                                not_(table.c['resultCode'].like(u'1%'))
                            ),
                            not_(table.c['status'].in_([-1,0]))
                        )
                    )).select_from(table)
        failed_runs = db.session.connection().execute(s)
        for run in failed_runs:
            failed_runs_by_solver[run.SolverConfig_idSolverConfig].append(run)

    for solver in ranked_solvers:
        if runs_by_solver_and_instance.has_key(solver.idSolverConfig):
            successful_runs = [run for ilist in runs_by_solver_and_instance[solver.idSolverConfig].values() \
                                for run in ilist]
        else:
            successful_runs = []
        successful_runs_sum = sum(j.cost for j in successful_runs)

        penalized_average_runtime = 0.0
        if calculate_par10:
            if len(successful_runs) + len(failed_runs_by_solver[solver.idSolverConfig]) == 0:
                # this should mean there are no jobs of this solver yet
                penalized_average_runtime = 0.0
            else:
                penalized_average_runtime = (sum([j.cost_limit*10.0 for j in failed_runs_by_solver[solver.idSolverConfig]]) + successful_runs_sum) \
                                            / (len(successful_runs) + len(failed_runs_by_solver[solver.idSolverConfig]))

        avg_stddev_runtime = 0.0
        avg_cv = 0.0
        avg_qcd = 0.0
        if calculate_avg_stddev:
            count = 0
            for instance in instance_ids:
                if solver.idSolverConfig in finished_runs_by_solver_and_instance and finished_runs_by_solver_and_instance[solver.idSolverConfig].has_key(instance):
                    instance_runtimes = finished_runs_by_solver_and_instance[solver.idSolverConfig][instance]
                    runtimes = [j[0] for j in instance_runtimes]
                    stddev = numpy.std(runtimes)
                    avg_stddev_runtime += stddev
                    avg_cv += stddev / numpy.average(runtimes)
                    quantiles = mquantiles(runtimes, [0.25, 0.5, 0.75])
                    avg_qcd += (quantiles[2] - quantiles[0]) / quantiles[1]
                    count += 1
            if count > 0:
                avg_stddev_runtime /= float(count)
                avg_cv /= float(count)
                avg_qcd /= float(count)

        data.append((
            solver,
            len(successful_runs),
            0 if len(successful_runs) == 0 else len(successful_runs) / float(max_num_runs_per_solver),
            0 if vbs_num_solved == 0 else len(successful_runs) / float(vbs_num_solved),
            successful_runs_sum,
            numpy.average([j[0] for j in successful_runs] or 0),
            avg_stddev_runtime,
            avg_cv,
            avg_qcd,
            penalized_average_runtime
        ))

    #if calculate_par10: data.sort(key=lambda x: x[7])
    return data
