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
def turnValue(values):
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
        selectValueList = {}
        deselectedConfigs = []
        turnList = []
        hideList = [] 
        domain = {}
        parameterDomain = {}
        
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
                            
        start = time.clock()
        for name in parameterName.values():
            parameterDomain[name] = experiment.configuration_scenario.get_parameter_domain(name)
        print time.clock() - start, "sec domain"
        solverConfigCosts = dict((s.idSolverConfig, s.cost) for s in experiment.solver_configurations) 
        
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
        domain['confidence']='num'
        paramList.append('performance')
        domain['performance']='num'
        
        #maps the web formular in lists
        if configForm != None:
            if 'min' in configForm.keys():
                minList = map(str, configForm.getlist('min'))
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
                    ##TODO: was ist mit mixedDomain und optionalDomain
                    if parameterDomain[str(parameterName[p])] == "realDomain" or parameterDomain[str(parameterName[p])] == "integerDomain":
                        domain[str(parameterName[p])] = 'num'
                    elif parameterDomain[str(parameterName[p])] == "categoricalDomain" or parameterDomain[str(parameterName[p])] == "ordinalDomain" or parameterDomain[str(parameterName[p])] == "flagDomain":
                        domain[str(parameterName[p])] = 'cat'
                    
            #creates the list deselectedConfigs of solverConfigs which are deselected if the values are restricted
                if configForm != None and domain[str(parameterName[p])] == 'cat':
                    if str(parameterName[p]) in configForm.keys():                        
                        selectValueList[n+1] =  map(str, configForm.getlist(str(parameterName[p])))
                        if str(parameterValue[scn][p]) not in selectValueList[n+1]:
                            deselectedConfigs.append(scn)
                ##TODO: Werteauswahl nach Domain und einschraenkungen und noch was ueberlegen, falls Position veraendert
                ##TODO: irgendwas stimmt noch im webfrontend mit min max eingabe noch nicht
                elif configForm != None and domain[str(parameterName[p])] == 'num':
                    if float(parameterValue[scn][p]) < float(minList[n]) or float(parameterValue[scn][p]) > float(maxList[n]):
                        deselectedConfigs.append(scn)
                n += 1
            
                       
            if len(minList)>0:
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
            if domain[pl] == "cat":
                values = classify(values, valueList)
            
            elif domain[pl] == "num":
                values = map(float, values)
                valueList = map(float, valueList)     
                 
            if len(turnList) > 0 and (i in turnList):
                turn = True
                values = turnValue(values)          
            
            #checks if a parameter is shielded
            ##TODO: bei hide veraendert sich im webfrontend die max position noch nicht
            hide = False
            if len(hideList)>0 and (i in hideList):
                hide = True
            
            positionList = []
            length = len(paramList)
            for p in range(length):
                pos = (p + i -1) % length
                positionList.append(pos+1)   
            
            if numValue < len(values):
                numValue = len(values)    
                        
            if domain[pl] == 'num': 
                if configForm != None and len(minList)>0 and float(minList[i-1])>=min(valueList) and float(minList[i-1])<=max(valueList):
                    minValue = minList[i-1]
                else:
                    minValue = min(valueList)
                if configForm != None and len(maxList)>0 and float(maxList[i-1])>=min(valueList) and float(maxList[i-1])<=max(valueList):
                    maxValue = maxList[i-1]
                else:
                    maxValue = max(valueList)
    
                values = project(values)
                paramAttribute[i] = {'values': values,'min': minValue, 'max': maxValue, 'name': pl, 'hide': hide, 'turn': turn, 'positionList': positionList, 'domain': domain[pl]}

                
            elif domain[pl] == 'cat':
                values = project(values)
                paramAttribute[i] = {'values': values,'valueList': valueList, 'selectValueList': selectValueList, 'name': pl, 'hide': hide, 'turn': turn, 'positionList': positionList, 'domain': domain[pl]}
           
        #chance the position
        ##TODO: position
##        if configForm != None:
##            for a in range(len(paramList)):
##                if  configForm.get(str(a+1)) != str(a+1):
##                    pos = map(int, configForm.get(str(a+1)))
##                    paramAttribute[a+1]
##                    paramList.insert(pos[0]-1, paramList[a])
##                    del paramList[a+1]

        list = []
        for i in range(numValue):
            list.append(i)
        configuration['numValue'] = list
        configuration['paramAttribute'] = paramAttribute
       
    def getConfiguration(self):
        return configuration
    