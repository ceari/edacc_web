"""
    edacc.configurator_view
    --------------------

    This module defines the view which shows configuration details.
    
    :copyright: (c) 2011 by Melanie Handel.
    :license: MIT, see LICENSE for details.
"""

from edacc import utils, models, constants
import math

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
def project(values, maxVal):
    values = map(float, values)
    if maxVal != 0:
        j = 0
        tmp = 1/float(maxVal)
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
    def __init__(self, database, expID, configForm, standardize):
        db = models.get_database(database) or abort(404)   
        experiment = db.session.query(db.Experiment).get(expID) or abort(404)
        if experiment.configurationExp == False: return # kein Konfiguratorexperiment
        solverConfig = {}
        paramAttribute = {}
        parameterValue = {}
        parameterName = {}
        paramList = []
        numValue = 0
        minDict = {}
        maxDict = {}
        selectValueList = {}
        deselectedConfigs = []
        choosenConfigs = []
        turnList = []
        hideList = []
        configList = [] 
        domain = {}
        parameterDomain = {}
        parameterPosition = {}
        page = 0
        absMax = 0
        negNum = 0

        #db Queries for configuration visualisation
        name = db.session.query(db.Experiment.name).filter(db.Experiment.idExperiment == expID).first()
        configuration['expName'] = str(name[0])
        configuration['standardize'] = standardize
        
        if configForm == None:
            configuration['page'] = page
        else:
            page = map(int, configForm.getlist("page"))[0]+1
            configuration['page'] = page
            minDict['confidence'] = map(str, configForm.getlist("min_confidence"))[0]
            maxDict['confidence'] = map(str, configForm.getlist("max_confidence"))[0]  
            minDict['performance'] = map(str, configForm.getlist("min_performance"))[0]
            maxDict['performance'] = map(str, configForm.getlist("max_performance"))[0]  

        paramList.append('confidence')
        paramList.append('performance') 
        
        parameterDomain['confidence']= "integerDomain"
        parameterDomain['performance']= "realDomain"
        
        solverConfigCosts = dict((s.idSolverConfig, s.cost) for s in experiment.solver_configurations)                 
        solverConfigName =  dict((s.idSolverConfig, s.name) 
                        for s in db.session.query(db.SolverConfiguration).
                            filter(db.SolverConfiguration.Experiment_idExperiment == expID))
        if page == 0:
            choosenConfigs = solverConfigName.keys()
                                
        for scn in solverConfigName:
            count = int(db.session.query(db.ExperimentResult.idJob).
                            filter(db.ExperimentResult.SolverConfig_idSolverConfig == scn).count())
            parameterValue[scn]= {'confidence': count}
            
            if solverConfigCosts[scn] != None:
                parameterValue[scn].update({'performance': solverConfigCosts[scn] })
            else:
                parameterValue[scn].update({'performance': 0.0 })
                
            #deselect solverConfigs which aren't in the range of choosen confidence or performance
            if page > 0:
                if count >= int(minDict['confidence']) and count <= int(maxDict['confidence']) and float(parameterValue[scn]['performance']) >= float(minDict['performance']) and float(parameterValue[scn]['performance']) <= float(maxDict['performance']):
                    choosenConfigs.append(scn)
                else:
                    deselectedConfigs.append(scn)

        if page > 0:
            configurable = [p.Parameters_idParameter for p in experiment.configuration_scenario.parameters if p.configurable and p.parameter.name not in ('instance', 'seed')]
            parameterName  =  dict((p.idParameter, p.name) 
                            for p in db.session.query(db.Parameter).
                                filter(db.Parameter.idParameter.in_(configurable)).distinct())
            for id in parameterName.keys():
                parameterDomain[id] = experiment.configuration_scenario.get_parameter_domain(parameterName[id])

            paramInstance = db.session.query(db.ParameterInstance).filter(db.ParameterInstance.SolverConfig_idSolverConfig.in_(choosenConfigs)).all()   
            
            for pv in paramInstance:
                if pv.Parameters_idParameter not in parameterName.keys() or pv.value == "": continue
                if pv.SolverConfig_idSolverConfig not in parameterValue: 
                    parameterValue[pv.SolverConfig_idSolverConfig] = {}
                parameterValue[pv.SolverConfig_idSolverConfig].update({pv.Parameters_idParameter: pv.value})
                if pv.Parameters_idParameter not in paramList:
                    paramList.append(pv.Parameters_idParameter)        
    
        
        parameterName.update({'confidence': 'confidence', 'performance': 'performance'})
               
        for pd in parameterDomain.keys():
                selectValueList[pd]= []
                if parameterDomain[pd] == "realDomain" or parameterDomain[pd] == "integerDomain":
                    domain[pd] = 'num'
                else:
                    domain[pd] = 'cat'
                       
        #maps the web formular in lists
        if page > 1:
            for pm in paramList: 
                if str(pm) in configForm.keys():
                    tmpList = mapPosition(configForm.getlist(str(pm))) 
                    parameterPosition[tmpList[0]] = [pm, tmpList[1]]                  
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
        for scn in choosenConfigs:
            parameterInstance = {} 
            parameter = {}
            
            parameterInstance['name'] = str(solverConfigName[scn])
            n = 2
            for p in parameterValue[scn]: 
                #assigns the value to the parameter of the solverConfig
                parameter[p]= str(parameterValue[scn][p])
                    
            #creates the list deselectedConfigs of solverConfigs which are deselected if the values are restricted
                if page > 1 and domain[p] == 'cat':
                    if "select_"+str(p) in configForm.keys():                 
                        if str(parameterValue[scn][p]) not in selectValueList[p]:
                            deselectedConfigs.append(scn)

                elif page > 1 and domain[p] == 'num':
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
        if page > 1:
            formerPosition = []
            for pp in parameterPosition:
                #create a list with parameter id in the former order
                formerPosition.append(parameterPosition[pp][0])
            for pp in parameterPosition:
                requestedPosition = parameterPosition[pp][1]
                paramID = parameterPosition[pp][0]
                if pp != requestedPosition:
                    del formerPosition[formerPosition.index(paramID)] 
                    formerPosition.insert((requestedPosition-1), paramID)
            paramList = formerPosition[:]
        
        i=0
        for pl in paramList:
            values = []
            valueList = []
            expectedValue = 0.0 
            variance = 0.0    
            minValue = 0
            maxValue = 0
            turn = False
            i += 1
            
            #creates a list of possible values (valueList) and an list of values for each parameter
            for scn in choosenConfigs:
                if (pl in solverConfig[scn]['parameter']):
                    tmp = solverConfig[scn]['parameter'][pl]
                    if (tmp not in valueList):
                        valueList.append(tmp)
                    if scn not in deselectedConfigs:
                        values.append(tmp)
                        if(domain[pl] == 'num'):
                            if standardize == 1:
                                expectedValue = expectedValue + float(tmp)
                else:
                    if scn not in deselectedConfigs:
                        values.append(0)
            if len(valueList) == 0:
                valueList.append(0)
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
                        values[iv] = 0.0 
                        iv += 1
                ivl = 0
                for vl in valueList:
                    try:
                        valueList[ivl] = float(vl)
                        ivl += 1
                    except:
                        valueList[ivl] = 0.0 
                        ivl += 1
                 
            if len(turnList)>0 and (str(pl) in turnList):
                turn = True
                values = turnValue(values)     
            
            #checks if a parameter is hidden
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
                if page > 1 and len(minDict[pl])>0 and float(minDict[pl])>=min(valueList) and float(minDict[pl])<=max(valueList):
                    minValue = minDict[pl]
                elif len(choosenConfigs) == 0:
                    minValue = minDict[pl]
                else:
                    minValue = min(valueList)
                if page > 1 and len(maxDict[pl])>0 and float(maxDict[pl])>=min(valueList) and float(maxDict[pl])<=max(valueList):
                        maxValue = maxDict[pl]
                elif len(choosenConfigs) == 0:
                    maxValue = maxDict[pl]
                else:
                    maxValue = max(valueList)
                if(parameterDomain[pl] == "integerDomain"):
                    minValue = int(minValue)
                    maxValue = int(maxValue)
                if standardize == 1:
                    negNum = 1
                    expectedValue = expectedValue / len(values)
                    for v in values:
                        variance = variance + (v - expectedValue)**2
                    variance = math.sqrt(variance/len(values))
                    standardScore = lambda x: (x-expectedValue)/variance if variance != 0 else 0
                    values = map(standardScore, values) 
                    
                else:
                    if min(values) < 0:
                        negNum = 1
                    if math.fabs(min(values))>max(values):
                        values = project(values, math.fabs(min(values)))
                    else:
                        values = project(values, max(values))
                if max(values)>absMax:
                    absMax = max(values)
                if math.fabs(min(values))>absMax:
                    absMax = math.fabs(min(values))
                paramAttribute[i] = {'values': values,'min': minValue, 'max': maxValue,'name': parameterName[pl], 'id': pl, 'hide': hide, 'turn': turn, 'positionList': positionList, 'domain': 'num'}
                
            elif domain[pl] == 'cat':
                values = project(values, max(values))
                paramAttribute[i] = {'values': values,'valueList': valueList, 'selectValueList': selectValueList[pl],'name': parameterName[pl], 'id': pl, 'hide': hide, 'turn': turn, 'positionList': positionList, 'domain': 'cat'}
        if standardize == 1:
            for ri in range(i):
                if paramAttribute[ri+1]['domain'] == 'num':
                    paramAttribute[ri+1]['values'] = project(paramAttribute[ri+1]['values'], absMax)

        configuration['paramAttribute'] = paramAttribute
        list = []
        for i in range(numValue):
            list.append(i)
        configuration['numValue'] = list
        configuration['negNum'] = negNum
        if page > 1:
            selectedConfigs = []
            for scn in choosenConfigs:
                if scn not in deselectedConfigs:
                    if str(scn) in configList:
                        selectedConfigs.append([scn, solverConfigName[scn], 1])
                    else:
                        selectedConfigs.append([scn, solverConfigName[scn], 0])  
            configuration['solverConfigs'] = selectedConfigs
        else:
            selectedConfigs = []
            for scn in choosenConfigs:
                selectedConfigs.append([scn, solverConfigName[scn], 0])
            configuration['solverConfigs'] = selectedConfigs
       
    def getConfiguration(self):
        return configuration
    