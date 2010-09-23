#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Simple EDACC client for testing purposes """
import sys, os
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'client_libs'))

import time, subprocess, resource, StringIO, shlex, threading, multiprocessing
import sqlalchemy
from sqlalchemy import Table, Integer, ForeignKey, create_engine, MetaData, Column
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import mapper, sessionmaker, scoped_session, deferred, relation, relationship, joinedload, joinedload_all
from datetime import datetime
from sqlalchemy.sql.expression import func

# Client configuration
TMP                 = '/tmp' # used for temporary files

# directory containing the subdirs solvers/ and instances/ (e.g. from a cluster package)
# os.path.join(os.path.abspath(os.path.dirname(__file__))) will be the directory containing this client.py file
PACKAGE_DIR         = os.path.join(os.path.abspath(os.path.dirname(__file__)))

DATABASE_DRIVER     = 'mysql'
DATABASE_HOST       = 'localhost'
DATABASE_PORT       = 3306
DATABASE_NAME       = 'EDACC'
DATABASE_USER       = 'edacc'
DATABASE_PASSWORD   = 'edaccteam'

# Experiment this client should run, case-sensitive
EXPERIMENT_NAME     = 'TestExperiment'

class EDACCDatabase(object):
    """ Encapsulates a single EDACC database connection """
    def __init__(self):
        url = URL(drivername=DATABASE_DRIVER, username=DATABASE_USER,
                  password=DATABASE_PASSWORD, host=DATABASE_HOST,
                  port=DATABASE_PORT, database=DATABASE_NAME)
        self.engine = create_engine(url)
        self.metadata = metadata = MetaData(bind=self.engine)

        class Solver(object): pass
        class SolverConfiguration(object): pass
        class Parameter(object): pass
        class ParameterInstance(object): pass
        class Instance(object): pass
        class Experiment(object): pass
        class ExperimentResult(object): pass
        class InstanceClass(object): pass
        class GridQueue(object): pass
        class User(object): pass
        class DBConfiguration(object): pass
        self.Solver = Solver
        self.SolverConfiguration = SolverConfiguration
        self.Parameter = Parameter
        self.ParameterInstance = ParameterInstance
        self.Instance = Instance
        self.Experiment = Experiment
        self.ExperimentResult = ExperimentResult
        self.InstanceClass = InstanceClass
        self.GridQueue = GridQueue
        self.User = User
        self.DBConfiguration = DBConfiguration

        metadata.reflect()

        # Table-Class mapping
        mapper(Parameter, metadata.tables['Parameters'])
        mapper(GridQueue, metadata.tables['gridQueue'])
        mapper(InstanceClass, metadata.tables['instanceClass'])
        mapper(Instance, metadata.tables['Instances'],
            properties = {
                'instance': deferred(metadata.tables['Instances'].c.instance),
                'instance_classes': relationship(InstanceClass, secondary=metadata.tables['Instances_has_instanceClass']),
                'source_class': relation(InstanceClass)
            }
        )
        mapper(Solver, metadata.tables['Solver'],
            properties = {
                'binary': deferred(metadata.tables['Solver'].c.binary),
                'code': deferred(metadata.tables['Solver'].c.code),
                'parameters': relation(Parameter, backref='solver')
            }
        )
        mapper(ParameterInstance, metadata.tables['SolverConfig_has_Parameters'],
            properties = {
                'parameter': relation(Parameter)
            }
        )
        mapper(SolverConfiguration, metadata.tables['SolverConfig'],
            properties = {
                'parameter_instances': relation(ParameterInstance),
                'solver': relation(Solver),
                'experiment': relation(Experiment),
            }
        )
        mapper(Experiment, metadata.tables['Experiment'],
            properties = {
                'instances': relationship(Instance, secondary=metadata.tables['Experiment_has_Instances']),
                'solver_configurations': relation(SolverConfiguration),
                'grid_queue': relationship(GridQueue, secondary=metadata.tables['Experiment_has_gridQueue']),
            }
        )
        mapper(ExperimentResult, metadata.tables['ExperimentResults'],
            properties = {
                'solverOutput': deferred(metadata.tables['ExperimentResults'].c.solverOutput),
                #'solverOutput': deferred(metadata.tables['ExperimentResults'].c.clientOutput),
                'solver_configuration': relation(SolverConfiguration),
                'experiment': relation(Experiment, backref='experiment_results'),
                'instance': relation(Instance),
            }
        )
        mapper(User, metadata.tables['User'],
            properties = {
                'solvers': relation(Solver, backref='user')
            }
        )
        mapper(DBConfiguration, metadata.tables['DBConfiguration'])

        self.session = scoped_session(sessionmaker(bind=self.engine, autocommit=False, autoflush=False))

def parameter_string(solver_config):
    """ Returns a string of the solver configuration parameters """
    parameters = solver_config.parameter_instances
    args = []
    for p in parameters:
        args.append(p.parameter.prefix)
        if p.parameter.hasValue:
            if p.value == "": # if value not set, use default value from parameters table
                args.append(p.parameter.value)
            else:
                args.append(p.value)
    return " ".join(args)

