import sys, tempfile, subprocess, os
sys.path.append("..")

sys.path.append("/srv/edacc_web")
sys.path.append("/srv/edacc_web/scripts")
sys.path.append("..")
try:
    activate_this = '/srv/edacc_web/env/bin/activate_this.py'
    execfile(activate_this, dict(__file__=activate_this))
except:
    pass

from edacc import models, config, constants
from sc14_config import *

db = models.add_database(DB_USER, DB_PASSWORD, DB_NAME, DB_NAME)

UNSAT = 10
SAT = 11

# check sequential experiments

for experiment_id in range(17, 31):
    experiment = db.session.query(db.Experiment).get(experiment_id)
    if not experiment: continue
    results_query = db.session.query(db.ExperimentResult).filter_by(experiment=experiment)
    num_jobs = results_query.count()

    print "Examining " + experiment.name + " with " + str(num_jobs) + " runs:"

    # Load runs and check if each job has the correct resource limits
    runs_by_instance = dict((i, list()) for i in experiment.instances)
    for ix, run in enumerate(results_query):
        if ix % 100 == 0: print ix, '/', num_jobs, '...'

        runs_by_instance[run.instance].append(run)

    wrong_runs = list()
    # check if there are both SAT and UNSAT answers for instances. Since we check SAT answers the UNSAT answers are wrong.
    for i in runs_by_instance:
        if any(run.resultCode == UNSAT for run in runs_by_instance[i]) and any(run.resultCode == SAT for run in runs_by_instance[i]):
            print "  For instance " + i.name + "("+i.md5+") there are both SAT and UNSAT answers"
            offending_solvers = set()
            for run in runs_by_instance[i]:
                if run.resultCode == UNSAT:
                    wrong_runs.append(run.idJob)
                    offending_solvers.add(run.solver_configuration)
            print "    Faulty solvers: " + ','.join([s.name for s in offending_solvers])

    print "wrong runs: ", ' OR '.join('idJob=%d' % (idJob) for idJob in wrong_runs)

    print "-------------------------"

