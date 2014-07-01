import sys
sys.path.append("..")

sys.path.append("/Users/ddiepold/edacc_web")
sys.path.append("/Users/ddiepold/edacc_web/scripts")
sys.path.append("..")
try:
    activate_this = '/Users/ddiepold/env2/bin/activate_this.py'
    execfile(activate_this, dict(__file__=activate_this))
except:
    pass

from edacc import models
from sqlalchemy.orm import joinedload_all
from sc14_config import *

db = models.add_database(DB_USER, DB_PASSWORD, DB_NAME, DB_NAME)

UNSAT = 10
SAT = 11

# check sequential experiments
for experiment_id in [19, 22]:
    experiment = db.session.query(db.Experiment).get(experiment_id)
    if not experiment: continue

    with open('experiment_' + str(experiment_id), 'w') as f:
        f.write('idJob,Solver,Instance,ResultCode,CPUTime,Verifier Wall Time,Verifier output\n')

        for job in db.session.query(db.ExperimentResult).options(joinedload_all('output')).\
                filter_by(experiment=experiment)\
                .order_by(db.ExperimentResult.SolverConfig_idSolverConfig):
            verification_time = -1
            verifier_status = ""
            for line in job.output.verifierOutput.split('\n'):
                if "Verification took" in line:
                    verification_time = int(line.split()[2])
                    if len(line.split()) > 6:
                        verifier_status = ' '.join(line.split()[6:8])

            f.write("%d,%s,%s,%d,%.2f,%d,%s\n" % (job.idJob, job.solver_configuration.name,
                                            job.instance.name, job.resultCode, job.resultTime,
                                            verification_time, verifier_status))
