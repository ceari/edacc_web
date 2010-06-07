# -*- coding: utf-8 -*-

from edacc import config, app
import sqlalchemy
from sqlalchemy import Table, Integer, ForeignKey, create_engine, MetaData, Column
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import mapper, sessionmaker, scoped_session, deferred, relation, relationship

sqlalchemy.convert_unicode = True
url = URL(drivername=config.DATABASE_DRIVER, username=config.DATABASE_USER, password=config.DATABASE_PASSWORD,
          host=config.DATABASE_HOST, port=config.DATABASE_PORT, database=config.DATABASE_NAME)
engine = create_engine(url)
metadata = MetaData(bind=engine)

# reflect all tables
metadata.reflect()

class Solver(object): pass
class SolverConfiguration(object): pass
class Parameter(object): pass
class ParameterInstance(object): pass
class Instance(object): pass
class Experiment(object): pass
class ExperimentResult(object): pass
class InstanceClass(object): pass
class GridQueue(object): pass

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
        'solver': relation(Solver)
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

# thread-local session
session = scoped_session(sessionmaker(bind=engine, autocommit=False, autoflush=False))

@app.after_request
def shutdown_session(response):
    session.remove()
    return response