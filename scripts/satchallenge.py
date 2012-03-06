import time, sys, random, pickle, smtplib
from sqlalchemy.sql import not_
from email.MIMEText import MIMEText

random.seed()

sys.path.append("..")

from edacc import models, config, constants
from satchallenge_config import *

db = models.add_database(DB_USER, DB_PASSWORD, DB_NAME, DB_NAME)

STATE_FILE = "satchallenge.state"

try:
    testing_solvers = pickle.load(open(STATE_FILE))
except:
    testing_solvers = set()
    pickle.dump(testing_solvers, open(STATE_FILE, "wb"))

def send_mail(msg, to):
    msg['From'] = config.DEFAULT_MAIL_SENDER
    msg['Reply-to'] = config.DEFAULT_MAIL_SENDER
    msg['To'] = to
    msg.set_charset('utf8')
    server = smtplib.SMTP(config.MAIL_SERVER, config.MAIL_PORT)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
    server.sendmail(config.DEFAULT_MAIL_SENDER, [to], msg.as_string() )
    server.close()

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
        run.priority = -1
        run.CPUTimeLimit = experiment_info[1]
        run.wallClockTimeLimit = experiment_info[2]
        run.memoryLimit = experiment_info[3]
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

    msg = MIMEText('Dear ' + user.firstname + " " + user.lastname + ',\n\n' +
                   'This is an automatically generated e-mail regarding your solver submission to the SAT Challenge 2012.\n' +
                   'Your solver was executed in our execution environment with the following results:\n' +
                   str(num_successful) + " out of " + str(num_total) + " runs finished successfully in time\n" +
                   str(num_crash) + " runs crashed\n\n" +
                   'Please have a look at ' + base_url + 'experiments/ for detailed information about the test\n'
                   )
    msg['Subject'] = '[SAT Challenge 2012] Solver tested'
    msg.set_charset('utf8')
    send_mail(msg, solver_binary.solver.user.email)


while True:
    db.session.remove()
    for solver_binary in db.session.query(db.SolverBinary):
        if solver_binary.solver.user is None: continue # only consider solvers from users
        solver = solver_binary.solver
        if db.session.query(db.SolverConfiguration).filter_by(solver_binary=solver_binary).count() == 0:
            print solver.name + " appears to be a new solver. Adding to all test experiments based on its competition cateogries."
            testing_solvers.add(solver_binary.idSolverBinary)
            pickle.dump(testing_solvers, open(STATE_FILE, "wb"))
            for competition_category in solver.competition_categories:
                create_test_jobs(competition_category, solver_binary)

            # send mail to admin account
            msg = MIMEText('Solver with ID ' + str(solver.idSolver) +  ' was added and test jobs generated.')
            msg['Subject'] = '[SAT Challenge 2012][Admin] A solver was added'
            msg.set_charset('utf8')
            send_mail(msg, config.DEFAULT_MAIL_SENDER)

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