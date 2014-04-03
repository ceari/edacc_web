import sys, os, zipfile, tempfile, hashlib, random

random.seed(5836592735)

sys.path.append("/srv/edacc_web")
sys.path.append("/srv/edacc_web/scripts")
sys.path.append("..")
try:
    activate_this = '/srv/edacc_web/env/bin/activate_this.py'
    execfile(activate_this, dict(__file__=activate_this))
except:
    pass

from sqlalchemy.sql import func

from edacc import models, config, constants
from satcomp13_config import *

db = models.add_database(DB_USER, DB_PASSWORD, DB_NAME, DB_NAME)

competition_experiments = {
    "Core solvers, Sequential, Application SAT":                            (17, 5000, -1, 7500),
    "Core solvers, Sequential, Application certified UNSAT":                (18, 5000, -1, 7500),
    "Core solvers, Sequential, Application SAT+UNSAT":                      (19, 5000, -1, 7500),
    "Core solvers, Sequential, Hard-combinatorial SAT":                     (20, 5000, -1, 7500),
    "Core solvers, Sequential, Hard-combinatorial certified UNSAT":         (21, 5000, -1, 7500),
    "Core solvers, Sequential, Hard-combinatorial SAT+UNSAT":               (22, 5000, -1, 7500),
    "Core solvers, Sequential, Random SAT":                                 (23, 5000, -1, 7500),
    "Core solvers, Sequential, Random certified UNSAT":                     (24, 5000, -1, 7500),
    "Core solvers, Sequential, Random SAT+UNSAT":                           (25, 5000, -1, 7500),
    "Core solvers, Parallel, Application SAT+UNSAT":                        (26, -1, 5000, 15000),
    "Core solvers, Parallel, Hard-combinatorial SAT+UNSAT":                 (27, -1, 5000, 15000),
    "Core solvers, Parallel, Random SAT":                                   (28, -1, 5000, 15000),
    "Open track":                                                           (29, -1, 5000, 15000),
    "Core solvers, Sequential, MiniSAT Hack-track, Application SAT+UNSAT":  (30, 5000, -1, 7500),
}

def add_solver_config(competition_category, solver_binary):
    if competition_category.name not in competition_experiments: return
    experiment_info = competition_experiments[competition_category.name]
    experiment = db.session.query(db.Experiment).get(experiment_info[0])

    # create solver configuration
    solver_config = db.SolverConfiguration()
    solver_config.name = solver.name
    solver_config.seed_group = None
    solver_config.experiment = experiment
    solver_config.solver_binary = solver_binary
    solver_config.hint = ""
    for parameter in solver.parameters:
        pi = db.ParameterInstance()
        pi.parameter = parameter
        pi.value = str(parameter.defaultValue) if parameter.hasValue else ""
        solver_config.parameter_instances.append(pi)
    db.session.add(solver_config)

    # generate testing jobs, one for each instance
    # for instance in experiment.instances:
    #     run = db.ExperimentResult()
    #     run.experiment = experiment
    #     run.instance = instance
    #     run.solver_configuration = solver_config
    #     run.run = 0
    #     run.seed = random.randint(1, 123456789)
    #     run.status = -1
    #     run.resultCode = 0
    #     run.priority = -1
    #     run.CPUTimeLimit = experiment_info[1]
    #     run.wallClockTimeLimit = experiment_info[2]
    #     run.memoryLimit = experiment_info[3]
    #     run.stackSizeLimit = -1
    #     run.output = db.ExperimentResultOutput()
    #     db.session.add(run)

    try:
        db.session.commit()
        return solver_config
    except Exception as e:
        db.session.rollback()
        print e
        sys.exit(1)


if __name__ == "__main__":
    for solver in db.session.query(db.Solver):
        if solver.user is None: continue

        competition_exp_ids = [i[0] for i in competition_experiments.values()]
        test_exp_ids = [i[0] for i in test_experiments.values()]

        if not solver.binaries:
            print solver.name + " has no binaries! Skipping!"
            continue

        solver_binary = solver.binaries[-1]

        if db.session.query(db.SolverConfiguration).filter_by(solver_binary=solver_binary) \
                .filter(db.SolverConfiguration.Experiment_idExperiment.in_(competition_exp_ids)).count() == 0:

            for cat in solver.competition_categories:
                test_exp = db.session.query(db.Experiment).get(test_experiments[cat.name][0])
                comp_exp = db.session.query(db.Experiment).get(competition_experiments[cat.name][0])
                has_test_exp_config = False
                for solver_config in test_exp.solver_configurations:
                    if solver_config.solver_binary == solver_binary:
                        has_test_exp_config = True
                if not has_test_exp_config:
                    print "Solver " + solver.name + " is not in test exp for category " + cat.name
                    continue

                solver_config = add_solver_config(cat, solver_binary)
                if solver_config:
                    print "Adding " + solver.name + "  to " + comp_exp.name

