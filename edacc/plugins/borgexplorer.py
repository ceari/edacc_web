"""
    Borg code by Bryan Silverthorn <bcs@cargo-cult.org>
    see LICENSE_borgexplorer
    http://nn.cs.utexas.edu/pages/research/borg/

    Adapted for the EDACC Web Frontend by Daniel Diepold.
"""

import scipy.special, scipy.optimize, scipy.stats
import scikits.learn.linear_model
import numpy
import os
import rpy2.robjects
import rpy2.robjects.numpy2ri
from functools import wraps
try: from cjson import encode as json_dumps
except:
    try: from simplejson import dumps as json_dumps
    except ImportError: from json import dumps as json_dumps

from flask import Module, abort, request
from flask import render_template as render
from sqlalchemy import not_

from edacc import models
from edacc.web import cache
from edacc.constants import STATUS_PROCESSING

from threading import Lock
global_lock = Lock()

def synchronized(f):
    """Thread synchronization decorator. Only allows exactly one thread
    to enter the wrapped function at any given point in time.
    """
    @wraps(f)
    def lockedfunc(*args, **kwargs):
        try:
            global_lock.acquire()
            return f(*args, **kwargs)
        finally:
            global_lock.release()
    return lockedfunc

borgexplorer = Module(__name__)

@borgexplorer.route('/<database>/experiment/<int:experiment_id>/borg-explorer/')
def borg_explorer(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    return render('borgexplorer/index.html', db=db, database=database, experiment=experiment)

@borgexplorer.route('/<database>/experiment/<int:experiment_id>/borg-explorer-data/')
def borg_explorer_data(database, experiment_id):
    db = models.get_database(database) or abort(404)
    experiment = db.session.query(db.Experiment).get(experiment_id) or abort(404)

    type = request.args.get('type')
    if type == 'categories.json':
        return json_dumps([{"path": experiment.name, "name": experiment.name}])

    @synchronized
    @cache.memoize(600)
    def get_data(database, experiment_id):
        runs = db.session.query(db.ExperimentResult) \
                                .filter(db.ExperimentResult.Experiment_idExperiment==experiment_id) \
                                .filter(not_(db.ExperimentResult.status.in_(STATUS_PROCESSING))).order_by('idJob').all()
        return CategoryData().fit([(0, r.instance.name, r.result_code.description, r.resultTime, 0, r.solver_configuration.name, 0) for r in runs])

    data = get_data(database, experiment_id)

    if type == 'runs.json':
        return json_dumps(data.table)
    elif type == 'solvers.json':
        return json_dumps(data.solvers)
    elif type == 'instances.json':
        return json_dumps(data.instances)
    elif type == 'membership.json':
        return json_dumps(data.model._tclass_res_LN.T.tolist())
    elif type == 'projection.json':
        return json_dumps(data.projection_N2.tolist())
    else:
        abort(404)

##############################################################################

def assert_probabilities(array):
    """Assert that an array contains only valid probabilities."""

    assert numpy.all(array >= 0.0)
    assert numpy.all(array <= 1.0)

def assert_log_probabilities(array):
    """Assert that an array contains only valid probabilities."""

    assert numpy.all(array <= 0.0)

def assert_weights(array, axis = None):
    """Assert than an array sums to one over a particular axis."""

    assert numpy.all(numpy.abs(numpy.sum(array, axis = axis) - 1.0 ) < 1e-6)

def fit_binomial_mixture(observed, counts, K):
    """Use EM to fit a discrete mixture."""

    concentration = 1e-8
    N = observed.shape[0]
    rates = (observed + concentration / 2.0) / (counts + concentration)
    components = rates[numpy.random.randint(N, size = K)]
    responsibilities = numpy.empty((K, N))
    old_ll = -numpy.inf

    for _ in xrange(512):
        # compute new responsibilities
        raw_mass = scipy.stats.binom.logpmf(observed[None, ...], counts[None, ...], components[:, None, ...])
        log_mass = numpy.sum(raw_mass, axis = 2)
        responsibilities = log_mass - numpy.logaddexp.reduce(log_mass, axis = 0)
        responsibilities = numpy.exp(responsibilities)
        weights = numpy.sum(responsibilities, axis = 1)
        weights /= numpy.sum(weights)
        ll = numpy.sum(numpy.logaddexp.reduce(numpy.log(weights)[:, None] + log_mass, axis = 0))

        if numpy.abs(ll - old_ll) <= 1e-3:
            break

        old_ll = ll

        # compute new components
        map_observed = observed[None, ...] * responsibilities[..., None]
        map_counts = counts[None, ...] * responsibilities[..., None]
        components = numpy.sum(map_observed, axis = 1) + concentration / 2.0
        components /= numpy.sum(map_counts, axis = 1) + concentration

        # split duplicates
        for j in xrange(K):
            for k in xrange(K):
                if j != k and numpy.sum(numpy.abs(components[j] - components[k])) < 1e-6:
                    components[j] = rates[numpy.random.randint(N)]
                    old_ll = -numpy.inf

    assert numpy.all(components >= 0.0)
    assert numpy.all(components <= 1.0)

    return (components, weights, responsibilities, ll)

def inverse_digamma(x):
    """Return the (approximate) inverse of the digamma function."""

    if x >= -2.22:
        y0 = numpy.exp(x) + 0.5
    else:
        y0 = -1.0 / (x - scipy.special.digamma(1.0))

    f = lambda y: scipy.special.digamma(y) - x
    f_ = lambda y: scipy.special.polygamma(1, y)

    return scipy.optimize.newton(f, y0, fprime = f_)

def fit_dirichlet(vectors, weights):
    """Compute the maximum-likelihood Dirichlet distribution."""

    log_pbar_k = numpy.sum(weights[:, None, None] * numpy.log(vectors), axis = 0) / numpy.sum(weights)
    alpha = numpy.random.random(vectors.shape[1:])
    alpha /= numpy.sum(alpha, axis = 1)[:, None]
    last_alpha = alpha

    for _ in xrange(64):
        psi_total = scipy.special.digamma(numpy.sum(alpha, axis = 1))
        psi_alpha = psi_total[:, None] + log_pbar_k

        alpha = numpy.array([[inverse_digamma(x) for x in row.flatten()] for row in psi_alpha])
        alpha = alpha.reshape(psi_alpha.shape)

        if numpy.sum(numpy.abs(alpha - last_alpha)) <= 1e-10:
            break

        last_alpha = alpha

    return alpha

def fit_dirichlet_vfixed(vectors, weights, variance):
    """Compute the maximum-likelihood Dirichlet distribution with fixed concentration."""

    log_pbar_k = numpy.sum(weights[:, None, None] * numpy.log(vectors), axis = 0) / numpy.sum(weights)
    alpha = numpy.random.random(vectors.shape[1:])
    alpha /= numpy.sum(alpha, axis = 1)[:, None]
    last_alpha = alpha

    for _ in xrange(64):
        psi_full = scipy.special.digamma(variance * alpha)
        psi_sigma = numpy.sum(alpha * (log_pbar_k - psi_full), axis = -1)
        psi_alpha = log_pbar_k - psi_sigma[..., None]

        alpha = numpy.array([[inverse_digamma(x) for x in row.flatten()] for row in psi_alpha])
        alpha = alpha.reshape(psi_alpha.shape)
        alpha /= numpy.sum(alpha, axis = -1)[..., None]

        if numpy.sum(numpy.abs(alpha - last_alpha)) <= 1e-10:
            break

        last_alpha = alpha

    return alpha * variance

def dirichlet_log_pdf(vectors, alphas):
    """Compute the Dirichlet log PDF."""

    vectors = numpy.asarray(vectors)
    alphas = numpy.asarray(alphas)

    term_a = scipy.special.gammaln(numpy.sum(alphas, axis = -1))
    term_b = numpy.sum(scipy.special.gammaln(alphas), axis = -1)
    term_c = numpy.sum((alphas - 1.0) * numpy.log(vectors), axis = -1)

    return term_a - term_b + term_c

def dcm_pdf(vector, alpha):
    """Compute the DCM PDF."""

    sum_alpha = numpy.sum(alpha, axis = -1)
    sum_vector = numpy.sum(vector, axis = -1)

    term_l = scipy.special.gamma(sum_alpha) / scipy.special.gamma(sum_alpha + sum_vector)
    term_r = numpy.prod(scipy.special.gamma(vector + alpha) / scipy.special.gamma(alpha), axis = -1)

    return term_l * term_r

def dcm_draw_pdf(k, alpha):
    """Compute the DCM PDF of a single draw."""

    sum_alpha = numpy.sum(alpha, axis = -1)
    alpha_plus = numpy.copy(alpha)

    alpha_plus[k] += 1.0

    term_l = scipy.special.gamma(sum_alpha) / scipy.special.gamma(sum_alpha + 1.0)
    term_r = numpy.prod(scipy.special.gamma(alpha_plus) / scipy.special.gamma(alpha), axis = -1)

    return term_l * term_r

def fit_dirichlet_mixture(vectors, K):
    """Use EM to fit a Dirichlet mixture."""

    # hackishly regularize our input vectors
    vectors = vectors + 1e-6
    vectors /= numpy.sum(vectors, axis = -1)[..., None]

    # then do EM
    N = vectors.shape[0]
    components = vectors[numpy.random.randint(N, size = K)]
    responsibilities = numpy.empty((K, N))
    old_ll = -numpy.inf

    for _ in xrange(512):
        # compute new responsibilities
        raw_mass = dirichlet_log_pdf(vectors[None, ...], components[:, None, ...])
        log_mass = numpy.sum(raw_mass, axis = 2)
        responsibilities = log_mass - numpy.logaddexp.reduce(log_mass, axis = 0)
        responsibilities = numpy.exp(responsibilities)
        weights = numpy.sum(responsibilities, axis = 1)
        weights /= numpy.sum(weights)
        ll = numpy.sum(numpy.logaddexp.reduce(numpy.log(weights)[:, None] + log_mass, axis = 0))


        # check for termination
        if numpy.abs(ll - old_ll) <= 1e-3:
            break

        old_ll = ll

        # compute new components
        for k in xrange(K):
            components[k] = fit_dirichlet(vectors, responsibilities[k])

        for j in xrange(K):
            for k in xrange(K):
                if j != k and numpy.sum(numpy.abs(components[j] - components[k])) < 1e-6:
                    components[j] = vectors[numpy.random.randint(N)]
                    old_ll = -numpy.inf

    return (components, weights)

class BilevelModel(object):
    """Two-level mixture model."""

    def __init__(self, successes, attempts):
        """Fit the model to data."""

        # mise en place
        (N, S, B) = successes.shape

        successes_NSB = successes
        attempts_NSB = attempts

        K = 8
        task_mixes_NSK = numpy.empty((N, S, K))
        self._inner_SKB = numpy.empty((S, K, B))

        for s in xrange(S):
            fit = lambda: fit_binomial_mixture(successes_NSB[:, s], attempts_NSB[:, s], K)
            (self._inner_SKB[s], _, responsibilities_KN, _) = \
                max(
                    [fit() for _ in xrange(4)],
                    key = lambda x: x[-1],
                    )
            task_mixes_NSK[:, s] = responsibilities_KN.T

        L = 16
        (self._outer_LSK, self._outer_weights_L) = fit_dirichlet_mixture(task_mixes_NSK, L)


    def predict(self, failures):
        """Return probabilistic predictions of success."""

        # mise en place
        F = len(failures)
        (L, _, K) = self._outer_LSK.shape

        # compute task class likelihoods
        tclass_weights_L = numpy.log(self._outer_weights_L)

        for l in xrange(L):
            tclass_weights_L[l] += self._lnp_failures_tclass(failures, l)

        tclass_weights_L = numpy.exp(tclass_weights_L - numpy.logaddexp.reduce(tclass_weights_L))

        assert_probabilities(tclass_weights_L)
        assert_weights(tclass_weights_L)

        # condition the task classes
        conditioned_LSK = numpy.copy(self._outer_LSK)

        for l in xrange(L):
            for f in xrange(F):
                (s, b) = failures[f]
                conditioning_K = numpy.zeros(K)

                for k in xrange(K):
                    p_f = 1.0 - self._inner_SKB[s, k, b]
                    p_z = dcm_draw_pdf(k, self._outer_LSK[l, s])

                    conditioning_K[k] += p_f * p_z

                conditioning_K /= numpy.sum(conditioning_K)
                conditioned_LSK[l, s] += conditioning_K

        # compute posterior probabilities
        tclass_means_LSK = conditioned_LSK / numpy.sum(conditioned_LSK, axis = -1)[..., None]
        tclass_rates_LSB = numpy.sum(tclass_means_LSK[..., None] * self._inner_SKB[None, ...], axis = -2)
        posterior_mean_SK = numpy.sum(tclass_weights_L[:, None, None] * tclass_means_LSK, axis = 0)
        posterior_rates_SB = numpy.sum(posterior_mean_SK[..., None] * self._inner_SKB, axis = 1)

        return (posterior_rates_SB, tclass_weights_L, tclass_rates_LSB)

    def _lnp_failures_tclass(self, failures, l):
        """Return p(failures | task class l)."""

        return sum(self._lnp_failure_tclass(failure, l) for failure in failures)

    def _lnp_failure_tclass(self, failure, l):
        """Return p(s@c failed | task class l)."""

        (s, b) = failure
        (_, _, K) = self._outer_LSK.shape
        sigma = -numpy.inf

        for k in xrange(K):
            lnp_l = numpy.log(1.0 - self._inner_SKB[s, k, b])
            lnp_r = numpy.log(dcm_draw_pdf(k, self._outer_LSK[l, s]))
            sigma = numpy.logaddexp(sigma, lnp_l + lnp_r)

        return sigma

def multinomial_log_mass(counts, total_counts, beta):
    """Compute multinomial log probability."""

    assert_probabilities(beta)
    assert_weights(beta, axis = -1)

    log_mass = numpy.sum(counts * numpy.log(beta), axis = -1)
    log_mass += scipy.special.gammaln(total_counts + 1.0)
    log_mass -= numpy.sum(scipy.special.gammaln(counts + 1.0), axis = -1)

    assert_log_probabilities(log_mass)

    return log_mass

def multinomial_log_mass_implied(counts, total_counts, beta):
    """Compute multinomial log probability; final parameter is implied."""

    assert_probabilities(beta)

    implied_p = 1.0 - numpy.sum(beta, axis = -1)
    implied_counts = total_counts - numpy.sum(counts, axis = -1)

    log_mass = numpy.sum(counts * numpy.log(beta), axis = -1)
    log_mass += implied_counts * numpy.log(implied_p)
    log_mass += scipy.special.gammaln(total_counts + 1.0)
    log_mass -= numpy.sum(scipy.special.gammaln(counts + 1.0), axis = -1)
    log_mass -= scipy.special.gammaln(implied_counts + 1.0)

    assert_log_probabilities(log_mass)

    return log_mass

def fit_multinomial_mixture(successes, attempts, K):
    """Fit a discrete mixture using EM."""

    # mise en place
    (N, B) = successes.shape

    successes_NB = successes
    attempts_N = attempts

    # expectation maximization
    previous_ll = -numpy.inf
    prior_alpha = 1.0 + 1e-2
    prior_beta = 1.0 + 1e-1
    prior_upper = prior_alpha - 1.0
    prior_lower = B * prior_alpha + prior_beta - B - 1.0
    initial_n_K = numpy.random.randint(N, size = K)
    components_KB = successes_NB[initial_n_K] + prior_upper
    components_KB /= (attempts_N[initial_n_K] + prior_lower)[:, None]

    for _ in xrange(512):
        # compute new responsibilities
        log_mass_KN = multinomial_log_mass_implied(successes_NB[None, ...], attempts_N[None, ...], components_KB[:, None, ...])

        log_responsibilities_KN = numpy.copy(log_mass_KN)
        log_responsibilities_KN -= numpy.logaddexp.reduce(log_responsibilities_KN, axis = 0)

        responsibilities_KN = numpy.exp(log_responsibilities_KN)

        log_weights_K = numpy.logaddexp.reduce(log_responsibilities_KN, axis = 1)
        log_weights_K -= numpy.log(N)

        # compute ll and check for convergence
        ll = numpy.logaddexp.reduce(log_weights_K[:, None] + log_mass_KN, axis = 0)
        ll = numpy.sum(ll)

        if numpy.abs(ll - previous_ll) <= 1e-4:
            break

        previous_ll = ll

        # compute new components
        weighted_successes_KNB = successes_NB[None, ...] * responsibilities_KN[..., None]
        weighted_attempts_KN = attempts_N[None, ...] * responsibilities_KN

        components_KB = numpy.sum(weighted_successes_KNB, axis = 1) + prior_upper
        components_KB /= (numpy.sum(weighted_attempts_KN, axis = 1) + prior_lower)[:, None]

        # split duplicates
        for j in xrange(K):
            for k in xrange(K):
                if j != k and numpy.sum(numpy.abs(components_KB[j] - components_KB[k])) < 1e-6:
                    previous_ll = -numpy.inf
                    n = numpy.random.randint(N)
                    components_KB[k] = successes_NB[n] + prior_upper
                    components_KB[k] /= attempts_N[n] + prior_lower

    assert_probabilities(components_KB)

    return (components_KB, responsibilities_KN, log_mass_KN, ll)

def fit_multinomial_outer_mixture(rclass_res, rclass_mass, L):
    """Fit a discrete mixture using EM."""

    # mise en place
    (_, _, N) = rclass_res.shape

    rclass_res_SKN = rclass_res
    rclass_res_NSK = rclass_res_SKN.swapaxes(0, 2).swapaxes(1, 2)
    rclass_log_mass_SKN = rclass_mass
    rclass_log_mass_NSK = rclass_log_mass_SKN.swapaxes(0, 2).swapaxes(1, 2)

    # expectation maximization
    previous_ll = -numpy.inf
    prior_alpha = 1.0 + 1e-2
    initial_n_L = numpy.random.randint(N, size = L)
    components_LSK = rclass_res_NSK[initial_n_L]

    for _ in xrange(1024):
        # compute new responsibilities
        log_components_LSK = numpy.log(components_LSK)

        log_mass_LNS = numpy.logaddexp.reduce(rclass_log_mass_NSK[None, ...] + log_components_LSK[:, None, ...], axis = -1)
        log_mass_LN = numpy.sum(log_mass_LNS, axis = -1)

        log_responsibilities_LN = numpy.copy(log_mass_LN)
        log_responsibilities_LN -= numpy.logaddexp.reduce(log_responsibilities_LN, axis = 0)

        responsibilities_LN = numpy.exp(log_responsibilities_LN)

        log_weights_L = numpy.logaddexp.reduce(log_responsibilities_LN, axis = 1)
        log_weights_L -= numpy.log(N)

        # compute ll and check for convergence
        ll = numpy.sum(numpy.logaddexp.reduce(log_weights_L[:, None] + log_mass_LN, axis = 0))

        if numpy.abs(ll - previous_ll) < 1e-6:
            break

        previous_ll = ll

        # compute new components
        weighted_rclass_res_LNSK = rclass_res_NSK[None, ...] * responsibilities_LN[..., None, None]

        components_LSK = numpy.sum(weighted_rclass_res_LNSK, axis = 1) + prior_alpha - 1.0
        components_LSK /= numpy.sum(components_LSK, axis = -1)[..., None]

        # split duplicates
        for l in xrange(L):
            for m in xrange(L):
                if l != m and numpy.sum(numpy.abs(components_LSK[l] - components_LSK[m])) < 1e-6:
                    previous_ll = -numpy.inf
                    n = numpy.random.randint(N)
                    components_LSK[l] = rclass_res_NSK[n]

    weights_L = numpy.exp(log_weights_L)

    return (components_LSK, weights_L, responsibilities_LN, ll)

class BilevelMultinomialModel(object):
    """Two-level multinomial mixture model."""

    def __init__(self, successes, attempts, features = None):
        """Fit the model to data."""

        # mise en place
        (N, S, B) = successes.shape

        successes_NSB = successes
        attempts_NS = attempts

        # fit the solver behavior classes

        K = 8
        self._rclass_SKB = numpy.empty((S, K, B))
        rclass_res = numpy.empty((S, K, N))
        rclass_mass = numpy.empty((S, K, N))

        for s in xrange(S):
            fit = lambda: fit_multinomial_mixture(successes_NSB[:, s], attempts_NS[:, s], K)
            (self._rclass_SKB[s], rclass_res[s], rclass_mass[s], _) = \
                max(
                    [fit() for _ in xrange(4)],
                    key = lambda x: x[-1],
                    )

        # fit the task mixture classes

        L = 15
        (self._tclass_LSK, self._tclass_weights_L, self._tclass_res_LN, _) = \
            fit_multinomial_outer_mixture(
                rclass_res,
                rclass_mass,
                L,
                )

        # fit the classifier
        if features is None:

            self._classifier = None
        else:

            train_x = []
            train_y = []

            for (n, task_features) in enumerate(features):
                counts_L = numpy.round(self._tclass_res_LN[:, n] * 100.0).astype(int)

                train_x.extend([task_features] * numpy.sum(counts_L))

                for l in xrange(L):
                    train_y.extend([l] * counts_L[l])

            self._classifier = scikits.learn.linear_model.LogisticRegression()

            self._classifier.fit(train_x, train_y)

    def predict(self, failures, features = ()):
        """Return probabilistic predictions of success."""

        # mise en place
        _ = len(failures)
        (L, _, _) = self._tclass_LSK.shape

        # let the classifier seed our cluster probabilities
        if len(features) > 1:
            (tclass_lr_weights_L,) = self._classifier.predict_proba([features])

            tclass_lr_weights_L += 1e-6
            tclass_lr_weights_L /= numpy.sum(tclass_lr_weights_L)
        else:
            tclass_lr_weights_L = self._tclass_weights_L

        # compute conditional tclass probabilities
        rclass_fail_cmf_SKB = numpy.cumsum(1.0 - self._rclass_SKB, axis = -1)
        tclass_post_weights_L = numpy.log(tclass_lr_weights_L)

        for l in xrange(L):
            for (s, b) in failures:
                p = numpy.sum(rclass_fail_cmf_SKB[s, :, b] * self._tclass_LSK[l, s])

                tclass_post_weights_L[l] += numpy.log(p)

        tclass_post_weights_L -= numpy.logaddexp.reduce(tclass_post_weights_L)
        tclass_post_weights_L = numpy.exp(tclass_post_weights_L)

        # compute per-tclass conditional rclass probabilities
        conditional_LSK = numpy.log(self._tclass_LSK)

        for l in xrange(L):
            for (s, b) in failures:
                conditional_LSK[l, s, :] += rclass_fail_cmf_SKB[s, :, b]

        conditional_LSK -= numpy.logaddexp.reduce(conditional_LSK, axis = -1)[..., None]
        conditional_LSK = numpy.exp(conditional_LSK)

        # compute posterior probabilities
        tclass_post_rates_LSB = numpy.sum(conditional_LSK[..., None] * self._rclass_SKB[None, ...], axis = -2)
        #_ = numpy.sum(tclass_post_weights_L[:, None, None] * tclass_post_rates_LSB, axis = 0)

        return (tclass_post_weights_L, tclass_post_rates_LSB)



class CategoryData(object):
    """Data for a category."""

    def fit(self, runs, budget_interval=100, budget_count=61):
        """ Fit data for a category.
            runs is expected to be a list of tuples of the format
            (_, instanceName, resultCodeDescription, cost, _, solverName, _)
            where '_' denotes currently unused entries
        """

        #runs = numpy.recfromcsv(runs_path, usemask = True).tolist()

        # build the indices
        solver_index = {}
        instance_index = {}

        for (_, instance, _, _, _, solver_name, _) in runs:
            instance_name = os.path.basename(instance)

            if instance_name not in instance_index:
                instance_index[instance_name] = len(instance_index)
            if solver_name not in solver_index:
                solver_index[solver_name] = len(solver_index)

        S = len(solver_index)
        N = len(instance_index)
        B = budget_count

        self.solvers = sorted(solver_index, key = lambda k: solver_index[k])
        self.instances = sorted(instance_index, key = lambda k: instance_index[k])

        # build the matrices
        budgets = [b * budget_interval for b in xrange(1, B + 1)]
        max_cost = budget_interval * budget_count
        attempts = numpy.zeros((N, S))
        costs = numpy.zeros((N, S))
        successes = numpy.zeros((N, S))
        answers = numpy.zeros((N, S))
        binned_successes = numpy.zeros((N, S, B))

        for (_, instance, answer, cost, _, solver_name, _) in runs:
            s = solver_index[solver_name]
            n = instance_index[os.path.basename(instance)]

            if attempts[n, s] == 0.0: # XXX support multiple runs
                attempts[n, s] = 1.0
                costs[n, s] = cost

                if cost <= max_cost and answer in ('SAT', 'UNSAT'):
                    b = numpy.digitize([cost], budgets)

                    successes[n, s] += 1.0
                    binned_successes[n, s, b] += 1.0

                    if answer == "SAT":
                        answers[n, s] = 1.0
                    elif answer == "UNSAT":
                        answers[n, s] = -1.0
                    else:
                        raise RuntimeError("unrecognized answer {0}".format(answer))

        # fit the model
        self.model = BilevelMultinomialModel(binned_successes, attempts)

        # build the mean-cost table
        self.table = []

        for n in xrange(N):
            task_runs_list = []

            for s in xrange(S):
                if answers[n, s] == 0.0:
                    answer = None
                elif answers[n, s] == 1.0:
                    answer = True
                else:
                    answer = False

                task_runs_list.append({
                    "solver": self.solvers[s],
                    "cost": costs[n, s],
                    "answer": answer
                    })

            self.table.append({
                "instance": self.instances[n],
                "runs": task_runs_list,
                })

        # generate cluster projection
        self.similarity_NN = numpy.empty((N, N))

        for m in xrange(N):
            for n in xrange(N):
                rm_SK = numpy.sum(self.model._tclass_res_LN[:, m][:, None, None] * self.model._tclass_LSK, axis = 0)
                rn_SK = numpy.sum(self.model._tclass_res_LN[:, n][:, None, None] * self.model._tclass_LSK, axis = 0)

                self.similarity_NN[m, n] = numpy.sum(rm_SK * numpy.log(rm_SK / rn_SK))

        self.projection_N2 = numpy.array(rpy2.robjects.r["cmdscale"](1.0 - self.similarity_NN))

        return self
