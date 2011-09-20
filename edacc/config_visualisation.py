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
    
    def __init__(self, database, expID, configForm):
        db = models.get_database(database) or abort(404)   
        experiment = db.session.query(db.Experiment).get(expID) or abort(404)
        if experiment.configurationExp == False: return # kein Konfiguratorexperiment
        solverConfig = {}
        paramAttribute = {}
        paramList = []
        numValue = 0
        paramList.append('confidence')
        paramList.append('perfomance')
##        if configForm != None:
##            for cf in configForm:
##                print cf, ": ", configForm[cf]
##            print configForm.keys()
##            print configForm.values()
        name = db.session.query(db.Experiment.name).filter(db.Experiment.idExperiment == expID).first()
        configuration['expName'] = str(name[0])
        solverConfigName =  dict((s.idSolverConfig, s.name) 
                        for s in db.session.query(db.SolverConfiguration).
                            filter(db.SolverConfiguration.Experiment_idExperiment == expID))
        parameterName  =  dict((p.idParameter, p.name) 
                        for p in db.session.query(db.Parameter).
                            filter(db.Parameter.idParameter == db.ConfigurationScenarioParameter.Parameters_idParameter).
                            filter(db.ConfigurationScenarioParameter.configurable == True).distinct())
        solverConfigCosts = dict((s.idSolverConfig, s.cost) 
                        for s in db.session.query(db.SolverConfiguration).
                            filter(db.SolverConfiguration.Experiment_idExperiment == expID))       
        
       ## print "val", db.session.query(db.Solver.description).all()
##        expPropertyValue = dict((rpv.) for rpv in ResultPropertyValue)
##        print "propValue", expPropertyValue
        
        for scn in solverConfigName:
            parameterInstance = {} 
            parameter = {}
            
            parameterInstance['name'] = str(solverConfigName[scn])
            parameterValue = dict((pv.Parameters_idParameter, pv.value) 
                        for pv in db.session.query(db.ParameterInstance).
                            filter(db.ParameterInstance.SolverConfig_idSolverConfig == scn).
                            filter(db.ConfigurationScenarioParameter.configurable == True).
                            filter(db.ParameterInstance.value != ''))
                            
            for p in parameterValue:
                parameter[str(parameterName[p])]=str(parameterValue[p])
                if str(parameterName[p]) not in paramList:
                    paramList.append(str(parameterName[p]))

            parameter['confidence'] = int(db.session.query(db.ExperimentResult.idJob).
                            filter(db.ExperimentResult.SolverConfig_idSolverConfig == scn).count())
            
            if solverConfigCosts[scn] != None:
                parameter['performance'] = solverConfigCosts[scn]
            else:
                parameter['performance'] = 0.0
   
            parameterInstance['parameter']= parameter 
            solverConfig[scn]= parameterInstance
        
        i=0
        for pl in paramList:
            value = []
            valueList = []
            minValue = 0
            maxValue = 0
            numDistinctValue = 0
            for scn in solverConfigName:
                if (pl in solverConfig[scn]['parameter']):
                    if (solverConfig[scn]['parameter'][pl] not in value):
                        numDistinctValue += 1
                        valueList.append(solverConfig[scn]['parameter'][pl])
                    
                    value.append(solverConfig[scn]['parameter'][pl])
                    
                else:
                    value.append(0)
                    
            #TODO: Wertetyp hier noch wichtig
            
            
            if experiment.configuration_scenario.get_parameter_domain("ps") == "realDomain" or experiment.configuration_scenario.get_parameter_domain("ps") == "integerDomain":  
                if experiment.configuration_scenario.get_parameter_domain("ps") == "realDomain":
                    value = map(float, value)
                    valueList = map(float, valueList)                    
                elif experiment.configuration_scenario.get_parameter_domain("ps") == "integerDomain":
                    value = map(int, value)
                    valueList = map(int, valueList)                
                if max(value) > 0:
                    j = 0
                    tmp = 10/max(value)
                    for v in value:
                        value[j] = v * tmp
                        j += 1 
                        
                if len(valueList): 
                    minValue = valueList[0]
                    maxValue = valueList[0]                    
                    for vl in valueList:
                        if vl < minValue:
                            minValue = vl
                        if vl > maxValue:
                            maxValue = vl
            
            if numValue < len(value):
                numValue = len(value)    
            if (pl not in paramAttribute):
                i += 1
            position = []
            length = len(paramList)
            for p in range(length):
                pos = (p + i -1) % length
                position.append(pos+1)
            paramAttribute[i] = {'value': value,'min': minValue, 'max': maxValue, 'name': pl, 'hide': False, 'position': position}
        
        list = []
        for i in range(numValue):
            list.append(i)
        configuration['numValue'] = list
        configuration['paramAttribute'] = paramAttribute
        

        
    def getConfiguration(self):
        return configuration
    
class setParamAttribute(object):
    def _init_(self, table):
        return table
    