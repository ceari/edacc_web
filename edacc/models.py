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

from sqlalchemy import create_engine, MetaData
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import mapper, sessionmaker, scoped_session, deferred
from sqlalchemy.orm import relation, relationship

from edacc import config, constants


class EDACCDatabase(object):
    """ Encapsulates a single EDACC database connection """
    def __init__(self, username, password, database, label):
        self.database = database
        self.username = username
        self.password = password
        self.label = label

        url = URL(drivername=config.DATABASE_DRIVER, username=username,
                  password=password, host=config.DATABASE_HOST,
                  port=config.DATABASE_PORT, database=database,
                  query={'charset': 'utf8', 'use_unicode': 0})
        self.engine = create_engine(url, convert_unicode=True)
        self.metadata = metadata = MetaData(bind=self.engine)

        class Solver(object): pass

        class SolverConfiguration(object):
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
                n = self.get_number()
                if n == 0:
                    return self.solver.name
                else:
                    return "%s (%s)" % (self.solver.name, str(n))

            def __str__(self):
                return self.get_name()

        class Parameter(object): pass

        class ParameterInstance(object): pass

        class Instance(object):
            def __str__(self):
                return self.name

            def get_property_value(self, property, db):
                """ Returns the value of the property with the given name. """
                if property == 'numAtoms':
                    return self.numAtoms
                else:
                    property = db.session.query(db.InstanceProperty).get(property)
                    pv = db.session.query(db.InstanceProperties).filter_by(property=property, instance=self).first()
                    return pv.get_value()

        class Experiment(object):
            def is_finished(self):
                """ Returns whether this experiment is finished (true if there are any jobs and all of them are terminated) """
                if len(self.experiment_results) == 0: return False
                return all(j.status in constants.JOB_FINISHED or j.status in constants.JOB_ERROR
                           for j in self.experiment_results)
            def is_running(self):
                """ Returns true if there are any running jobs """
                return any(j.status in constants.JOB_RUNNING for j in self.experiment_results)
            def get_num_runs(self, db):
                num_results = db.session.query(db.ExperimentResult).filter_by(experiment=self).count()
                num_solver_configs = db.session.query(db.SolverConfiguration).filter_by(experiment=self).count()
                num_instances = db.session.query(db.Instance).filter(db.Instance.experiments.contains(self)).count()
                if num_solver_configs == 0 or num_instances == 0:
                    return 0
                return num_results / num_solver_configs / num_instances

        class ExperimentResult(object):
            def get_time(self):
                """ Returns the CPU time needed for this result or the
                    experiment's timeOut value if the status is
                    not "finished" (correct).
                """
                return self.time if self.status == 1 else self.experiment.timeOut

            def get_property_value(self, property, db):
                """ Returns the value of the property with the given name.
                    If the property is 'cputime' it returns the time.
                    If the property is an integer, it returns the value of the
                    associated SolverProperty with this id.
                """
                if property == 'cputime':
                    return self.get_time()
                else:
                    property = db.session.query(db.SolverProperty).get(int(property))
                    pv = db.session.query(db.ExperimentResultSolverProperty).filter_by(solver_property=property, experiment_result=self).first()
                    return pv.get_value()

        class InstanceClass(object):
            def __str__(self):
                return self.name

        class GridQueue(object): pass

        class User(object): pass

        class DBConfiguration(object): pass

        class CompetitionCategory(object):
            def __str__(self):
                return self.name

        class BenchmarkType(object):
            def __str__(self):
                return self.name

        class InstanceProperty(object):
            def is_simple(self):
                """ Returns whether the property is a simple property which is
                    stored in a way that's directly castable to a Python object
                """
                return self.valueType.lower() in ('float', 'double', 'int', 'integer')

        class InstanceProperties(object):
            def get_value(self):
                valueType = self.property.valueType.lower()
                try:
                    if valueType in ('float', 'double',):
                        return float(self.value)
                    elif valueType in ('int', 'integer'):
                        return int(self.value)
                    else:
                        return None
                except ValueError:
                    return None

        class PropertyValueType(object): pass

        class SolverProperty(object):
            def is_simple(self):
                """ Returns whether the property is a simple property which is
                    stored in a way that's directly castable to a Python object
                """
                return self.multiple == False and self.PropertyValueType_name.lower() in ('float', 'double', 'int', 'integer')

        class ExperimentResultSolverProperty(object):
            def get_value(self):
                valueType = self.solver_property.PropertyValueType_name.lower()
                try:
                    if valueType in ('float', 'double',):
                        return float(self.values[0].value)
                    elif valueType in ('int', 'integer'):
                        return int(self.values[0].value)
                    else:
                        return None
                except ValueError:
                    return None

        class SolverPropertyValue(object): pass

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
        self.InstanceProperty = InstanceProperty
        self.PropertyValueType = PropertyValueType
        self.SolverProperty = SolverProperty
        self.ExperimentResultSolverProperty = ExperimentResultSolverProperty
        self.SolverPropertyValue = SolverPropertyValue
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
        mapper(SolverProperty, metadata.tables['SolverProperty'],
            properties = {
                'value_type': relation(PropertyValueType)
            }
        )
        mapper(ExperimentResult, metadata.tables['ExperimentResults'],
            properties = {
                'resultFile': deferred(metadata.tables['ExperimentResults'].c.resultFile),
                'clientOutput': deferred(metadata.tables['ExperimentResults'].c.clientOutput),
                'solver_configuration': relation(SolverConfiguration),
                'solver_properties': relationship(ExperimentResultSolverProperty, backref='experiment_result'),
                'experiment': relation(Experiment, backref='experiment_results'),
                'instance': relation(Instance),
            }
        )
        mapper(ExperimentResultSolverProperty, metadata.tables['ExperimentResult_has_SolverProperty'],
            properties = {
                'solver_property': relationship(SolverProperty, backref='experiment_results'),
                'values': relation(SolverPropertyValue)
            }
        )
        mapper(InstanceProperties, metadata.tables['Instance_has_InstanceProperty'],
            properties = {
                'property': relation(InstanceProperty),
                'value': deferred(metadata.tables['Instance_has_InstanceProperty'].c.value)
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
        mapper(PropertyValueType, metadata.tables['PropertyValueType'])
        mapper(SolverPropertyValue, metadata.tables['SolverPropertyValue'])
        mapper(InstanceProperty, metadata.tables['InstanceProperty'])

        self.session = scoped_session(sessionmaker(bind=self.engine, autocommit=False, autoflush=False))

        # initialize DBConfiguration table if not already done
        if self.session.query(DBConfiguration).get(0) is None:
            dbConfig = DBConfiguration()
            dbConfig.id = 0
            dbConfig.competition = False
            dbConfig.competitionPhase = None
            self.session.add(dbConfig)
            self.session.commit()

    def get_result_properties(self):
        """ Returns a list of the result properties in the database that are
            suited for Python use.
        """
        return [p for p in self.session.query(self.SolverProperty).all() if p.is_simple()]

    def get_instance_properties(self):
        """ Returns a list of the instance properties in the database that are
            suited for Python use.
        """
        return [p for p in self.session.query(self.InstanceProperty).all() if p.is_simple()]

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

# Dictionary of the databases this web server is serving
databases = {}


def get_databases():
    return databases


def add_database(username, password, database, label):
    databases[database] = EDACCDatabase(username, password, database, label)


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
