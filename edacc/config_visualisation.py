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
        print configForm
        solverConfig = {}
        paramAttribute = {}
        parameterValue = {}
        confidence = {}
        paramList = []
        numValue = 0
        minList = []
        maxList = []
        selectValueList = {}
        deselectedConfigs = []
        turnList = []
        hideList = [] 
        domain = None       
        
        #db Queries for configuration visualisation
        name = db.session.query(db.Experiment.name).filter(db.Experiment.idExperiment == expID).first()
        configuration['expName'] = str(name[0])
        solverConfigName =  dict((s.idSolverConfig, s.name) 
                        for s in db.session.query(db.SolverConfiguration).
                            filter(db.SolverConfiguration.Experiment_idExperiment == expID))
        configurable = [p.Parameters_idParameter for p in experiment.configuration_scenario.parameters if p.configurable and p.parameter.name not in ('instance', 'seed')]
        parameterName  =  dict((p.idParameter, p.name) 
                        for p in db.session.query(db.Parameter).
                            filter(db.Parameter.idParameter.in_(configurable)).distinct())
        #start = time.clock()
        solverConfigCosts = dict((s.idSolverConfig, s.cost) for s in experiment.solver_configurations) 
        #print time.clock() - start, "sec cost"
        ##TODO: query optimieren
        for scn in solverConfigName:
            parameterValue[scn] = dict((pv.Parameters_idParameter, pv.value) 
                            for pv in db.session.query(db.ParameterInstance).
                                filter(db.ParameterInstance.SolverConfig_idSolverConfig == scn).
                                filter(db.ParameterInstance.Parameters_idParameter.in_(parameterName.keys())).
                                filter(db.ParameterInstance.value != '')) 
        for scn in solverConfigName:
            confidence[scn] = int(db.session.query(db.ExperimentResult.idJob).
                            filter(db.ExperimentResult.SolverConfig_idSolverConfig == scn).count())
                   

        paramList.append('confidence')
        paramList.append('performance')
        
        #maps the web formular in lists
        if configForm != None:
            if 'min' in configForm.keys():
                domain = 'num'
                minList = map(str, configForm.getlist('min'))
            else:
                domain = 'cat'
            if 'max' in configForm.keys():
                maxList = map(str, configForm.getlist('max'))
            if 'turn' in configForm.keys():
                turnList =  map(int, configForm.getlist('turn'))
            if 'hide' in configForm.keys():
                hideList = map(int, configForm.getlist('hide'))          

        #creates a dictionary with values of the parameters of each solverConfig
        for scn in solverConfigName:
            parameterInstance = {} 
            parameter = {}
            
            parameterInstance['name'] = str(solverConfigName[scn])
            n = 2
            for p in parameterValue[scn]: 
                #assigns the value to the parameter of the solverConfig
                parameter[str(parameterName[p])]= str(parameterValue[scn][p])
                #creates a list of parameters              
                if str(parameterName[p]) not in paramList:
                    paramList.append(str(parameterName[p]))
                    
            #creates the list deselectedConfigs of solverConfigs which are deselected if the values are restricted
                elif domain == 'cat':
                    if str(parameterName[p]) in configForm.keys():                        
                        selectValueList[n] =  map(str, configForm.getlist(str(parameterName[p])))
                        if str(parameterValue[scn][p]) not in selectValueList[n]:
                            deselectedConfigs.append(scn)
                ##TODO: Werteauswahl nach Domain und einschraenkungen und noch was ueberlegen, falls Position veraendert
                ##TODO: irgendwas stimmt noch im webfrontend mit min max eingabe noch nicht
                elif domain == 'num':
                    if float(parameterValue[scn][p]) < float(minList[n]) or float(parameterValue[scn][p]) > float(maxList[n]):
                        deselectedConfigs.append(scn)
                n += 1
            
            if domain == 'cat':
                if 'confidence' in configForm.keys():
                    selectValueList[0] =  map(str, configForm.getlist('confidence'))
                    if str(confidence[scn]) not in selectValueList:
                        deselectedConfigs.append(scn)
                        
                if 'performance' in configForm.keys():
                    selectValueList[1] =  map(str, configForm.getlist('performance'))
                    if str(solverConfigCosts[scn]) not in selectValueList:
                        deselectedConfigs.append(scn)                        
            elif domain == 'num':
                if float(confidence[scn]) < float(minList[0]) or float(confidence[scn]) > float(maxList[0]):                       
                    deselectedConfigs.append(scn)
                if solverConfigCosts[scn] != None:
                    if float(solverConfigCosts[scn]) < float(minList[1]) or float(solverConfigCosts[scn]) > float(maxList[1]):
                        deselectedConfigs.append(scn)
                           
            parameter['confidence'] = confidence[scn]
        
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
            
            #creates a list of possible values (valueList) and an list of values for each parameter
            for scn in solverConfigName:
                if (pl in solverConfig[scn]['parameter']):
                    if (solverConfig[scn]['parameter'][pl] not in valueList):
                        valueList.append(solverConfig[scn]['parameter'][pl])
                    if scn not in deselectedConfigs:
                        values.append(solverConfig[scn]['parameter'][pl])
                else:
                    if scn not in deselectedConfigs:
                        values.append(0)        
            
            #maps the values of each parameter suitable for domains        
            if experiment.configuration_scenario.get_parameter_domain(pl) == "categoricalDomain":
                values = classify(values, valueList)
                domain = 'cat'
                
            elif experiment.configuration_scenario.get_parameter_domain(pl) == "ordinalDomain": 
                values = classify(values, valueList)
                domain = 'cat'

            elif experiment.configuration_scenario.get_parameter_domain(pl) == "realDomain":
                domain = 'num'
                values = map(float, values)
                valueList = map(float, valueList)      
                if i in turnList:
                    turn = True
                    values = turn(values)
                
            elif experiment.configuration_scenario.get_parameter_domain(pl) == "integerDomain":
                domain = 'num'
                values = map(int, values)
                valueList = map(int, valueList)                  
                if i in turnList:
                    turn = True
                    values = turn(values)             
            
            #checks if a parameter is shielded
            ##TODO: bei hide veraendert sich im webfrontend die max position noch nicht
            hide = False
            if len(hideList)>0 and (i in hideList):
                hide = True
            
            position = []
            length = len(paramList)
            for p in range(length):
                pos = (p + i -1) % length
                position.append(pos+1)   
            
            if numValue < len(values):
                numValue = len(values)    
                        
            if domain == 'num': 
                if float(minList[i-1])>=min(valueList) and float(minList[i-1])<=max(valueList):
                    minValue = minList[i-1]
                else:
                    minValue = min(valueList)
                if float(maxList[i-1])>=min(valueList) and float(maxList[i-1])<=max(valueList):
                    maxValue = maxList[i-1]
                else:
                    maxValue = max(valueList)
                    
                values = project(values)
                paramAttribute[i] = {'values': values,'min': minValue, 'max': maxValue, 'name': pl, 'hide': hide, 'turn': turn, 'position': position, 'domain': domain}
        
            elif domain == 'cat':
                values = project(values)
                paramAttribute[i] = {'values': values,'valueList': valueList, 'selectValueList': selectValueList, 'name': pl, 'hide': hide, 'turn': turn, 'position': position, 'domain': domain}
        
        list = []
        for i in range(numValue):
            list.append(i)
        configuration['numValue'] = list
        configuration['paramAttribute'] = paramAttribute
       
    def getConfiguration(self):
        return configuration
    