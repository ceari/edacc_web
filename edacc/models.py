# -*- coding: utf-8 -*-
"""
    edacc.models
    ------------

    Provides EDACC database connections. The web application can serve multiple
    databases, which are held in the databases dictionary defined in this
    module.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

from collections import namedtuple
from lxml import etree
from cStringIO import StringIO

import sqlalchemy
from sqlalchemy import create_engine, MetaData, func
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import mapper, sessionmaker, scoped_session, deferred
from sqlalchemy.orm import relation, relationship, joinedload_all
from sqlalchemy.sql import and_, not_, select
from sqlalchemy import schema

from edacc import config, utils
from edacc.constants import *


class EDACCDatabase(object):
    """ Encapsulates a single EDACC database connection. """
    def __init__(self, username, password, database, label, hidden=False):
        self.database = database
        self.username = username
        self.password = password
        self.label = label
        self.hidden = hidden

        url = URL(drivername=config.DATABASE_DRIVER, username=username,
                  password=password, host=config.DATABASE_HOST,
                  port=config.DATABASE_PORT, database=database,
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
            def get_name(self):
                """ Returns the name of the solver configuration. """
                return self.name

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
                return self.get_name()

            def get_name(self):
                if self.instance_classes[0] is None:
                    return self.name
                pc = self.instance_classes[0]
                parent_classes = [pc.name]
                count = 1
                while pc.parent_class and count < 3:
                    pc = pc.parent_class
                    parent_classes.append(pc.name)
                    count += 1
                if pc.parent_class: return '/.../' + '/'.join(reversed(parent_classes)) + "/" + self.name
                else: return '/'.join(reversed(parent_classes)) + "/" + self.name

            def get_property_value(self, property, db):
                """ Returns the value of the property with the given name. """
                try:
                    for p in self.properties:
                        if p.idProperty == int(property):
                            return p.get_value()
                except:
                    return None

            def get_instance(self, db):
                """
                    Decompresses the instance blob if necessary and returns it as string.
                    EDACC can store compressed and uncompressed instances. To distinguish
                    between them, we prepend the ASCII characters "LZMA" to a compressed instance.
                """
                table = db.metadata.tables['Instances']
                c_instance = table.c['instance']
                c_id = table.c['idInstance']
                # get prefix
                instance_header = db.session.connection().execute(select([func.substring(c_instance, 1, 4)],
                                            c_id==self.idInstance).select_from(table)).first()[0]
                data_length = db.session.connection().execute(select([func.length(c_instance)],
                                            c_id==self.idInstance).select_from(table)).first()[0]
                if data_length > 32 * 1024 * 1024:
                    return "Instance too large for processing. Please use the EDACC GUI application."
                if instance_header == 'LZMA': # compressed instance?
                    # get blob without LZMA prefix
                    instance_blob = db.session.connection().execute(select([func.substring(c_instance, 5)],
                                                c_id==self.idInstance).select_from(table)).first()[0]
                    return utils.lzma_decompress(instance_blob)
                else:
                    return self.instance

            def set_instance(self, uncompressed_instance):
                """ Compresses the instance and sets the instance blob attribute """
                self.instance = "LZMA" + utils.lzma_compress(uncompressed_instance)


        class Experiment(object):
            """ Maps the Experiment table. """
            def get_num_jobs(self, db):
                return db.session.query(db.ExperimentResult).filter_by(experiment=self).count()

            #def get_num_runs(self, db):
            #    """ Returns the number of runs of the experiment """
            #    num_results = db.session.query(db.ExperimentResult) \
            #                        .filter_by(experiment=self).count()
            #    num_solver_configs = db.session.query(db.SolverConfiguration) \
            #                            .filter_by(experiment=self).count()
            #    num_instances = db.session.query(db.Instance) \
            #                                .filter(db.Instance.experiments \
            #                                        .contains(self)).distinct().count()
            #    if num_solver_configs == 0 or num_instances == 0:
            #        return 0
            #    return num_results / num_solver_configs / num_instances

            def get_max_num_runs(self, db):
                """ Returns the number of runs of the experiment """
                res = db.session.query(func.max(db.ExperimentResult.run)).filter_by(experiment=self).first()
                if res is None or res[0] is None: return 0
                return res[0] + 1

            def get_solved_instances(self, db):
                """ Returns the instances of the experiment that any solver
                solved in any of its runs
                """
                instance_ids = [i[0] for i in db.session.query(db.ExperimentResult.Instances_idInstance) \
                            .filter_by(experiment=self).filter(db.ExperimentResult.resultCode.like('1%')) \
                            .filter_by(status=1).distinct().all()]
                return db.session.query(db.Instance).filter(db.Instance.idInstance.in_(instance_ids)).all()

            def get_fully_solved_instances(self, db):
                """ Returns the instances of the experiment that all solvers
                solved in all of their runs
                """
                numInstances = db.session.query(db.Instance).options(joinedload_all('properties')) \
                        .filter(db.Instance.experiments.contains(self)).distinct().count()
                if numInstances == 0: return 0
                num_jobs_per_instance = db.session.query(db.ExperimentResult) \
                        .filter_by(experiment=self).count() / numInstances
                instances = []
                for i in self.instances:
                    if db.session.query(db.ExperimentResult) \
                            .filter(db.ExperimentResult.resultCode.like('1%')) \
                            .filter_by(experiment=self, instance=i, status=1) \
                            .count() == num_jobs_per_instance:
                        instances.append(i)
                return instances

            def get_unsolved_instances(self, db):
                t_results = db.metadata.tables['ExperimentResults']
                s = select([t_results.c['Instances_idInstance']],
                            and_(t_results.c['Experiment_idExperiment']==self.idExperiment,
                                 t_results.c['resultCode'].like('1%'),
                                 t_results.c['status']==1),
                            from_obj=t_results).distinct()
                ids = db.session.connection().execute(s).fetchall()
                return db.session.query(db.Instance).options(joinedload_all('properties')).filter(db.Instance.experiments.contains(self)).filter(not_(db.Instance.idInstance.in_(list(r[0] for r in ids)))).all()

            def get_instances(self, db):
                return db.session.query(db.Instance).options(joinedload_all('properties')) \
                        .filter(db.Instance.experiments.contains(self)).distinct().all()

            def get_num_solver_configs(self, db):
                return db.session.query(db.SolverConfiguration) \
                        .filter_by(experiment=self).distinct().count()

            def get_num_instances(self, db):
                return db.session.query(db.Instance) \
                        .filter(db.Instance.experiments.contains(self)).distinct().count()

            def get_total_instance_blob_size(self, db):
                table = db.metadata.tables['Instances']
                c_instance = table.c['instance']
                c_id = table.c['idInstance']
                instance_ids = [i.idInstance for i in self.get_instances(db)]
                instance_sizes = db.session.connection().execute(select([func.length(c_instance)],
                              c_id.in_(instance_ids)).select_from(table)).fetchall()
                total_size = sum(i[0] for i in instance_sizes or [(0,)])
                return total_size
            
            def get_result_matrix(self, db, solver_configs, instances):
                """ Returns the results as matrix of lists of result tuples, i.e.
                    Dict<idInstance, Dict<idSolverConfig, List of runs>> """
                num_successful = dict((i.idInstance, dict((sc.idSolverConfig, 0) for sc in solver_configs)) for i in instances)
                num_completed = dict((i.idInstance, dict((sc.idSolverConfig, 0) for sc in solver_configs)) for i in instances)
                M = dict((i.idInstance, dict((sc.idSolverConfig, list()) for sc in solver_configs)) for i in instances)
                solver_config_ids = [sc.idSolverConfig for sc in solver_configs]
                instance_ids = [i.idInstance for i in instances]
                table = db.metadata.tables['ExperimentResults']
                table_result_codes = db.metadata.tables['ResultCodes']
                s = select([table.c['idJob'], table.c['resultCode'], table.c['resultTime'], table.c['status'],
                            table.c['SolverConfig_idSolverConfig'], table.c['Instances_idInstance'],
                            table_result_codes.c['description'], table.c['CPUTimeLimit']],
                            and_(table.c['Experiment_idExperiment'] == self.idExperiment,
                                table.c['SolverConfig_idSolverConfig'].in_(solver_config_ids),
                                table.c['Instances_idInstance'].in_(instance_ids)),
                            from_obj=table.join(table_result_codes))
                Run = namedtuple('Run', ['idJob', 'result_code_description', 'resultCode', 'resultTime', 'successful', 'penalized_time10', 'idSolverConfig', 'idInstance'])
                for r in db.session.connection().execute(s):
                    if r.Instances_idInstance not in M: continue
                    if r.SolverConfig_idSolverConfig not in M[r.Instances_idInstance]: continue
                    if str(r.resultCode).startswith('1'): num_successful[r.Instances_idInstance][r.SolverConfig_idSolverConfig] += 1
                    if r.status not in STATUS_PROCESSING: num_completed[r.Instances_idInstance][r.SolverConfig_idSolverConfig] += 1
                    M[r.Instances_idInstance][r.SolverConfig_idSolverConfig].append(
                        Run(r.idJob, r[6], r.resultCode, None if r.status <= 0 else r.resultTime, str(r.resultCode).startswith('1'),
                            r.resultTime if str(r.resultCode).startswith('1') else r.CPUTimeLimit * 10,
                            r.SolverConfig_idSolverConfig, r.Instances_idInstance))
                return M, num_successful, num_completed
                    
        class ExperimentResult(object):
            """ Maps the ExperimentResult table. Provides a function
                to obtain a result property of a job.
            """
            def get_time(self):
                """ Returns the CPU time needed for this result or the
                    experiment's timeOut value if the status is
                    not correct (certified SAT/UNSAT answer).
                """
                # if the job is being processed or the CC had a crash return None
                if self.status <= 0:
                    return None

                if self.status in (STATUS_FINISHED, 21):
                    if self.resultTime == 0.0: return 1e-3
                    return self.resultTime

                return None

            def get_penalized_time(self, p_factor=10):
                if self.CPUTimeLimit == -1:
                    return float('inf')
                else:
                    return self.CPUTimeLimit * p_factor

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
                        for pv in self.properties:
                            if pv.idProperty == int(property):
                                return pv.get_value() 
                    except:
                        return None

            def to_json(self):
                return {
                    'idJob': self.idJob,
                    'Experiment_idExperiment': self.Experiment_idExperiment,
                    'Instances_idInstance': self.Instances_idInstance,
                    'run': self.run,
                    'resultCode': self.resultCode,
                    'resultTime': self.resultTime,
                    'status': self.status,
                    'seed': self.seed,
                    'startTime': str(self.startTime),
                    'computeQueue': self.computeQueue,
                    'priority': self.priority,
                }

        class ExperimentResultOutput(object): pass

        class InstanceClass(object):
            def __str__(self):
                return self.name

        class ResultCodes(object):
            def to_json(self):
                return {
                    'code': self.resultCode,
                    'description': self.description,
                }
        class StatusCodes(object):
            def to_json(self):
                return {
                    'code': self.statusCode,
                    'description': self.description,
                }
        class SolverBinary(object): pass
        class Client(object): pass
        class Experiment_has_Client(object): pass

        class GridQueue(object):
            pass
        
        class ConfigurationScenario(object):
            def get_parameter_domain(self, parameter_name):
                """ Returns the domain name of a parameter. This can
                    be one of the following:
                    realDomain, flagDomain, categoricalDomain, ordinalDomain,
                    integerDomain, mixedDomain, optionalDomain.
                """
                pgraph = self.solver_binary.solver.parameter_graph[0].serializedGraph
                if pgraph is None: return None
                tree = etree.parse(StringIO(pgraph))
                if tree is None: return None
                root = tree.getroot()
                for node in root:
                    if node.tag == "parameters" and node[1].text == parameter_name:
                        return node[0].attrib.values()[0]
            
        class ConfigurationScenarioParameter(object): pass

        class ParameterGraph(object): pass

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
                return self.propertyType == RESULT_PROPERTY_TYPE

            def is_instance_property(self):
                return self.propertyType == INSTANCE_PROPERTY_TYPE

            def is_simple(self):
                """ Returns whether the property is a simple property which is
                    stored in a way that's directly castable to a Python object
                """
                return self.propertyValueType.lower() in ('float', 'double',
                                                          'int', 'integer',
                                                          'string')

            def is_plotable(self):
                """ Returns whether the property is a simple property which is
                    stored in a way that's directly castable to a Python object
                    and is numeric.
                """
                return self.propertyValueType.lower() in ('float', 'double',
                                                          'int', 'integer')

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
                valueType = self.property.propertyValueType.lower()
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
        self.ExperimentResultOutput = ExperimentResultOutput
        self.InstanceClass = InstanceClass
        self.GridQueue = GridQueue
        self.ResultCodes = ResultCodes
        self.StatusCodes = StatusCodes
        self.SolverBinary = SolverBinary
        self.Client = Client
        self.Experiment_has_Client = Experiment_has_Client
        self.ConfigurationScenario = ConfigurationScenario
        self.ConfigurationScenarioParameter = ConfigurationScenarioParameter

        self.User = User
        self.DBConfiguration = DBConfiguration
        self.CompetitionCategory = CompetitionCategory
        self.BenchmarkType = BenchmarkType

        self.Property = Property
        self.PropertyValueType = PropertyValueType
        self.ExperimentResultProperty = ExperimentResultProperty
        self.ResultPropertyValue = ResultPropertyValue
        self.InstanceProperties = InstanceProperties
        self.ParameterGraph = ParameterGraph

        metadata.reflect()

        schema.Table("instanceClass", metadata,
            schema.Column('parent', sqlalchemy.Integer, schema.ForeignKey("instanceClass.idinstanceClass")),
            useexisting=True, autoload=True
        )

        # Table-Class mapping
        mapper(GridQueue, metadata.tables['gridQueue'])
        mapper(Client, metadata.tables['Client'],
            properties = {
                'grid_queue': relationship(GridQueue, backref='clients'),
                'experiments': relationship(Experiment,
                    secondary=metadata.tables['Experiment_has_Client'], backref='clients'),
            }
        )
        mapper(Experiment_has_Client, metadata.tables['Experiment_has_Client'])
        mapper(Parameter, metadata.tables['Parameters'])
        mapper(InstanceClass, metadata.tables['instanceClass'],
            properties = {
                'parent_class': relationship(InstanceClass, remote_side=metadata.tables['instanceClass'].c['idinstanceClass'],
                    lazy="joined", join_depth=10)
            }
        )
        mapper(Instance, metadata.tables['Instances'],
            properties = {
                'instance': deferred(metadata.tables['Instances'].c.instance),
                'instance_classes': relationship(InstanceClass,
                    secondary=metadata.tables['Instances_has_instanceClass'], backref='instances',
                    lazy="joined"),
                'properties': relation(InstanceProperties, backref='instance'),
            }
        )
        mapper(Solver, metadata.tables['Solver'],
            properties = {
                'code': deferred(metadata.tables['Solver'].c.code),
                'binaries': relation(SolverBinary, backref='solver'),
                'parameters': relation(Parameter, backref='solver'),
                'competition_categories': relationship(
                    CompetitionCategory,
                    backref='solvers',
                    secondary=metadata.tables['Solver_has_CompetitionCategory']),
                'parameter_graph': relation(ParameterGraph),
            }
        )
        mapper(SolverBinary, metadata.tables['SolverBinaries'],
            properties = {
                'binaryArchive': deferred(metadata.tables['SolverBinaries'].c.binaryArchive),
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
                'solver_binary': relation(SolverBinary),
                'experiment': relation(Experiment),
            }
        )
        mapper(ParameterGraph, metadata.tables['ParameterGraph'])
        mapper(ConfigurationScenarioParameter, metadata.tables['ConfigurationScenario_has_Parameters'],
            properties = {
                'parameter': relation(Parameter)
            }
        )
        mapper(ConfigurationScenario, metadata.tables['ConfigurationScenario'],
            properties = {
                'parameters': relation(ConfigurationScenarioParameter),
                'solver_binary': relation(SolverBinary),
            }
        )
        mapper(Experiment, metadata.tables['Experiment'],
            properties = {
                'instances': relationship(Instance,
                    secondary=metadata.tables['Experiment_has_Instances'], backref='experiments'),
                'solver_configurations': relation(SolverConfiguration),
                'grid_queue': relationship(GridQueue,
                    secondary=metadata.tables['Experiment_has_gridQueue']),
                'results': relation(ExperimentResult),
                'configuration_scenario': relation(ConfigurationScenario, uselist=False),
            }
        )
        mapper(StatusCodes, metadata.tables['StatusCodes'])
        mapper(ResultCodes, metadata.tables['ResultCodes'])
        mapper(ExperimentResultOutput, metadata.tables['ExperimentResultsOutput'])
        mapper(ExperimentResult, metadata.tables['ExperimentResults'],
            properties = {
                'output': relation(ExperimentResultOutput, backref='result', uselist=False),
                'solver_configuration': relation(SolverConfiguration),
                'properties': relationship(ExperimentResultProperty, backref='experiment_result'),
                'experiment': relation(Experiment, backref='experiment_results'),
                'instance': relation(Instance, backref='results'),
                'status_code': relation(StatusCodes, uselist=False),
                'result_code': relation(ResultCodes, uselist=False),
                'computeNode': deferred(metadata.tables['ExperimentResults'].c.computeNode),
                'computeNodeIP': deferred(metadata.tables['ExperimentResults'].c.computeNodeIP),
                'client': relation(Client),
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
                'property': relationship(Property, backref='experiment_results', lazy='joined'),
                'values': relation(ResultPropertyValue, backref='experiment_result_property', lazy='joined')
            }
        )
        mapper(ResultPropertyValue, metadata.tables['ExperimentResult_has_PropertyValue'])
        mapper(InstanceProperties, metadata.tables['Instance_has_Property'],
            properties = {
                'property': relationship(Property, backref='instances')
            }
        )

        self.session = scoped_session(sessionmaker(bind=self.engine, autocommit=False,
                                                   autoflush=False))

        # initialize DBConfiguration table if not already done
        if self.session.query(DBConfiguration).get(0) is None:
            dbConfig = DBConfiguration()
            dbConfig.id = 0
            dbConfig.competition = False
            dbConfig.competitionPhase = None
            self.session.add(dbConfig)
            self.session.commit()

        self.db_is_competition = self.session.query(self.DBConfiguration).get(0).competition
        if not self.db_is_competition:
            self.db_competition_phase = None
        else:
            self.db_competition_phase = self.session.query(self.DBConfiguration).get(0).competitionPhase

    def get_result_properties(self):
        """ Returns a list of the result properties in the database that are
            suited for Python use.
        """
        return [p for p in self.session.query(self.Property).all() \
                if p.is_simple() and p.is_result_property()]

    def get_plotable_result_properties(self):
        """ Returns a list of the result properties in the database that are
            suited for plotting.
        """
        return [p for p in self.session.query(self.Property).all() \
                if p.is_plotable() and p.is_result_property()]

    def get_instance_properties(self):
        """ Returns a list of the instance properties in the database that are
            suited for Python use.
        """
        return [p for p in self.session.query(self.Property).all() \
                if p.is_simple() and p.is_instance_property()]

    def get_plotable_instance_properties(self):
        """ Returns a list of the instance properties in the database that are
            suited for plotting.
        """
        return [p for p in self.session.query(self.Property).all() \
                if p.is_plotable() and p.is_instance_property()]

    def is_competition(self):
        """ returns whether this database is a competition database (user management etc.
        necessary) or not
        """
        return self.db_is_competition

    def set_competition(self, b):
        self.session.query(self.DBConfiguration).get(0).competition = b
        self.db_is_competition = b
        if b == False:
            self.db_competition_phase = None

    def competition_phase(self):
        """ returns the competition phase this database is in (or None,
        if is_competition() == False) as integer
        """
        return self.db_competition_phase

    def set_competition_phase(self, phase):
        if phase is not None and phase not in (1,2,3,4,5,6,7): return
        self.session.query(self.DBConfiguration).get(0).competitionPhase = phase
        self.db_competition_phase = phase

    def __str__(self):
        return self.label

# Dictionary of the databases this web server is serving
databases = {}


def get_databases():
    return databases


def add_database(username, password, database, label, hidden=False):
    databases[database] = EDACCDatabase(username, password, database, label, hidden)
    return databases[database]


def remove_database(database):
    if database in databases:
        del databases[database]


def get_database(database):
    if databases.has_key(database):
        return databases[database]
    else:
        return None

#import logging
#logging.basicConfig()
#logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
#logging.getLogger('sqlalchemy.orm.unitofwork').setLevel(logging.DEBUG)
