"""
    edacc.clientMonitor
    --------------------

    This module defines the monitor which shows experiment details.
    The Client Monitor shows which client are active and link the clients with the progress table.

    :copyright: (c) 2011 by Melanie Handel.
    :license: MIT, see LICENSE for details.
"""

import pygame
from math import *
from sqlalchemy import text, func

from edacc import utils, models, constants
from edacc.monitor import Canvas

NW = True

#test

#screensize
winWidth = 820
winHeight = 600
imageMap = {'db': (winHeight/2, winHeight/2)}

#calculate the radian for the inner and the outer circle of the diagram
#needs the number of diagramm on the circle and radius of the diagramm
def radian(radius, value):
    x = radius * cos((value) * 2 * pi) + winHeight/2
    y = radius * sin((value) * 2 * pi) + winHeight/2
    return x, y

#calculate the center of every circle diagram
def center(x, y, radiusDiagram):
    xy = x-radiusDiagram, y-radiusDiagram, x+radiusDiagram, y+radiusDiagram
    return xy


class ClientMonitor(Canvas):           
    
    def __init__(self, database, expID, **config):
        self.config(height = winHeight, width = winWidth)
        db = models.get_database(database) or abort(404)    
        
        maxRadiusDiagram = 50
        radiusClusterDiagram = 45
        radiusDBDiagram = 40
        
        radiusClient = winHeight/2-maxRadiusDiagram
        radiusCluster = radiusClient/2 
        clusterImageMap = []
        i = 1

        #Dictionary which store all clients for each experiment
        clientIsInExperimentName = {}
        clientIsInExperimentID = {}
        clusterHasClient = {}
        cluster = [] 
        for exp in expID:
            eClient = []
            expName = db.session.query(db.Experiment.name).filter(db.Experiment.idExperiment == exp).first()
            for e in db.session.query(db.Experiment_has_Client.Client_idClient).filter(db.Experiment_has_Client.Experiment_idExperiment == exp):
                eClient.append(e[0])
                clientIsInExperimentName[int(e[0])] = expName[0]
                clientIsInExperimentID[int(e[0])] = exp

        
        #Dictionary which store all clients for each grid
        for c in db.session.query(db.Client.gridQueue_idgridQueue).filter(db.Client.idClient == db.Experiment_has_Client.Client_idClient).filter(db.Experiment_has_Client.Experiment_idExperiment == exp):
            if int(c[0]) not in cluster:
                cluster.append(int(c[0]))   

        for clu in cluster:   
            cClient = [] 
            for c in db.session.query(db.Client.idClient).filter(db.Client.gridQueue_idgridQueue == clu):
                cClient.append(int(c[0]))    
            clusterHasClient[clu]=cClient        
        
        #Dictionary which store the locationname for each grid
        gridQueue =  dict((g.idgridQueue, g.location) for g in db.session.query(db.GridQueue).all())
                
        #returns a tuple out of ClientID, Timedifference in seconds
        timestampdiff = dict(db.session.query(db.Client.idClient, func.timestampdiff(text("SECOND"),db.Client.lastReport, func.now())).all())
        
        #double loop which draws the diagramm
        if len(clusterHasClient)== 1:
            numCluster = 2.0
        else:
            numCluster = float(len(clusterHasClient))
        
        #TODO: nach ExperimentID auswaehlen und ID an Webfrontend uebergeben    
        for c in clusterHasClient:
            clientImageMap = []
            j = 1
            clusterCenter = radian(radiusCluster, i/numCluster)
            self.create_line(winHeight/2, winHeight/2, clusterCenter)
            xy = center(clusterCenter[0], clusterCenter[1], radiusClusterDiagram)
            numClients = float(len(clusterHasClient[c]))
            for cID in clusterHasClient[c]:
                value = (2*i-1)/(2*numCluster)+j/(numCluster*numClients)
                clientCenter = radian(radiusClient, value-1/(2*numCluster*numClients))
                self.create_line(clusterCenter, clientCenter)
                rD = ((radiusClient * 3.14) / (numClients * numCluster)) -1
                if rD < maxRadiusDiagram:
                    radiusDiagram = rD
                else:
                    radiusDiagram = maxRadiusDiagram
                cxy = center(clientCenter[0], clientCenter[1], radiusDiagram)
                clientImageMap.append({"id": cID, "position": clientCenter, "radius": radiusDiagram, "exp": clientIsInExperimentID[cID]}) 
                if timestampdiff[cID]<= 10:
                    self.circle(cxy, 'active')
                elif timestampdiff[cID] > 10:
                    self.circle(cxy, 'passive')
                expText = clientIsInExperimentName[cID]
                self.create_text(clientCenter, text=expText)                  
                j = j + 1
            clusterImageMap.append({"id": str(c), "position": clusterCenter, "clients": clientImageMap}) 
            location = gridQueue[c]
            self.circleCluster(xy, location, radiusClusterDiagram)       
            i = i + 1   
            
        #draws the db point
        db_xy = center(winHeight/2, winHeight/2, radiusDBDiagram)
        self.circleCluster(db_xy, database, radiusDBDiagram)     
        imageMap['cluster'] = clusterImageMap 
       
    def getImageMap(self):
        return imageMap

    def circle(self, xy, status):
        if status == 'active':
            self.create_oval(xy, fill="green")
        elif status == 'passive':
            self.create_oval(xy, fill="red")


    def circleCluster(self, xy, location, radius):
        self.create_oval(xy, fill="white")
        self.create_text(xy[0]+radius, xy[1]+radius, text = location)
    
