import time, sys, random, pickle, smtplib
from sqlalchemy.sql import not_
random.seed()

sys.path.append("..")

from edacc import models, config, constants

DB_NAME = "EDACC"
DB_USER = "edacc"
DB_PASSWORD = "edaccteam"

base_url = 'http://edacc3.informatik.uni-ulm.de/SATChallenge2012/'

db = models.add_database(DB_USER, DB_PASSWORD, DB_NAME, DB_NAME)

# competition category - test experiment (id, time limit)  mapping
test_experiments = {
    "Random SAT": (8, 30),
}

STATE_FILE = "satchallenge.state"

try:
    testing_solvers = pickle.load(open(STATE_FILE))
except:
    testing_solvers = set()
    pickle.dump(testing_solvers, open(STATE_FILE, "wb"))

def create_test_jobs(competition_category, solver_binary):
    if competition_category.name not in test_experiments: return
    experiment_info = test_experiments[competition_category.name]
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
    for instance in experiment.instances:
        run = db.ExperimentResult()
        run.experiment = experiment
        run.instance = instance
        run.solver_configuration = solver_config
        run.run = 0
        run.seed = random.randint(1, 123456789)
        run.status = -1
        run.resultCode = 0
        run.priority = 0
        run.CPUTimeLimit = experiment_info[1]
        run.wallClockTimeLimit = -1
        run.memoryLimit = -1
        run.stackSizeLimit = -1
        run.output = db.ExperimentResultOutput()
        db.session.add(run)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print e
        sys.exit(1)

def send_info_mail(solver_binary):
    num_total = 0
    num_successful = 0
    num_crash = 0
    for solver_config in solver_binary.solver_configurations:
        qry = db.session.query(db.ExperimentResult).filter_by(solver_configuration=solver_config)
        num_total += qry.count()
        num_successful += qry.filter(db.ExperimentResult.resultCode.like(u"1%")).count()
        num_crash += qry.filter(db.ExperimentResult.status.in_(constants.STATUS_ERRORS)).count()

    user = solver_binary.solver.user

    from email.MIMEText import MIMEText
    msg = MIMEText('Dear ' + user.firstname + " " + user.lastname + ',\n\n' +
                   'This is an automatically generated e-mail regarding your solver submission to the SAT Challenge 2012\n' +
                   'Your solver was executed on our execution environment with the following results:\n' +
                   str(num_successful) + " out of " + str(num_total) + " runs finished successfully in time\n" +
                   str(num_crash) + " runs crashed\n\n" +
                   'Please have a look at ' + base_url + 'experiments/ for detailed information about the test\n'
                   )
    msg['Subject'] = '[SAT Challenge 2012] Solver tested'
    msg['From'] = "daniel.diepold@gmail.com"
    msg['Reply-to'] = "daniel.diepold@gmail.com"
    msg['To'] = solver_binary.solver.user.email

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login("daniel.diepold@gmail.com", "PASSWORD")
    server.sendmail("daniel.diepold@gmail.com", [solver_binary.solver.user.email], msg.as_string() )
    server.close()


while True:
    db.session.remove()

    for solver_binary in db.session.query(db.SolverBinary):
        if solver_binary.solver.user is None: continue # only consider solvers from users
        solver = solver_binary.solver
        if db.session.query(db.SolverConfiguration).filter_by(solver_binary=solver_binary).count() == 0:
            print solver.name + " appears to be a new solver"
            testing_solvers.add(solver_binary.idSolverBinary)
            pickle.dump(testing_solvers, open(STATE_FILE, "wb"))
            for competition_category in solver.competition_categories:
                create_test_jobs(competition_category, solver_binary)

    testing_solvers = pickle.load(open(STATE_FILE))
    done_solvers = set()
    for solver_binary_id in testing_solvers:
        solver_binary = db.session.query(db.SolverBinary).get(solver_binary_id)
        if not solver_binary: continue

        all_done = True
        for solver_config in solver_binary.solver_configurations:
            print solver_config.name, db.session.query(db.ExperimentResult).filter_by(solver_configuration=solver_config)\
                .filter(db.ExperimentResult.status.in_([-1, 0])).count()
            if db.session.query(db.ExperimentResult).filter_by(solver_configuration=solver_config) \
               .filter(db.ExperimentResult.status.in_([-1, 0])).count() != 0:
                all_done = False
                break
        if all_done:
            print "All runs of " + solver_binary.solver.name + " finished."
            done_solvers.add(solver_binary_id)
            send_info_mail(solver_binary)

    testing_solvers = testing_solvers.difference(done_solvers)
    pickle.dump(testing_solvers, open(STATE_FILE, "wb"))

    print "sleeping for 10 seconds"
    time.sleep(10)