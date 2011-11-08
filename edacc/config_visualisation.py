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

#Projects values to the range of the graph
##TODO: was passiert, wenn die Werte kleiner Null?
def project(values):
    values = map(float, values)
    if max(values) > 0:
        j = 0
        tmp = 10/max(values)
        for v in values:
            values[j] = v * tmp
            j += 1 
    return values

#change position of the parameter
def mapPosition(form):
    pos = map(str, form)
    list = []
    b = 0
    pos1 = ''
    pos2 = ''
    while pos[0][b]!= ':':
        pos1 += pos[0][b]
        b+=1
    b += 1
    while b < len(pos[0]):
        pos2 += pos[0][b]
        b+=1
    list = [int(pos1), int(pos2)]               
    return list


class config_vis(object):
    def __init__(self, database, expID, configForm):
        db = models.get_database(database) or abort(404)   
        experiment = db.session.query(db.Experiment).get(expID) or abort(404)
        if experiment.configurationExp == False: return # kein Konfiguratorexperiment
        solverConfig = {}
        paramAttribute = {}
        parameterValue = {}
        paramList = []
        numValue = 0
        minDict = {}
        maxDict = {}
        selectValueList = {}
        deselectedConfigs = []
        turnList = []
        hideList = []
        configList = [] 
        domain = {}
        parameterDomain = {}
        parameterPosition = {}
        
        start_db = time.clock() 
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
                     
        for id in parameterName.keys():
            parameterDomain[id] = experiment.configuration_scenario.get_parameter_domain(parameterName[id])
        parameterDomain['confidence']= "integerDomain"
        parameterDomain['performance']= "realDomain"
        solverConfigCosts = dict((s.idSolverConfig, s.cost) for s in experiment.solver_configurations) 
        
        ##TODO: vielleicht noch optimieren
        for scn in solverConfigName:
            parameterValue[scn]= {'confidence': int(db.session.query(db.ExperimentResult.idJob).
                            filter(db.ExperimentResult.SolverConfig_idSolverConfig == scn).count())}
            if solverConfigCosts[scn] != None:
                parameterValue[scn].update({'performance': solverConfigCosts[scn] })
            else:
                parameterValue[scn].update({'performance': 0.0 })
        paramInstance = db.session.query(db.ParameterInstance).filter(db.ParameterInstance.SolverConfig_idSolverConfig.in_(solverConfigName.keys())).all()   
        print time.clock() - start_db, "dbZeit"

        parameterName.update({'confidence': 'confidence', 'performance': 'performance'})
        paramList.append('confidence')
        paramList.append('performance')
        
        start_pi = time.clock() 
        for pv in paramInstance:
            if pv.Parameters_idParameter not in parameterName.keys() or pv.value == "": continue
            if pv.SolverConfig_idSolverConfig not in parameterValue: 
                parameterValue[pv.SolverConfig_idSolverConfig] = {}
            parameterValue[pv.SolverConfig_idSolverConfig].update({pv.Parameters_idParameter: pv.value})
            if pv.Parameters_idParameter not in paramList:
                paramList.append(pv.Parameters_idParameter)        
        print time.clock() - start_pi, "piZeit"
        
        for pd in parameterDomain.keys():
                selectValueList[pd]= []
                if parameterDomain[pd] == "realDomain" or parameterDomain[pd] == "integerDomain":
                    domain[pd] = 'num'
                else:
                    domain[pd] = 'cat'
                                
        #maps the web formular in lists
        if configForm != None:
            for pm in paramList: 
                if str(pm) in configForm.keys():
                    parameterPosition[pm] = mapPosition(configForm.getlist(str(pm)))                    
                if domain[pm] == "num":
                    indexMin = "min_"+str(pm)
                    minList = []
                    if indexMin in configForm.keys():                    
                        minList = map(str, configForm.getlist(indexMin))
                    minDict[pm]=minList[0].strip()
                    indexMax = "max_"+str(pm)
                    maxList = []
                    if indexMax in configForm.keys():                    
                        maxList = map(str, configForm.getlist(indexMax))
                    maxDict[pm]=maxList[0].strip()
                elif domain[pm] == "cat":
                    index = "select_"+str(pm)
                    if index in configForm.keys():                    
                        select = map(str, configForm.getlist(index))
                        selectValueList[pm]=select

            if 'turn' in configForm.keys():
                turnList =  map(str, configForm.getlist('turn'))
            if 'hide' in configForm.keys():
                hideList = map(str, configForm.getlist('hide')) 
                
            if 'solverConfigs' in configForm.keys():
                configList = map(str, configForm.getlist('solverConfigs'))
                 
            
        #creates a dictionary with values of the parameters of each solverConfig
        for scn in solverConfigName:
            parameterInstance = {} 
            parameter = {}
            
            parameterInstance['name'] = str(solverConfigName[scn])
            n = 2
            for p in parameterValue[scn]: 
                #assigns the value to the parameter of the solverConfig
                parameter[p]= str(parameterValue[scn][p])
                    
            #creates the list deselectedConfigs of solverConfigs which are deselected if the values are restricted
                if configForm != None and domain[p] == 'cat':
                    if "select_"+str(p) in configForm.keys():                 
                        if str(parameterValue[scn][p]) not in selectValueList[p]:
                            deselectedConfigs.append(scn)

                elif configForm != None and domain[p] == 'num':
                    if len(minDict[p]) < 0:
                        if float(parameterValue[scn][p]) < float(minDict[p]):
                            deselectedConfigs.append(scn)
                    if len(maxDict[p]) < 0:
                        if float(parameterValue[scn][p]) > float(maxDict[p]):
                            deselectedConfigs.append(scn)
                n += 1
                   
            parameterInstance['parameter']= parameter 
            solverConfig[scn]= parameterInstance
        #chance the position
        if configForm != None:
            tmpList = paramList[:]
            for pl in paramList:
                pos0 = int(parameterPosition[pl][0])-1
                pos1 = int(parameterPosition[pl][1])-1
                if pos0 != pos1:
                    del tmpList[tmpList.index(pl)] 
                    tmpList.insert(pos1, pl)
            paramList = tmpList[:]
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
                iv = 0
                for v in values:
                    try:
                        values[iv] = float(v)
                        iv += 1
                    except:
                        ##TODO: im Fehlerfall hier vielleicht noch eine andere Loesung
                        values[iv] = 0.0 
                        iv += 1
                ivl = 0
                for vl in valueList:
                    try:
                        valueList[ivl] = float(vl)
                        ivl += 1
                    except:
                        ##TODO: im Fehlerfall hier vielleicht noch eine andere Loesung
                        valueList[ivl] = 0.0 
                        ivl += 1
                 
            if len(turnList)>0 and (str(pl) in turnList):
                turn = True
                values = turnValue(values)          
            
            #checks if a parameter is shielded
            hide = False
            if len(hideList)>0 and (str(pl) in hideList):
                hide = True
            
            positionList = []
            length = len(paramList)
            for p in range(length):
                pos = (p + i -1) % length
                positionList.append(pos+1)   
            
            if numValue < len(values):
                numValue = len(values)    
                        
            if domain[pl] == 'num': 
                if configForm != None and len(minDict[pl])>0:
                    if float(minDict[pl])>=min(valueList) and float(minDict[pl])<=max(valueList):
                        minValue = minDict[pl]
                    else:
                        minValue = min(valueList)    
                else:
                    minValue = min(valueList)
                
                if configForm != None and len(maxDict[pl])>0:
                    if float(maxDict[pl])>=min(valueList) and float(maxDict[pl])<=max(valueList):
                        maxValue = maxDict[pl]
                    else:
                        maxValue = max(valueList)
                else:
                    maxValue = max(valueList)
                if(parameterDomain[pl] == "integerDomain"):
                    minValue = int(minValue)
                    maxValue = int(maxValue)
                values = project(values)
                paramAttribute[i] = {'values': values,'min': minValue, 'max': maxValue,'name': parameterName[pl], 'id': pl, 'hide': hide, 'turn': turn, 'positionList': positionList, 'domain': 'num'}
                
            elif domain[pl] == 'cat':
                values = project(values)
                paramAttribute[i] = {'values': values,'valueList': valueList, 'selectValueList': selectValueList[pl],'name': parameterName[pl], 'id': pl, 'hide': hide, 'turn': turn, 'positionList': positionList, 'domain': 'cat'}
        
        configuration['paramAttribute'] = paramAttribute
        list = []
        for i in range(numValue):
            list.append(i)
        configuration['numValue'] = list
        if configForm != None:
            selectedConfigs = []
            for scn in solverConfigName:
                if scn not in deselectedConfigs:
                    if str(scn) in configList:
                        selectedConfigs.append([scn, solverConfigName[scn], 1])
                    else:
                        selectedConfigs.append([scn, solverConfigName[scn], 0])  
            configuration['solverConfigs'] = selectedConfigs
        else:
            selectedConfigs = []
            for scn in solverConfigName:
                selectedConfigs.append([scn, solverConfigName[scn], 0])
            configuration['solverConfigs'] = selectedConfigs
       
    def getConfiguration(self):
        return configuration
    