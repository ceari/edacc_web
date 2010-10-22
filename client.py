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
DATABASE_HOST       = 'edacc.informatik.uni-ulm.de'
DATABASE_PORT       = 3306
DATABASE_NAME       = 'EDACC5'
DATABASE_USER       = 'edacc'
DATABASE_PASSWORD   = 'edaccteam'

# Experiment this client should run, case-sensitive
EXPERIMENT_NAME     = 'echo `satisfiable` > /dev/null'

class EDACCDatabase(object):
    """ Encapsulates a single EDACC database connection. """
    def __init__(self):
        self.database = DATABASE_NAME
        self.username = DATABASE_USER
        self.password = DATABASE_PASSWORD
        self.label = DATABASE_NAME

        url = URL(drivername=DATABASE_DRIVER, username=DATABASE_USER,
                  password=DATABASE_PASSWORD, host=DATABASE_HOST,
                  port=DATABASE_PORT, database=DATABASE_NAME,
                  query={'charset': 'utf8', 'use_unicode': 0})
        self.engine = create_engine(url, convert_unicode=True)
        self.metadata = metadata = MetaData(bind=self.engine)

        class Solver(object):
            """ Maps the Solver table """
            pass

        class SolverConfiguration(object):
            """ Solver configuration mapping the SolverConfig table.
                A solver configuration consists of a solver and a set of
                parameters and their values.
            """
            def get_number(self):
                """ Returns an integer i if `self` is the i-th of the solver configurations of the same solver
                    in the experiment `self` is in. If there's only one solver configuration of the solver this
                    function returns 0.
                """
                same_solvers = [sc for sc in self.experiment.solver_configurations if sc.solver == self.solver]
                if len(same_solvers) == 1:
                    return 0
                else:
                    return same_solvers.index(self) + 1

            def get_name(self):
                """ Returns the name of the solver configuration. """
                n = self.get_number()
                if n == 0:
                    return self.solver.name
                else:
                    return "%s (%s)" % (self.solver.name, str(n))

            def __str__(self):
                return self.get_name()

        class Parameter(object):
            """ Maps the Parameters table. """
            pass

        class ParameterInstance(object):
            """ Maps the n:m association table SolverConfig_has_Parameters,
                which for a parameter specifies its value in the corresponding
                solver configuration.
            """
            pass

        class Instance(object):
            """ Maps the Instances table. """
            def __str__(self):
                return self.name

            def get_property_value(self, property, db):
                """ Returns the value of the property with the given name. """
                try:
                    property = db.session.query(db.Property).get(property)
                    pv = db.session.query(db.InstanceProperties).filter_by(property=property, instance=self).first()
                    return pv.get_value()
                except:
                    return None

            def get_instance(self):
                """ Decompresses the instance blob and returns it as string """
                return pylzma.decompress(self.instance)

            def set_instance(self, uncompressed_instance):
                """ Compresses the instance and sets the instance blob attribute """
                self.instance = pylzma.compress(uncompressed_instance)


        class Experiment(object):
            """ Maps the Experiment table. """
            def get_num_runs(self, db):
                """ Returns the number of runs of the experiment """
                num_results = db.session.query(db.ExperimentResult).filter_by(experiment=self).count()
                num_solver_configs = db.session.query(db.SolverConfiguration).filter_by(experiment=self).count()
                num_instances = db.session.query(db.Instance).filter(db.Instance.experiments.contains(self)).count()
                if num_solver_configs == 0 or num_instances == 0:
                    return 0
                return num_results / num_solver_configs / num_instances

            def get_solved_instances(self, db):
                """ Returns the instances of the experiment that all solvers solved in every run """
                numInstances = db.session.query(db.Instance).filter(db.Instance.experiments.contains(self)).count()
                if numInstances == 0: return 0
                num_jobs_per_instance = db.session.query(db.ExperimentResult).filter_by(experiment=self).count() / numInstances
                instances = []
                for i in self.instances:
                    if db.session.query(db.ExperimentResult).filter(db.ExperimentResult.resultCode.like('1%')).filter_by(experiment=self, instance=i, status=1).count() == num_jobs_per_instance:
                        instances.append(i)
                return instances

            def get_num_solver_configs(self, db):
                return db.session.query(db.SolverConfiguration).filter_by(experiment=self).count()

            def get_num_instances(self, db):
                return db.session.query(db.Instance).filter(db.Instance.experiments.contains(self)).count()

        class ExperimentResult(object):
            """ Maps the ExperimentResult table. Provides a function
                to obtain a result property of a job.
            """
            def get_time(self):
                """ Returns the CPU time needed for this result or the
                    experiment's timeOut value if the status is
                    not correct (certified SAT/UNSAT answer).
                """
                if self.resultTime is None or self.resultCode not in (10, 11):
                    return self.experiment.CPUTimeLimit
                else:
                    return self.resultTime


            def get_property_value(self, property, db):
                """ Returns the value of the property with the given name.
                    If the property is 'cputime' it returns the time.
                    If the property is an integer, it returns the value of the
                    associated Property with this id.
                """
                if property == 'cputime':
                    return self.get_time()
                else:
                    try:
                        property = db.session.query(db.Property).get(int(property))
                        pv = db.session.query(db.ExperimentResultResultProperty).filter_by(property=property, experiment_result=self).first()
                        return pv.get_value()
                    except:
                        # if the property or property value doesn't exist return None
                        return None

        class InstanceClass(object):
            def __str__(self):
                return self.name

        class GridQueue(object): pass

        # competition tables

        class User(object): pass

        class DBConfiguration(object): pass

        class CompetitionCategory(object):
            def __str__(self):
                return self.name

        class BenchmarkType(object):
            def __str__(self):
                return self.name

        # result and instance properties

        class Property(object):
            def is_result_property(self):
                return self.propertyType == constants.RESULT_PROPERTY_TYPE

            def is_instance_property(self):
                return self.propertyType == constants.INSTANCE_PROPERTY_TYPE

            def is_simple(self):
                """ Returns whether the property is a simple property which is
                    stored in a way that's directly castable to a Python object
                """
                return self.propertyValueType.lower() in ('float', 'double', 'int', 'integer', 'string')

            def is_plotable(self):
                """ Returns whether the property is a simple property which is
                    stored in a way that's directly castable to a Python object
                    and is numeric.
                """
                return self.propertyValueType.lower() in ('float', 'double', 'int', 'integer')

        class PropertyValueType(object): pass

        class ExperimentResultProperty(object):
            def get_value(self):
                valueType = self.property.propertyValueType.lower()
                try:
                    if valueType in ('float', 'double'):
                        return float(self.values[0].value)
                    elif valueType in ('int', 'integer'):
                        return int(self.values[0].value)
                    else:
                        return None
                except Exception:
                    return None

        class ResultPropertyValue(object): pass

        class InstanceProperties(object):
            def get_value(self):
                valueType = self.property.valueType.lower()
                try:
                    if valueType in ('float', 'double',):
                        return float(self.value)
                    elif valueType in ('int', 'integer'):
                        return int(self.value)
                    elif valueType in ('string', ):
                        return str(self.value)
                    else:
                        return None
                except ValueError:
                    return None


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
        self.CompetitionCategory = CompetitionCategory
        self.BenchmarkType = BenchmarkType

        self.Property = Property
        self.PropertyValueType = PropertyValueType
        self.ExperimentResultProperty = ExperimentResultProperty
        self.ResultPropertyValue = ResultPropertyValue
        self.InstanceProperties = InstanceProperties

        metadata.reflect()

        # Table-Class mapping
        mapper(Parameter, metadata.tables['Parameters'])
        mapper(GridQueue, metadata.tables['gridQueue'])
        mapper(InstanceClass, metadata.tables['instanceClass'])
        mapper(Instance, metadata.tables['Instances'],
            properties = {
                'instance': deferred(metadata.tables['Instances'].c.instance),
                'instance_classes': relationship(InstanceClass, secondary=metadata.tables['Instances_has_instanceClass'], backref='instances'),
                'source_class': relation(InstanceClass, backref='source_instances'),
                'properties': relation(InstanceProperties, backref='instance'),
            }
        )
        mapper(Solver, metadata.tables['Solver'],
            properties = {
                'binary': deferred(metadata.tables['Solver'].c.binary),
                'code': deferred(metadata.tables['Solver'].c.code),
                'parameters': relation(Parameter, backref='solver'),
                'competition_categories': relationship(
                    CompetitionCategory,
                    backref='solvers',
                    secondary=metadata.tables['Solver_has_CompetitionCategory'])
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
                'instances': relationship(Instance, secondary=metadata.tables['Experiment_has_Instances'], backref='experiments'),
                'solver_configurations': relation(SolverConfiguration),
                'grid_queue': relationship(GridQueue, secondary=metadata.tables['Experiment_has_gridQueue']),
                'results': relation(ExperimentResult)
            }
        )
        mapper(ExperimentResult, metadata.tables['ExperimentResults'],
            properties = {
                'solverOutput': deferred(metadata.tables['ExperimentResults'].c.solverOutput),
                'launcherOutput': deferred(metadata.tables['ExperimentResults'].c.launcherOutput),
                'watcherOutput': deferred(metadata.tables['ExperimentResults'].c.watcherOutput),
                'verifierOutput': deferred(metadata.tables['ExperimentResults'].c.verifierOutput),
                'solverOutputFN': deferred(metadata.tables['ExperimentResults'].c.solverOutputFN),
                'launcherOutputFN': deferred(metadata.tables['ExperimentResults'].c.launcherOutputFN),
                'watcherOutputFN': deferred(metadata.tables['ExperimentResults'].c.watcherOutputFN),
                'verifierOutputFN': deferred(metadata.tables['ExperimentResults'].c.verifierOutputFN),
                'solver_configuration': relation(SolverConfiguration),
                'properties': relationship(ExperimentResultProperty, backref='experiment_result'),
                'experiment': relation(Experiment, backref='experiment_results'),
                'instance': relation(Instance),
            }
        )

        mapper(User, metadata.tables['User'],
            properties = {
                'solvers': relation(Solver, backref='user'),
                'source_classes': relation(InstanceClass, backref='user'),
                'benchmark_types': relation(BenchmarkType, backref='user')
            }
        )
        mapper(DBConfiguration, metadata.tables['DBConfiguration'])
        mapper(CompetitionCategory, metadata.tables['CompetitionCategory'])
        mapper(BenchmarkType, metadata.tables['BenchmarkType'],
            properties = {
                'instances': relation(Instance, backref='benchmark_type')
            }
        )

        mapper(Property, metadata.tables['Property'])
        mapper(PropertyValueType, metadata.tables['PropertyValueType'])
        mapper(ExperimentResultProperty, metadata.tables['ExperimentResult_has_Property'],
            properties = {
                'property': relationship(Property, backref='experiment_results'),
                'values': relation(ResultPropertyValue)
            }
        )
        mapper(ResultPropertyValue, metadata.tables['ExperimentResult_has_PropertyValue'])
        mapper(InstanceProperties, metadata.tables['Instance_has_Property'],
            properties = {
                'property': relationship(Property, backref='instances')
            }
        )

        self.session = scoped_session(sessionmaker(bind=self.engine, autocommit=False, autoflush=False))

        # initialize DBConfiguration table if not already done
        if self.session.query(DBConfiguration).get(0) is None:
            dbConfig = DBConfiguration()
            dbConfig.id = 0
            dbConfig.competition = False
            dbConfig.competitionPhase = None
            self.session.add(dbConfig)
            self.session.commit()

    def is_competition(self):
        """ returns whether this database is a competition database (user management etc. necessary) or not """
        return self.session.query(self.DBConfiguration).get(0).competition

    def set_competition(self, b):
        self.session.query(self.DBConfiguration).get(0).competition = b

    def competition_phase(self):
        """ returns the competition phase this database is in (or None, if is_competition() == False) as integer"""
        if not self.is_competition(): return None
        return self.session.query(self.DBConfiguration).get(0).competitionPhase

    def set_competition_phase(self, phase):
        if phase is not None and phase not in (1,2,3,4,5,6,7): return
        self.session.query(self.DBConfiguration).get(0).competitionPhase = phase

    def __str__(self):
        return self.label

