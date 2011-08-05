"""
    edacc.configurator_view
    --------------------

    This module defines the view which shows configuration details.
    
    :copyright: (c) 2011 by Melanie Handel.
    :license: MIT, see LICENSE for details.
"""

from edacc import utils, models, constants

configuration = {}

class config_vis(object):
    
    def __init__(self, database, expID):
        db = models.get_database(database) or abort(404)   
        experiment = db.session.query(db.Experiment).get(expID) or abort(404)
        solverConfig = {}
        paramAttribute = {}
        paramList = []
        confidence = []
        
        name = db.session.query(db.Experiment.name).filter(db.Experiment.idExperiment == expID).first()
        configuration['expName'] = str(name[0])
        solverConfigName =  dict((s.idSolverConfig, s.name) for s in db.session.query(db.SolverConfiguration).filter(db.SolverConfiguration.Experiment_idExperiment == expID))
        parameterName  =  dict((p.idParameter, p.name) for p in db.session.query(db.Parameter).all())

        for scn in solverConfigName:
            parameterInstance = {} 
            parameter = {}
            
            parameterInstance['name'] = str(solverConfigName[scn])
            parameterValue = dict((pv.Parameters_idParameter, pv.value) for pv in db.session.query(db.ParameterInstance).filter(db.ParameterInstance.SolverConfig_idSolverConfig == scn))

            for p in parameterValue:
                parameter[str(parameterName[p])]=str(parameterValue[p])
                if str(parameterName[p]) not in paramList:
                    paramList.append(str(parameterName[p]))

            parameter['confidence'] = int(db.session.query(db.ExperimentResult.idJob).filter(db.ExperimentResult.SolverConfig_idSolverConfig == scn).count())
            paramList.append('confidence')
            parameter['performance'] = 68
            paramList.append('perfomance')
            parameterInstance['parameter']= parameter 
            solverConfig[scn]= parameterInstance
        
        #configuration['solverConfig'] = solverConfig
        
        i=0
        for pl in paramList:
            value = []
            valueList = []
            minValue = 0
            maxValue = 0
            numValue = 0
            for scn in solverConfigName:
                if (pl in solverConfig[scn]['parameter']):
                    if (solverConfig[scn]['parameter'][pl] not in value):
                        numValue += 1
                    value.append(solverConfig[scn]['parameter'][pl])
                    valueList.append(solverConfig[scn]['parameter'][pl])
                else:
                    value.append(' ')
            if len(valueList):
                minValue = min(valueList)
                maxValue = max(valueList)
                
            paramAttribute[pl] = {'value': value,'min': minValue, 'max': maxValue, 'numValue': numValue, 'position': i, 'hide': False, 'move up': False}
            i = i+1
        configuration['paramAttribute'] = paramAttribute
        

        
    def getConfiguration(self):
        return configuration
    
class setParamAttribute(object):
    def _init_(self, table):
        return configuration
    