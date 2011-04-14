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
import scipy
from sqlalchemy.sql import select, and_, functions

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

    from scipy import stats
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
            ranked_data = list(stats.stats.rankdata(res1 + res2))

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

def number_of_solved_instances_ranking(db, experiment, instances):
    """ Ranking by the number of instances correctly solved.
        This is determined by an resultCode that starts with '1' and a 'finished' status
        of a job.
    """
    instance_ids = [i.idInstance for i in instances]

    table = db.metadata.tables['ExperimentResults']
    c_solver_config_id = table.c['SolverConfig_idSolverConfig']
    c_result_time = table.c['resultTime']
    c_experiment_id = table.c['Experiment_idExperiment']
    c_result_code = table.c['resultCode']
    c_status = table.c['status']
    c_instance_id = table.c['Instances_idInstance']

    s = select([c_solver_config_id, functions.sum(c_result_time), functions.count()], \
        and_(c_experiment_id==experiment.idExperiment, c_result_code.like(u'1%'), c_status==1,
             c_instance_id.in_(instance_ids))) \
        .select_from(table) \
        .group_by(c_solver_config_id)

    results = {}
    query_results = db.session.connection().execute(s)
    for row in query_results:
        results[row[0]] = (row[1], row[2])

    def comp(s1, s2):
        num_solved_s1, num_solved_s2 = 0, 0
        if results.has_key(s1.idSolverConfig):
            num_solved_s1 = results[s1.idSolverConfig][1]
        if results.has_key(s2.idSolverConfig):
            num_solved_s2 = results[s2.idSolverConfig][1]

        if num_solved_s1 > num_solved_s2: return 1
        elif num_solved_s1 < num_solved_s2: return -1
        else:
            # break ties by cumulative CPU time over all solved instances
            if results.has_key(s1.idSolverConfig) and results.has_key(s2.idSolverConfig):
                return -1 * int(results[s1.idSolverConfig][0] - results[s2.idSolverConfig][0])
            else:
                return 0

    return list(reversed(sorted(experiment.solver_configurations,cmp=comp)))

def get_ranking_data(db, experiment, ranked_solvers, instances, calculate_par10, calculate_avg_stddev):
    instance_ids = [i.idInstance for i in instances]
    solver_config_ids = [s.idSolverConfig for s in ranked_solvers]
    num_runs = experiment.get_num_runs(db)
    num_runs_per_solver = num_runs * len(instance_ids)

    vbs_num_solved = 0
    vbs_cumulated_cpu = 0
    from sqlalchemy import func, or_, not_
    best_instance_runtimes = db.session.query(func.min(db.ExperimentResult.resultTime)) \
        .filter_by(experiment=experiment) \
        .filter(db.ExperimentResult.resultCode.like(u'1%')) \
        .filter(db.ExperimentResult.Instances_idInstance.in_(instance_ids)) \
        .group_by(db.ExperimentResult.Instances_idInstance).all()

    vbs_num_solved = len(best_instance_runtimes) * num_runs
    vbs_cumulated_cpu = sum(r[0] for r in best_instance_runtimes) * num_runs

    num_unsolved_instances = len(instances) - len(best_instance_runtimes)

    #vbs_par10 = vbs_cumulated_cpu + 10.0 * experiment.CPUTimeLimit * num_unsolved_instances * num_runs
    #vbs_par10 = vbs_par10 / num_runs_per_solver if num_runs_per_solver != 0 else 0
    # TODO: make this work somehow with the new DB model (no more experiment.CPUTimeLimit)
    vbs_par10 = 0.0

    # Virtual best solver data
    data = [('Virtual Best Solver (VBS)',                   # name of the solver
             vbs_num_solved,                                # number of successful runs
             0.0 if num_runs_per_solver == 0 else \
                    vbs_num_solved / float(num_runs_per_solver) ,  # % of all runs
             1.0,                                           # % of vbs runs
             vbs_cumulated_cpu,                             # cumulated CPU time
             (0.0 if vbs_num_solved == 0 else \
                     vbs_cumulated_cpu / vbs_num_solved),   # average CPU time per successful run
             0.0, # avg stddev
             vbs_par10
             )]

    # single query fetch of all/most required data
    successful_runs = db.session.query(db.ExperimentResult.resultTime,
                                       db.ExperimentResult.SolverConfig_idSolverConfig,
                                       db.ExperimentResult.Instances_idInstance) \
                                .filter(db.ExperimentResult.resultCode.like(u'1%')) \
                                .filter(db.ExperimentResult.Instances_idInstance.in_(instance_ids)) \
                                .filter(db.ExperimentResult.SolverConfig_idSolverConfig.in_(solver_config_ids)) \
                                .filter_by(experiment=experiment, status=1).all()

    runs_by_solver_and_instance = {}
    for run in successful_runs:
        if not runs_by_solver_and_instance.has_key(run.SolverConfig_idSolverConfig):
            runs_by_solver_and_instance[run.SolverConfig_idSolverConfig] = {}
        if not runs_by_solver_and_instance[run.SolverConfig_idSolverConfig].has_key(run.Instances_idInstance):
            runs_by_solver_and_instance[run.SolverConfig_idSolverConfig][run.Instances_idInstance] = []
        runs_by_solver_and_instance[run.SolverConfig_idSolverConfig][run.Instances_idInstance].append(run)

    for solver in ranked_solvers:
        if runs_by_solver_and_instance.has_key(solver.idSolverConfig):
            successful_runs = [run for ilist in runs_by_solver_and_instance[solver.idSolverConfig].values() \
                                for run in ilist]
        else:
            successful_runs = []
        successful_runs_sum = sum(j.resultTime for j in successful_runs)

        penalized_average_runtime = 0.0
        if calculate_par10:
            failed_runs = db.session.query(db.ExperimentResult) \
                                    .filter_by(experiment=experiment, solver_configuration=solver) \
                                    .filter(or_(db.ExperimentResult.status != 1,
                                                not_(db.ExperimentResult.resultCode.like(u'1%')))) \
                                    .filter(db.ExperimentResult.Instances_idInstance.in_(instance_ids)).all()

            if len(successful_runs) + len(failed_runs) == 0:
                # this should mean there are no jobs of this solver yet
                penalized_average_runtime = 0.0
            else:
                penalized_average_runtime = (sum([j.CPUTimeLimit * 10.0 for j in failed_runs]) + successful_runs_sum) \
                                            / (len(successful_runs) + len(failed_runs))

        avg_stddev_runtime = 0.0
        if calculate_avg_stddev:
            count = 0
            for instance in instance_ids:
                if solver.idSolverConfig in runs_by_solver_and_instance and runs_by_solver_and_instance[solver.idSolverConfig].has_key(instance):
                    instance_runtimes = runs_by_solver_and_instance[solver.idSolverConfig][instance]
                    avg_stddev_runtime += scipy.std([j[0] for j in instance_runtimes])
                    count += 1
            if count > 0:
                avg_stddev_runtime /= float(count)
            else:
                avg_stddev_runtime = 0.0

        data.append((
            solver,
            len(successful_runs),
            0 if len(successful_runs) == 0 else len(successful_runs) / float(num_runs_per_solver),
            0 if vbs_num_solved == 0 else len(successful_runs) / float(vbs_num_solved),
            successful_runs_sum,
            numpy.average([j[0] for j in successful_runs] or 0),
            avg_stddev_runtime,
            penalized_average_runtime
        ))

    return data