def parameter_string(solver_config, instance_filename, seed):
    """ Returns a string of the solver configuration parameters """
    parameters = sorted(solver_config.parameter_instances, key=lambda p: p.parameter.order)
    args = []
    for p in parameters:
        if p.parameter.name == "instance":
            p.value = instance_filename
        elif p.parameter.name == "seed":
            p.value = seed
        if p.parameter.prefix != None:
            args.append(p.parameter.prefix)
        if p.parameter.hasValue:
            if p.value == "": # if value not set, use default value from parameters table
                args.append(p.parameter.value)
            else:
                args.append(p.value)
    return " ".join(args)

def launch_command(solver_config, instance_filename, seed):
    """ Returns a string of what the solver launch command looks like given the solver configuration """
    return "./" + solver_config.solver.binaryName + " " + parameter_string(solver_config, instance_filename, seed)

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

                client_line = '/usr/bin/time -f ";time=%U;mem=%M;" '
                client_line += os.path.join(PACKAGE_DIR, 'solvers', launch_command(job.solver_configuration, os.path.join(PACKAGE_DIR, 'instances', str(job.instance.idInstance)+ '_' + job.instance.name), str(job.seed))[2:])


                print "running job", job.idJob, client_line
                stdout = open(os.path.join(TMP, str(job.idJob) + 'stdout~'), 'w')
                stderr = open(os.path.join(TMP, str(job.idJob) + 'stderr~'), 'w')
                start = time.time()

                p = subprocess.Popen(shlex.split(str(client_line)), preexec_fn=setlimits(self.experiment.CPUTimeLimit), stdout = stdout, stderr = stderr)

                returncode = p.wait()
                print "Job", job.idJob, "done .. Realtime:", str(time.time() - start), "s"
                stdout.close()
                stderr.close()

                stdout = open(os.path.join(TMP, str(job.idJob) + 'stdout~'), 'r')
                stderr = open(os.path.join(TMP, str(job.idJob) + 'stderr~'), 'r')
                time_output = stderr.read().split(';')
                runtime = float([d.split('=')[1] for d in time_output if d.startswith('time=')][0])
                memory = int([d.split('=')[1] for d in time_output if d.startswith('mem=')][0])

                job.solverOutput = stdout.read()
                stdout.close()
                stderr.close()
                os.remove(os.path.join(TMP, str(job.idJob) + 'stdout~'))
                os.remove(os.path.join(TMP, str(job.idJob) + 'stderr~'))

                job.resultTime = runtime


                #cpuinfo = open('/proc/cpuinfo')
                #job.solverOutput = cpuinfo.read()
                #cpuinfo.close()

                print "  retcode", returncode

                if returncode != 10 and returncode != 0: # CPU Time limit exceeded exit code guess
                    job.status = 21
                else:
                    job.status = 1
                    if 's SATISFIABLE' in job.solverOutput:
                        job.resultCode = 11
                print "  CPU time:", runtime, "s", "Memory used:", memory, "kB"
                job.computeQueue = self.experiment.grid_queue[0].idgridQueue
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
