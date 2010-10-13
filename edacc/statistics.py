# -*- coding: utf-8 -*-
"""
    edacc.statistics
    ----------------

    Various statistics functions.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

from rpy2 import robjects
from rpy2.robjects.packages import importr

r_stats = importr('stats')

def prob_domination(v1, v2):
    """ Returns an integer indicating if the empirical CDF of Algorithm A
        obtained from the runtimes vector v1 probabilistically dominates
        the empirical CDF obtained from v2 (return 1), or the other way around
        (return -1), or if there are crossovers (return 0).
        Algorithm A probabilistically dominates algorithm B, iff.
        1) \forall t: P(RT_A <= t) >= P(RT_B <= t)
        2) \exists t: P(RT_A <= t) > P(RT_B <= t)
    """

    ecdf1 = robjects.r.ecdf(robjects.FloatVector(v1))
    ecdf2 = robjects.r.ecdf(robjects.FloatVector(v2))
    paired = zip([ecdf1(x)[0] for x in v1 + v2], [ecdf2(x)[0] for x in v1 + v2])

    if all(a >= b for a, b in paired) and any(a > b for a, b in paired):
        return 1
    if all(b >= a for a, b in paired) and any(b > a for a, b in paired):
        return -1

    return 0


def spearman_correlation(x, y):
    """ Calculates the spearman rank correlation coefficient.
        Returns a tuple (rho, p-value)
    """
    try:
        r = r_stats.cor_test(robjects.FloatVector(x), robjects.FloatVector(y),
                             method='spearman')
    except Exception:
        return 0.0, 1.0
    cor, p_value = r[3][0], r[2][0] # r is a vector of vectors
    return cor, p_value

def pearson_correlation(x, y):
    """ Calculates the pearson correlation coefficient.
        Returns a tuple (rho, p-value)
    """
    try:
        r = r_stats.cor_test(robjects.FloatVector(x), robjects.FloatVector(y),
                             method='pearson')
    except Exception:
        return 0.0, 1.0
    cor, p_value = r[3][0], r[2][0] # r is a vector of vectors
    return cor, p_value

def kolmogorow_smirnow_2sample_test(x, y):
    """ Calculates the Kolmogorow-Smirnow two-sample statistic
        Returns a tuple (value, p-value)
    """
    r = r_stats.ks_test(robjects.FloatVector(x), robjects.FloatVector(y),
                        alternative='two.sided')
    return r[0][0], r[1][0]

def wilcox_test(x, y):
    """ Calculates the two sample Wilcoxon test statistic (aka Mann-Whitney)
        Returns a tuple (value, p-value)
    """
    r = r_stats.wilcox_test(robjects.FloatVector(x), robjects.FloatVector(y),
                            alternative='two.sided', paired=False)
    return r[0][0], r[2][0]