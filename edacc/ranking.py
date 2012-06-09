# -*- coding: utf-8 -*-
"""
    edacc.ranking
    -------------

    This module implements some possible ranking schemes that can be used
    by the ranking view in the analysis module.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""
import numpy, math
from scipy.stats.mstats import mquantiles
from itertools import izip

from sqlalchemy.sql import select, and_, functions, not_, expression

from edacc import statistics


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
                return sgn((results[s2.idSolverConfig][0] or 0.0) - (results[s1.idSolverConfig][0] or 0.0))
            else:
                return 0

    return list(sorted(solver_configs,cmp=comp,reverse=True))


def get_ranking_data(db, experiment, ranked_solvers, instances, calculate_par10, calculate_avg_stddev, cost):
    instance_ids = [i.idInstance for i in instances]
    solver_config_ids = [s.idSolverConfig for s in ranked_solvers]
    if not solver_config_ids: return [], None
    
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
    best_instance_runtimes = db.session.query(func.min(cost_property), db.ExperimentResult.Instances_idInstance) \
        .filter_by(experiment=experiment) \
        .filter(db.ExperimentResult.resultCode.like(u'1%')) \
        .filter(db.ExperimentResult.Instances_idInstance.in_(instance_ids)) \
        .filter(db.ExperimentResult.SolverConfig_idSolverConfig.in_(solver_config_ids)) \
        .group_by(db.ExperimentResult.Instances_idInstance).all()

    vbs_num_solved = len(best_instance_runtimes) * max_num_runs
    vbs_cumulated_cpu = sum(r[0] or 0.0 for r in best_instance_runtimes) * max_num_runs
    vbs_median = numpy.median([r[0] or 0.0 for r in best_instance_runtimes])
    best_runtime_by_instance = dict()
    for bir in best_instance_runtimes:
        best_runtime_by_instance[bir.Instances_idInstance] = bir[0]

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
                     vbs_median),
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

    vbs_uses_solver_count = dict((id, 0) for id in solver_config_ids)
    runs_by_solver_and_instance = {}
    for run in successful_runs:
        if not runs_by_solver_and_instance.has_key(run.SolverConfig_idSolverConfig):
            runs_by_solver_and_instance[run.SolverConfig_idSolverConfig] = {}
        if not runs_by_solver_and_instance[run.SolverConfig_idSolverConfig].has_key(run.Instances_idInstance):
            runs_by_solver_and_instance[run.SolverConfig_idSolverConfig][run.Instances_idInstance] = []
        runs_by_solver_and_instance[run.SolverConfig_idSolverConfig][run.Instances_idInstance].append(run)
        if run.cost == best_runtime_by_instance[run.Instances_idInstance]:
            vbs_uses_solver_count[run.SolverConfig_idSolverConfig] += 1

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

    failed_runs_by_solver = dict((sc.idSolverConfig, list()) for sc in ranked_solvers)
    s = select([expression.label('cost', cost_column),
                expression.label('cost_limit', cost_limit_column), table.c['SolverConfig_idSolverConfig']],
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
        successful_runs_sum = sum(j.cost or 0.0 for j in successful_runs)

        penalized_average_runtime = 0.0
        if calculate_par10:
            if len(successful_runs) + len(failed_runs_by_solver[solver.idSolverConfig]) == 0:
                # this should mean there are no jobs of this solver yet
                penalized_average_runtime = 0.0
            else:
                penalized_average_runtime = (sum([j.cost_limit*10.0 for j in failed_runs_by_solver[solver.idSolverConfig]]) + successful_runs_sum) \
                                            / (len(successful_runs) + len(failed_runs_by_solver[solver.idSolverConfig]))

        median_runtime = numpy.median([j.cost_limit for j in failed_runs_by_solver[solver.idSolverConfig]] + [j.cost for j in successful_runs])

        avg_stddev_runtime = 0.0
        avg_cv = 0.0
        avg_qcd = 0.0
        if calculate_avg_stddev:
            count = 0
            for instance in instance_ids:
                if solver.idSolverConfig in finished_runs_by_solver_and_instance and finished_runs_by_solver_and_instance[solver.idSolverConfig].has_key(instance):
                    instance_runtimes = finished_runs_by_solver_and_instance[solver.idSolverConfig][instance]
                    runtimes = [j[0] or 0.0 for j in instance_runtimes]
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
            #numpy.average([j[0] or 0.0 for j in successful_runs] or 0),
            median_runtime,
            avg_stddev_runtime,
            avg_cv,
            avg_qcd,
            penalized_average_runtime,
        ))

    #if calculate_par10: data.sort(key=lambda x: x[7])
    return data, vbs_uses_solver_count


def ranking_from_graph(M, edges, vertices, solver_config_ids):
    outedges_by_node = dict((v, list()) for v in vertices)
    for e in edges:
        outedges_by_node[e[0]].append(e)

    indices = dict((v, -1) for v in vertices)
    lowlinks = indices.copy()
    index = 0
    stack = []
    connected_components = []

    def strongly_connected(v, index):
        indices[v] = index
        lowlinks[v] = index
        index += 1
        stack.append(v)

        for v, w in outedges_by_node[v]:
            if indices[w] < 0:
                strongly_connected(w, index)
                lowlinks[v] = min(lowlinks[v], lowlinks[w])
            elif w in stack:
                lowlinks[v] = min(lowlinks[v], indices[w])

        if indices[v] == lowlinks[v]:
            connected_components.append([])
            while stack[-1] != v:
                connected_components[-1].append(stack.pop())
            connected_components[-1].append(stack.pop())

    for v in vertices:
        if indices[v] < 0:
            strongly_connected(v, index)

    scc_edges = set()
    for comp in connected_components:
        for s1 in comp:
            for s2 in solver_config_ids:
                if s1 == s2: continue
                if M[s1][s2] == 1 and s2 not in comp:
                    scc_edges.add((frozenset(comp), frozenset([c for c in connected_components if s2 in c][0])))

    def topological_sort():
        l = []
        visited = set()
        s = set()
        for comp in connected_components:
            outgoingEdges = False
            for edge in scc_edges:
                if frozenset(edge[0]) == frozenset(comp): outgoingEdges = True
            if not outgoingEdges:
                s.add(frozenset(comp))

        def visit(n):
            if n not in visited:
                visited.add(n)
                for edge in scc_edges:
                    if frozenset(edge[1]) == frozenset(n):
                        visit(frozenset(edge[0]))
                l.append(list(n))
        for n in s:
            visit(n)
        return l

    l = topological_sort()

    return l


def survival_ranking(db, experiment, instances, solver_configs, results, cost="resultTime"):
    instance_ids = [i.idInstance for i in instances]
    solver_config_ids = [s.idSolverConfig for s in solver_configs]
    sc_by_id = dict()
    for sc in solver_configs:
        sc_by_id[sc.idSolverConfig] = sc

    def values_tied(v1, v2, a=0.02):
        # Test if two values are tied, i.e. if the intervals [v1 - a*v1, v1 + a*v1]
        # and [v2 - a*v2, v2 + a*v2] overlap.
        if v1 > v2:
            if v2 + a * v2 > v1 - a * v1:
                return True
        else:
            if v1 + a * v1 > v2 - a * v2:
                return True

        return False

    # build the matrix of pairwise comparisons:
    # survival_winner[(solver1, solver2)] = 0 if no signficiant difference
    # survival_winner[(solver1, solver2)] = 1 if solver1 signif. better than solver2
    # and -1 otherwise
    survival_winner = dict()
    for s1 in solver_config_ids:
        for s2 in solver_config_ids:
            if (s1, s2) in survival_winner: continue
            survival_winner[(s1, s2)] = 0
            survival_winner[(s2, s1)] = 0
            if s1 == s2: continue

            runs_s1 = list()
            runs_s2 = list()
            runs_s1_censored = list()
            runs_s2_censored = list()
            # list of results of s1 and s2, tied pairs are replaced by their mean
            for idInstance in instance_ids:
                for run1, run2 in izip(results[idInstance][s1], results[idInstance][s2]):
                    if values_tied(run1.penalized_time1, run2.penalized_time1):
                        runs_s1.append((run1.penalized_time1 + run2.penalized_time1) / 2.0)
                        runs_s2.append((run1.penalized_time1 + run2.penalized_time1) / 2.0)
                    else:
                        runs_s1.append(run1.penalized_time1)
                        runs_s2.append(run2.penalized_time1)
                    runs_s1_censored.append(run1.censored)
                    runs_s2_censored.append(run2.censored)
            # calculate p-value of the survival-analysis hypothesis test
            p_value = statistics.surv_test(runs_s1, runs_s2, runs_s1_censored, runs_s2_censored)

            if p_value < 0.05:
                if numpy.median(runs_s1) > numpy.median(runs_s2):
                    # s2 better
                    survival_winner[(s1, s2)] = -1
                    survival_winner[(s2, s1)] = 1
                else:
                    # s1 better
                    survival_winner[(s1, s2)] = 1
                    survival_winner[(s2, s1)] = -1

    # build graph matrix
    edges_surv = set()
    vertices = set(solver_config_ids)
    M_surv = dict()
    for s1 in solver_config_ids:
        M_surv[s1] = dict()
        for s2 in solver_config_ids:
            if s1 == s2:
                M_surv[s1][s2] = 0
                continue
            M_surv[s1][s2] = 1 if survival_winner[(s1, s2)] == 1 else 0.5 if survival_winner[(s1, s2)] == 0 else 0
            if M_surv[s1][s2] == 1:
                edges_surv.add((s1, s2))
            elif M_surv[s1][s2] == 0.5:
                edges_surv.add((s1, s2))
                edges_surv.add((s2, s1))

    # find strongly connected components and sort topologically
    l_surv = ranking_from_graph(M_surv, edges_surv, vertices, solver_config_ids)

    return [[sc_by_id[sc] for sc in comp_surv] for comp_surv in l_surv], survival_winner, M_surv

def careful_ranking(db, experiment, instances, solver_configs, results, cost="resultTime", noise=1.0, break_ties=False):
    instance_ids = [i.idInstance for i in instances]
    solver_config_ids = [s.idSolverConfig for s in solver_configs]
    sc_by_id = dict()
    for sc in solver_configs:
        sc_by_id[sc.idSolverConfig] = sc

    alpha = math.sqrt(noise / 2.0)
    raw = dict()
    for s1 in solver_config_ids:
        for s2 in solver_config_ids:
            if (s1, s2) in raw: continue
            raw[(s1, s2)] = 0
            raw[(s2, s1)] = 0
            if s1 == s2: continue

            for idInstance in instance_ids:
                for r1, r2 in izip(results[idInstance][s1], results[idInstance][s2]):

                    e1 = (r1.penalized_time1 + r2.penalized_time1) / 2.0
                    delta = alpha * math.sqrt(e1)
                    if r1.penalized_time1 < e1 - delta:
                        raw[(s1, s2)] += 1
                        raw[(s2, s1)] -= 1
                    elif r2.penalized_time1 < e1 - delta:
                        raw[(s2, s1)] += 1
                        raw[(s1, s2)] -= 1

    edges = set()

    vertices = set(solver_config_ids)
    M = dict()
    for s1 in solver_config_ids:
        M[s1] = dict()
        for s2 in solver_config_ids:
            if s1 == s2:
                M[s1][s2] = 0
                continue
            M[s1][s2] = 1 if raw[(s1, s2)] > 0 else 0.5 if raw[(s1, s2)] == 0 else 0
            if M[s1][s2] == 1:
                edges.add((s1, s2))
            elif M[s1][s2] == 0.5:
                edges.add((s1, s2))
                edges.add((s2, s1))

    l = ranking_from_graph(M, edges, vertices, solver_config_ids)

    if break_ties:
        tie_break = dict()
        for comp in l:
            for solver in comp:
                tie_break[solver] = sum(raw[(solver, s_j)] for s_j in comp)
            comp.sort(key=lambda sc: tie_break[sc], reverse=True)

    return [[sc_by_id[sc] for sc in comp] for comp in l], raw, M