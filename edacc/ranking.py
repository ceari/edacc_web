# -*- coding: utf-8 -*-
"""
    edacc.ranking
    -------------

    This module implements some possible ranking schemes that can be used
    by the ranking view in the analysis module.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

def avg_point_biserial_correlation_ranking(experiment):
    """ Ranking through comparison of the RTDs of the solvers on the instances.
        This ranking only makes sense if the there were multiple runs of each
        solver on each instance.
        See the paper "Statistical Methodology for Comparison of SAT Solvers"
        by M. Nikolić for details.
    """
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
        for i in experiment.instances:
            res1 = [res.get_time() for res in experiment.results \
                    if res.SolverConfig_idSolverConfig == s1.idSolverConfig \
                    and res.Instances_idInstance == i.idInstance]
            res2 = [res.get_time() for res in experiment.results \
                    if res.SolverConfig_idSolverConfig == s2.idSolverConfig \
                    and res.Instances_idInstance == i.idInstance]
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
    return list(reversed(sorted(experiment.solver_configurations, cmp=comp)))

def number_of_solved_instances_ranking(experiment):
    """ Ranking by the number of instances correctly solved.
        This is determined by an resultCode that starts with '1' and a 'finished' status
        of a job.
    """
    results = experiment.results
    def comp(s1, s2):
        solved_s1 = [res for res in results if res.solver_configuration == s1 and res.status == 1 and str(res.resultCode).startswith('1')]
        solved_s2 = [res for res in results if res.solver_configuration == s2 and res.status == 1 and str(res.resultCode).startswith('1')]
        num_solved_s1 = len(solved_s1)
        num_solved_s2 = len(solved_s2)
        if num_solved_s1 > num_solved_s2: return 1
        elif num_solved_s1 < num_solved_s2: return -1
        else:
            # break ties by cumulative CPU time over all solved instances
            return -1 * int(sum([res.get_time() for res in solved_s1]) - sum([res.get_time() for res in solved_s2]))

    return list(reversed(sorted(experiment.solver_configurations,cmp=comp)))