import sys, tempfile, subprocess, os
sys.path.append("..")

from edacc import models, config, constants
from satchallenge_config import *

db = models.add_database(DB_USER, DB_PASSWORD, DB_NAME, DB_NAME)

SAT_verifier = "./SAT"

TEMP_DIR = '/tmp/satchallenge'
try:
    os.makedirs(TEMP_DIR)
except: pass

UNSAT = 10
SAT = 11

limits_by_experiment = {
    21: (900, -1, 6144),
    18: (900, -1, 6144),
    19: (900, -1, 6144),
    20: (-1, 900, 12288),
    24: (900, -1, 6144),
    25: (900, -1, 6144)
}

# check sequential experiments

for experiment_id in [19, 21, 18, 20, 24, 25]:
    experiment = db.session.query(db.Experiment).get(experiment_id)
    results_query = db.session.query(db.ExperimentResult).filter_by(experiment=experiment)
    num_jobs = results_query.count()

    print "Examining " + experiment.name + " with " + str(num_jobs) + " runs:"

    # Load runs and check if each job has the correct resource limits
    runs_by_instance = dict((i, list()) for i in experiment.instances)
    for ix, run in enumerate(results_query):
        if ix % 100 == 0: print ix, '/', num_jobs, '...'

        runs_by_instance[run.instance].append(run)
        if (run.CPUTimeLimit, run.wallClockTimeLimit, run.memoryLimit) != limits_by_experiment[experiment_id]:
            print "run " + str(run.idJob) + " has wrong limits!"


        if run.SolverConfig_idSolverConfig in (688, 793):
            if run.output.solverOutput and "Could not create the Java virtual machine" in run.output.solverOutput:
                print "run " + str(run.idJob) + " couldnt create JVM"

        continue

        if run.status == 1 and run.resultCode >= 0:
            # run verifier and check answer again.
            instance_path = os.path.join(TEMP_DIR, run.instance.md5)
            if not os.path.exists(instance_path):
                with open(os.path.join(instance_path), 'wb') as f: f.write(run.instance.get_instance(db))

            solver_output_path = os.path.join(TEMP_DIR, str(run.idJob))
            with open(os.path.join(solver_output_path), 'wb') as f: f.write(run.output.solverOutput)
            proc = subprocess.Popen([SAT_verifier, instance_path, solver_output_path], stdout=subprocess.PIPE)
            verifier_lines = proc.stdout.readlines()
            if int(verifier_lines[-1]) != run.resultCode:
                print "  [Job "+str(run.idJob)+"] Mismatch between old and new result code (" + str(run.resultCode) + ", " + str(int(verifier_lines[-1])) + ")"
            proc.wait()
            os.remove(solver_output_path)

    # check if there are both SAT and UNSAT answers for instances. Since we check SAT answers the UNSAT answers are wrong.
    for i in runs_by_instance:
        if any(run.resultCode == UNSAT for run in runs_by_instance[i]) and any(run.resultCode == SAT for run in runs_by_instance[i]):
            print "  For instance " + i.name + "("+i.md5+") there are both SAT and UNSAT answers"
            offending_solvers = set()
            for run in runs_by_instance[i]:
                if run.resultCode == UNSAT:
                    offending_solvers.add(run.solver_configuration)
            print "    Faulty solvers: " + ','.join([s.name for s in offending_solvers])



    print "-------------------------"

