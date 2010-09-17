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

def prob_domination(v1, v2):
    """ Returns an integer indicating if the empirical CDF of Algorithm A
        obtained from the runtimes vector v1 probabilistically dominates
        the empirical CDF obtained from v2 (return 1), or the other way around
        (return -1), or if there are crossovers (return 0).
        Algorithm A probabilistically dominates algorithm B, iff.
        1) \forall t: P(RT_A <= t) >= P(RT_B <= t)
        2) \exists t: P(RT_A <= t) > P(RT_B <= t)

        The t's to be checked can be constrained to those where the probability
        P(RT_A <= t) actually changes, which is exactly v1.
    """

    ecdf1 = robjects.r.ecdf(robjects.FloatVector(v1))
    ecdf2 = robjects.r.ecdf(robjects.FloatVector(v2))
    paired = zip([ecdf1(x)[0] for x in v1], [ecdf2(x)[0] for x in v1])

    if all(a >= b for a, b in paired) and any(a > b for a, b in paired):
        return 1
    elif all(b >= a for a, b in paired) and any(b > a for a, b in paired):
        return -1
    else:
        return 0