def launch_command(solver_config):
    """ Returns a string of what the solver launch command looks like given the solver configuration """
    return "./" + solver_config.solver.binaryName + " " + parameter_string(solver_config)

def setlimits(cputime):
    resource.setrlimit(resource.RLIMIT_CPU, (cputime, cputime + 10))

def fetch_resources(experiment_id, db):
    try:
        os.mkdir(os.path.join(PACKAGE_DIR, 'solvers'))
        os.mkdir(os.path.join(PACKAGE_DIR, 'instances'))
    except: pass

    experiment = db.session.query(db.Experiment).get(experiment_id)

    for i in experiment.instances:
        if not os.path.exists(os.path.join(PACKAGE_DIR, 'instances', str(i.idInstance) + '_' + i.name)):
            f = open(os.path.join(PACKAGE_DIR, 'instances', str(i.idInstance) + '_' + i.name), 'wb')
            f.write(i.instance)
            f.close()

    for s in set(sc.solver for sc in experiment.solver_configurations):
        if not os.path.exists(os.path.join(PACKAGE_DIR, 'solvers', s.binaryName)):
            f = open(os.path.join(PACKAGE_DIR, 'solvers', s.binaryName), 'wb')
            f.write(s.binary)
            f.close()
        os.chmod(os.path.join(PACKAGE_DIR, 'solvers', s.binaryName), 0744)

class EDACCClient(threading.Thread):
    count = 0
    def __init__(self, experiment_id, db):
        super(EDACCClient, self).__init__(group=None)
        self.experiment = db.session.query(db.Experiment).get(experiment_id)
        self.name = str(EDACCClient.count)
        self.db = db
        EDACCClient.count += 1

    def run(self):
        if self.experiment is None: return
        experiment = self.experiment
        db = self.db
        while True:
            job = None
            try:
                job = db.session.query(db.ExperimentResult) \
                        .filter_by(experiment=self.experiment) \
                        .filter_by(status=-1) \
                        .order_by(func.rand()).limit(1).first()
                job.status = 0
                db.session.commit()
            except:
                db.session.rollback()

            if job:
                job.startTime = func.now()
                db.session.commit()

                client_line = '/usr/bin/time -f ";%U;" '
                client_line += os.path.join(PACKAGE_DIR, 'solvers', launch_command(job.solver_configuration)[2:])
                client_line += os.path.join(PACKAGE_DIR, 'instances', str(job.instance.idInstance) + '_' + job.instance.name) + ' ' + str(job.seed)

                print "running job", job.idJob, client_line
                stdout = open(os.path.join(TMP, str(job.idJob) + 'stdout~'), 'w')
                stderr = open(os.path.join(TMP, str(job.idJob) + 'stderr~'), 'w')
                start = time.time()
                p = subprocess.Popen(shlex.split(client_line), preexec_fn=setlimits(experiment.CPUTimeLimit), stdout = stdout, stderr = stderr)
                p.wait()
                print "Job", job.idJob, "done .. Realtime:", str(time.time() - start), "s"
                stdout.close()
                stderr.close()

                stdout = open(os.path.join(TMP, str(job.idJob) + 'stdout~'), 'r')
                stderr = open(os.path.join(TMP, str(job.idJob) + 'stderr~'), 'r')
                time_output = stderr.read()
                tstart = time_output.find(";")
                tend = time_output.find(";", tstart+1)
                runtime = float(time_output[tstart+1:tend])

                job.solverOutput = stdout.read()
                stdout.close()
                stderr.close()
                os.remove(os.path.join(TMP, str(job.idJob) + 'stdout~'))
                os.remove(os.path.join(TMP, str(job.idJob) + 'stderr~'))

                job.resultTime = runtime

                #cpuinfo = open('/proc/cpuinfo')
                #job.solverOutput = cpuinfo.read()
                #cpuinfo.close()

                print "retcode", p.returncode

                if p.returncode == 24: # CPU Time limit exceeded exit code
                    job.status = 2
                else:
                    job.status = 1
                print "             CPU time:", runtime, "s"
                db.session.commit()
            else:
                if db.session.query(db.ExperimentResult) \
                        .filter_by(experiment=self.experiment) \
                        .filter_by(status=-1) \
                        .order_by(func.rand()).count() == 0: break # no more jobs


if __name__ == '__main__':
    try:
        db = EDACCDatabase()
    except Exception as e:
        print "Can't connect to database:", e
        sys.exit(0)

    experiment = db.session.query(db.Experiment).filter_by(name=EXPERIMENT_NAME).first()

    if experiment is None:
        print "Experiment doesn't exist"
        sys.exit(0)

    exp_id = experiment.idExperiment

    fetch_resources(exp_id, db)

    print "Starting up .. using " + str(experiment.grid_queue[0].numCPUs) + " threads"
    clients = [EDACCClient(exp_id, db) for _ in xrange(experiment.grid_queue[0].numCPUs)]
    for c in clients:
        c.start()
    for c in clients:
        c.join()
