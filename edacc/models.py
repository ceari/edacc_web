# -*- coding: utf-8 -*-

from edacc import config, constants
import sqlalchemy
from sqlalchemy import Table, Integer, ForeignKey, create_engine, MetaData, Column
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import mapper, sessionmaker, scoped_session, deferred, relation, relationship, joinedload, joinedload_all

sqlalchemy.convert_unicode = True

class EDACCDatabase(object):
    """ Encapsulates a single EDACC database connection """
    def __init__(self, username, password, database, label):
        self.database = database
        self.username = username
        self.password = password
        self.label = label
        
        url = URL(drivername=config.DATABASE_DRIVER, username=username,
                  password=password, host=config.DATABASE_HOST,
                  port=config.DATABASE_PORT, database=database)
        self.engine = create_engine(url)
        self.metadata = metadata = MetaData(bind=self.engine)
        
        class Solver(object): pass
        class SolverConfiguration(object):
            def get_number(self):
                """ Returns an integer i if `self` is the i-th of the solver configurations of the same solver
                    in the experiment `self` is in. If there's only one solver configuration of the solver this
                    function returns 0 """
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
            
        class Parameter(object): pass
        class ParameterInstance(object): pass
        class Instance(object): pass
        class Experiment(object):
            def is_finished(self):
                """ Returns whether this experiment is finished (true if there are any jobs and all of them are terminated) """
                if len(self.experiment_results) == 0: return False
                return all(j.status in constants.JOB_FINISHED or j.status in constants.JOB_ERROR
                           for j in self.experiment_results)
            def is_running(self):
                """ Returns true if there are any running jobs """
                return any(j.status in constants.JOB_RUNNING for j in self.experiment_results)
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
                'resultFile': deferred(metadata.tables['ExperimentResults'].c.resultFile),
                'clientOutput': deferred(metadata.tables['ExperimentResults'].c.clientOutput),
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
        self.session.commit()
    
    def competition_phase(self):
        """ returns the competition phase this database is in (or None, if is_competition() == False) as integer"""
        if not self.is_competition(): return None
        return self.session.query(self.DBConfiguration).get(0).competitionPhase
    
    def set_competition_phase(self, phase):
        if phase is not None and phase not in (1,2,3,4): return
        self.session.query(self.DBConfiguration).get(0).competitionPhase = phase
        self.session.commit()
        
    def __str__(self):
        return self.label
        
# Dictionary of the databases this web server is serving
databases = {}

def get_databases():
    return databases

def add_database(username, password, database, label):
    databases[database] = EDACCDatabase(username, password, database, label)

def remove_database(database):
    if databases.has_key(database):
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