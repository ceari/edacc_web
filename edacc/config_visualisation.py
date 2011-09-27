"""
    edacc.configurator_view
    --------------------

    This module defines the view which shows configuration details.
    
    :copyright: (c) 2011 by Melanie Handel.
    :license: MIT, see LICENSE for details.
"""

from edacc import utils, models, constants
import time

configuration = {}
 #classify in Categories
def classify(values, categories):
    valueDict = {}    
    for vl in range(len(categories)): 
        valueDict[categories[vl]] = vl
    m = 0 
    for v in values:
        if v in valueDict:
            values[m] = valueDict[v]
        m += 1
    return values

#Turns the range of value
def turn(values):
    k = 0
    for va in values:
        values[k] = max(values) - va
        k += 1
    return values

#Projects the values to the range of the graph
def project(values):
    values = map(float, values)
    if max(values) > 0:
        j = 0
        tmp = 10/max(values)
        for v in values:
            values[j] = v * tmp
            j += 1 
    return values

class config_vis(object):
   
    
    def __init__(self, database, expID, configForm):
        db = models.get_database(database) or abort(404)   
        experiment = db.session.query(db.Experiment).get(expID) or abort(404)
        if experiment.configurationExp == False: return # kein Konfiguratorexperiment
        solverConfig = {}
        paramAttribute = {}
        parameterValue = {}
        confidence = {}
        paramList = []
        numValue = 0
        minList = []
        maxList = []
        turnList = []
        hideList = [] 
        domain = None       
        
        #start1 = time.clock()            
        name = db.session.query(db.Experiment.name).filter(db.Experiment.idExperiment == expID).first()
        configuration['expName'] = str(name[0])
        solverConfigName =  dict((s.idSolverConfig, s.name) 
                        for s in db.session.query(db.SolverConfiguration).
                            filter(db.SolverConfiguration.Experiment_idExperiment == expID))
        configurable = [p.Parameters_idParameter for p in experiment.configuration_scenario.parameters if p.configurable and p.parameter.name not in ('instance', 'seed')]
        parameterName  =  dict((p.idParameter, p.name) 
                        for p in db.session.query(db.Parameter).
                            filter(db.Parameter.idParameter.in_(configurable)).distinct())
        solverConfigCosts = dict((s.idSolverConfig, s.cost) 
                        for s in db.session.query(db.SolverConfiguration).
                            filter(db.SolverConfiguration.Experiment_idExperiment == expID)) 
        #print time.clock() - start1, "sec db1" 
        
        #start = time.clock()
        for scn in solverConfigName:
            parameterValue[scn] = dict((pv.Parameters_idParameter, pv.value) 
                            for pv in db.session.query(db.ParameterInstance).
                                filter(db.ParameterInstance.SolverConfig_idSolverConfig == scn).
                                filter(db.ParameterInstance.Parameters_idParameter.in_(parameterName.keys())).
                                filter(db.ParameterInstance.value != ''))
 
        for scn in solverConfigName:
            confidence[scn] = int(db.session.query(db.ExperimentResult.idJob).
                            filter(db.ExperimentResult.SolverConfig_idSolverConfig == scn).count())
       # print time.clock() - start, "sec db2"            

        paramList.append('confidence')
        paramList.append('perfomance')
        
        if configForm != None:
            minList = map(str, configForm.getlist('min'))
            maxList = map(str, configForm.getlist('max'))
            if 'turn' in configForm.keys():
                turnList =  map(int, configForm.getlist('turn'))
            if 'hide' in configForm.keys():
                hideList = map(int, configForm.getlist('hide'))
                
        
          
        
        for scn in solverConfigName:
            parameterInstance = {} 
            parameter = {}
            
            parameterInstance['name'] = str(solverConfigName[scn])
            
            for p in parameterValue[scn]:
                parameter[str(parameterName[p])]= str(parameterValue[scn][p])
                if str(parameterName[p]) not in paramList:
                    paramList.append(str(parameterName[p]))

            parameter['confidence'] = confidence[scn]
            
            ##TODO: nochmal genauer anschauen
            if solverConfigCosts[scn] != None:
                parameter['performance'] = solverConfigCosts[scn]
            else:
                parameter['performance'] = 0.0
   
            parameterInstance['parameter']= parameter 
            solverConfig[scn]= parameterInstance
        
        i=0
        for pl in paramList:
            values = []
            valueList = []
            minValue = 0
            maxValue = 0
            turn = False
            
            if (pl not in paramAttribute):
                i += 1
                
            for scn in solverConfigName:
                if (pl in solverConfig[scn]['parameter']):
                    if (solverConfig[scn]['parameter'][pl] not in values):
                        valueList.append(solverConfig[scn]['parameter'][pl])
                    #if configForm == None:
                    values.append(solverConfig[scn]['parameter'][pl])
##                    else:
##                        if solverConfig[scn]['parameter'][pl] <= maxList[i] and solverConfig[scn]['parameter'][pl] >= minList[i]:
##                            value.append(solverConfig[scn]['parameter'][pl])
                else:
                    values.append(0)        

            if experiment.configuration_scenario.get_parameter_domain(pl) == "categoricalDomain":
                values = classify(values, valueList)
                domain = categorical
                
            elif experiment.configuration_scenario.get_parameter_domain(pl) == "ordinalDomain": 
                values = classify(values, valueList)
                domain = ordinal

            elif experiment.configuration_scenario.get_parameter_domain(pl) == "realDomain":
                domain = real
                values = map(float, values)
                valueList = map(float, valueList)      
                if i in turnList:
                    turn = True
                    values = turn(values)
                
            elif experiment.configuration_scenario.get_parameter_domain(pl) == "integerDomain":
                domain = integer
                values = map(int, values)
                valueList = map(int, valueList)                  
                if i in turnList:
                    turn = True
                    values = turn(values) 
            
            values = project(values)
                        
            ##Todo: muss noch fuer die Domain individualisiert werden
            if len(valueList): 
                minValue = min(valueList)
                maxValue = max(valueList)                   
            
            if numValue < len(values):
                numValue = len(values)    
            
            hide = False
            if len(hideList)>0 and (i in hideList):
                hide = True
                
            position = []
            length = len(paramList)
            for p in range(length):
                pos = (p + i -1) % length
                position.append(pos+1)
            ##TODO: muss noch nach Domains geordnet werden
            paramAttribute[i] = {'values': values,'min': minValue, 'max': maxValue, 'name': pl, 'hide': hide, 'turn': turn, 'position': position, 'domain': domain}
        
        list = []
        for i in range(numValue):
            list.append(i)
        configuration['numValue'] = list
        configuration['paramAttribute'] = paramAttribute
       
    def getConfiguration(self):
        return configuration
    