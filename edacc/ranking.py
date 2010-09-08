# -*- coding: utf-8 -*-
"""
    edacc.ranking
    -------------

    This module implements some possible ranking schemes that can be used
    by the ranking view in the analysis module.

    The ranking view handler calls the function :rank_solvers: of this module,
    which has to accept the experiment of which the solver configurations should
    be ranked as parameter and return a list with the solver configurations
    ordered from best to worst.

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
            res1 = [res.time if res.status == 1 else experiment.timeOut for res in experiment.results if res.solver_configuration == s1 and res.instance == i]
            res2 = [res.time if res.status == 1 else experiment.timeOut for res in experiment.results if res.solver_configuration == s2 and res.instance == i]
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
    """ TODO: use result properties to determine if an instance was actually
        solved.
    """
    return list(reversed(sorted(experiment.solver_configurations,
                                key=lambda s: len([r for r in experiment.results if r.status == 1]))))

rank_solvers = avg_point_biserial_correlation_ranking