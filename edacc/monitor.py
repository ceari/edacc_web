"""
    edacc.monitor
    --------------------

    This module defines the monitor which shows experiment details.
    It's a choice between normal mode and problem mode.

    :copyright: (c) 2011 by Melanie Handel.
    :license: MIT, see LICENSE for details.
"""

import pygame, time
from pygame import gfxdraw

pygame.font.init()
from math import *
from PIL import Image, ImageDraw

from sqlalchemy import func, text

from edacc import utils, models, constants

NW = True

#screensize
winWidth = 820
winHeight = 600
imageMap = {}
statusTable = {}

#calculate the radian for the inner and the outer circle of the diagram
def radian(radius, value):
    x = radius * cos((value) * 2 * pi) + winHeight / 2
    y = radius * sin((value) * 2 * pi) + winHeight / 2
    return x, y

#calculate the center of every circle diagram
def center(x, y, radiusDiagram):
    xy = x - radiusDiagram, y - radiusDiagram, x + radiusDiagram, y + radiusDiagram
    return xy

#calculate the extent of status in the circle diagram
def extent(numStatus):
    ges = 0
    e = []
    temp = 0.0
    for nS in numStatus:
        ges = ges + nS
    if (ges):
        for ns in numStatus:
            temp = (float(ns) / float(ges)) * 360
            e.append(temp)
    return e


class Canvas(object):
    def __init__(self, *args, **kwargs):
        pass

    def config(self, height, width):
        self.surf = pygame.Surface((width, height))
        self.surf.fill(pygame.Color("white"))

    def create_text(self, x, y=None, text="", anchor=None):
        if y is None: x, y = x
        font = pygame.font.Font(pygame.font.match_font("monospace"), 14)
        txtsurf = font.render(text, 1, pygame.Color("black"))
        if anchor:
            self.surf.blit(txtsurf, (x, y - txtsurf.get_height() / 2))
        else:
            self.surf.blit(txtsurf, (x - txtsurf.get_width() / 2, y - txtsurf.get_height() / 2))

    def create_rectangle(self, x1, y1, x2, y2, width=1, fill=None):
        pygame.draw.rect(self.surf, pygame.Color(fill), pygame.Rect(x1, y1, x2 - x1, y2 - y1), 0)
        if fill:
            pygame.draw.rect(self.surf, pygame.Color("black"), pygame.Rect(x1, y1, x2 - x1, y2 - y1), width)

    def create_line(self, fr, to, x2=None):
        if x2 is not None:
            pygame.draw.line(self.surf, pygame.Color("black"), (fr, to), (x2[0], x2[1]))
        else:
            pygame.draw.line(self.surf, pygame.Color("black"), fr, to)

    def create_oval(self, xy, fill="white"):
        x1, y1, x2, y2 = xy
        pygame.draw.ellipse(self.surf, pygame.Color(fill), pygame.Rect(x1, y1, x2 - x1, y2 - y1), 0)
        pygame.draw.ellipse(self.surf, pygame.Color("black"), pygame.Rect(x1, y1, x2 - x1, y2 - y1), 1)

    def create_arc(self, xy, start, extent, fill):
        if len(xy) == 3: # centerX, centerY, radius format
            x1 = xy[0]
            y1 = xy[1]
            x2, y2 = xy[2] * 2, xy[2] * 2
        else:
            x1, y1, x2, y2 = map(int, xy)
        img = Image.new('RGB', ((x2 - x1), (y2 - y1)))
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, x2 - x1, y2 - y1), outline=(255, 105, 180), fill=(255, 105, 180))
        draw.pieslice((0, 0, x2 - x1, y2 - y1), int(start), int(start + extent), outline=fill, fill=fill)
        srf = pygame.image.fromstring(img.tostring(), img.size, img.mode)
        srf.set_colorkey((255, 105, 180))
        if len(xy) == 3:
            self.surf.blit(srf, (x1 + xy[2] / 2, y1 + xy[2] / 2))
        else:
            self.surf.blit(srf, (x1, y1))

    def pack(self, *args, **kwargs):
        pass

    def save(self, file, *args, **kwargs):
        pygame.image.save(self.surf, file)


class Monitor(Canvas):
    def __init__(self, database, status, expID, **config):
        self.config(height=winHeight, width=winWidth)
        db = models.get_database(database) or abort(404)

        radiusDiagram = 0
        maxRadiusDiagram = 50
        clusterRadiusDiagram = 45
        dbRadiusDiagram = 40
        radiusClient = winHeight / 2 - maxRadiusDiagram
        radiusExpID = radiusClient - maxRadiusDiagram
        radiusCluster = radiusClient / 2

        imageMap['db'] = ({"id": str(database), "position": (winHeight / 2, winHeight / 2), "radius": dbRadiusDiagram})

        expName = {}
        numDBStatus = []
        dbTable = {}
        cluster = []
        numClusterStatus = []
        clusterImageMap = []
        problemStatus = []
        problemText = []
        numDBJobs = 0.0
        i = 0
        m = 0
        q = 0
        y1 = 6
        y2 = 16

        #TODO: db Abfrage Job Status, gridQueue, Cluster passend zu expID
        #all database queries
        JOB_STATUS = dict((s.statusCode, s.description) for s in db.session.query(db.StatusCodes).all())
        gridQueue = dict((g.idgridQueue, g.location) for g in db.session.query(db.GridQueue).all())

        for eID in expID:
            expName[eID] = db.session.query(db.Experiment.name).filter(db.Experiment.idExperiment == eID).first()
            for cQueue in db.session.query(db.ExperimentResult.computeQueue).filter(
                            db.ExperimentResult.Experiment_idExperiment == eID).distinct():
                if (cQueue[0] is not None and int(cQueue[0]) not in cluster):
                    if (cQueue[0] is not None) and (cQueue[0] != 0):
                        cluster.append(cQueue[0])
        if len(cluster) == 1:
            numCluster = 2.0
        else:
            numCluster = float(len(cluster))
            #Legend
        if status == ['pm']:
            problemStatus = [-2, -1, 0]
            problemText = ['crashed', 'blocked', 'forever running']
            for t, s in zip(problemText, problemStatus):
                numClusterStatus.append(0)
                numDBStatus.append(0)
                self.create_text(winWidth - 100, y1 + 4, text=t, anchor=NW)
                self.create_rectangle(winWidth - 115, y1, winWidth - 105, y2, width=1,
                                      fill=constants.JOB_STATUS_COLOR[s])
                y1 = y1 + 26
                y2 = y2 + 26
        else:
            status = map(int, status)
            for c in status:
                numClusterStatus.append(0)
                numDBStatus.append(0)
                self.create_text(winWidth - 100, y1 + 4, text=JOB_STATUS[c], anchor=NW)
                self.create_rectangle(winWidth - 115, y1, winWidth - 105, y2, width=1,
                                      fill=constants.JOB_STATUS_COLOR[c])
                y1 = y1 + 26
                y2 = y2 + 26



        #paint the diagram in an double for-loop, outer circle is the client circle, inner circle is the cluster circle
        for c in cluster:
            clientID = []
            clientExpID = []
            clientExpName = []
            clientImageMap = []
            clusterStatusTable = {}
            numClusterJobs = 0.0
            j = 1
            l = 0
            i = i + 1

            clusterCenter = radian(radiusCluster, i / numCluster)
            self.create_line(winHeight / 2, winHeight / 2, clusterCenter)
            xy = center(clusterCenter[0], clusterCenter[1], clusterRadiusDiagram)

            #TODO: db Abfrage, Clients passend zu Cluster
            for eID in expID:
                exp = db.session.query(db.Experiment).get(eID)
                for client in exp.clients:
                    if (client.gridQueue_idgridQueue == c):
                        if (str(client.idClient) not in clientID) and (int(client.idClient) != 0):
                            clientID.append(str(client.idClient))
                            name = expName[eID]
                            clientExpName.append(name[0])
                            clientExpID.append(eID)
            numClients = float(len(clientID))

            for cID, eID in zip(clientID, clientExpID):
                clientStatusTable = {}
                numClientStatus = []
                numClientJobs = 0.0
                k = 0

                value = (2 * i - 1) / (2 * numCluster) + j / (numCluster * numClients)
                clientCenter = radian(radiusClient, value - 1 / (2 * numCluster * numClients))
                expIDCenter = radian(radiusExpID, value - 1 / (2 * numCluster * numClients))
                self.create_line(clusterCenter, clientCenter)
                rD = ((radiusClient * 3.14) / (numClients * numCluster)) - 1
                if rD < maxRadiusDiagram:
                    radiusDiagram = rD
                else:
                    radiusDiagram = maxRadiusDiagram
                cxy = center(clientCenter[0], clientCenter[1], radiusDiagram)
                clientImageMap.append({"id": cID, "position": clientCenter, "radius": radiusDiagram})

                clientStatusTable['expID'] = expName[eID][0]
                clientSTable = []
                if status == ['pm']:
                    problemCount = []
                    #TODO: dbAbfrage, Problemmodus, Statusanzeige

                    crashed = db.session.query(db.ExperimentResult.status).filter(
                        db.ExperimentResult.status < -1).filter(db.ExperimentResult.computeNode == eID).count()
                    problemCount.append(crashed)
                    blocked = db.session.query(db.ExperimentResult.status).filter(
                        db.ExperimentResult.status == -1).filter(db.ExperimentResult.priority < 0).filter(
                        db.ExperimentResult.computeNode == eID).count()
                    problemCount.append(blocked)

                    foreverRunning = db.session.query(db.ExperimentResult.status) \
                        .filter(db.ExperimentResult.status == 0).filter(
                        func.timestampdiff(text("SECOND"), db.ExperimentResult.startTime, func.now()) \
                        > db.ExperimentResult.CPUTimeLimit + 20) \
                        .filter(db.ExperimentResult.computeNode == cID).count()
                    problemCount.append(foreverRunning)

                    for pC in problemCount:
                        numClientJobs += pC
                    p = 0
                    for pC, cT in zip(problemCount, problemText):
                        if (numClientJobs):
                            perc = round((pC / numClientJobs) * 10000)
                            perc = perc / 100
                        else:
                            perc = 0
                        numClientStatus.append(pC)
                        numClusterStatus[k] = numClusterStatus[k] + pC
                        clientSTable.append({"name": cT, "val": int(pC), "perc": str(perc) + '%'})
                        k = k + 1
                    clientStatusTable['table'] = clientSTable
                    self.circleDiagram(cxy, problemStatus, numClientStatus, expName[eID][0], radiusDiagram)
                else:
                    for s in status:
                        #TODO: db Abfrage, Gesamtanzahl der Clients//
                        numClientJobs = numClientJobs + db.session.query(db.ExperimentResult.status).filter(
                            db.ExperimentResult.computeNode == cID).filter(db.ExperimentResult.status == s).count()
                    for s in status:
                        #TODO: db Abfrage, Anzahl der Clients
                        count = float(
                            db.session.query(db.ExperimentResult.status).filter(db.ExperimentResult.status == s).filter(
                                db.ExperimentResult.computeNode == cID).count())
                        if (numClientJobs):
                            perc = round((count / numClientJobs) * 10000)
                            perc = perc / 100
                        else:
                            perc = 0

                        name = JOB_STATUS[s]
                        numClientStatus.append(count)
                        numClusterStatus[k] = numClusterStatus[k] + count
                        clientSTable.append({"name": name, "val": int(count), "perc": str(perc) + '%'})
                        k = k + 1
                    clientStatusTable['table'] = clientSTable
                    self.circleDiagram(cxy, status, numClientStatus, expName[eID][0], radiusDiagram)
                numClusterJobs = numClusterJobs + numClientJobs
                statusTable[cID] = clientStatusTable

                j = j + 1

            numDBJobs += numClusterJobs
            liste = list(set(clientExpName))

            clusterStatusTable['expID'] = liste
            q += 1
            if status == ['pm']:
                clusterStatus = problemStatus
            else:
                clusterStatus = status
            if c in gridQueue:
                location = gridQueue[c]
            else:
                location = str(c)
            self.circleDiagram(xy, clusterStatus, numClusterStatus, location, clusterRadiusDiagram)
            clusterSTable = []
            for s in clusterStatus:
                count = numClusterStatus[l]
                numClusterStatus[l] = 0
                numDBStatus[l] = numDBStatus[l] + count
                if (numClusterJobs):
                    perc = round((count / numClusterJobs) * 10000)
                    perc = perc / 100
                else:
                    perc = 0

                name = JOB_STATUS[s]

                clusterSTable.append({"name": name, "val": int(count), "perc": str(perc) + '%'})
                l = l + 1
            clusterStatusTable['table'] = clusterSTable

            if c in gridQueue:
                location = gridQueue[c]
            else:
                location = str(c)

            clusterImageMap.append(
                {"id": location, "position": clusterCenter, "clients": clientImageMap, "radius": radiusDiagram})
            statusTable[location] = clusterStatusTable
        imageMap['cluster'] = clusterImageMap

        #database
        db_xy = center(winHeight / 2, winHeight / 2, dbRadiusDiagram)

        name = expName.values()
        dbTable['expID'] = name
        if status == ['pm']:
            dbStatus = problemStatus
        else:
            dbStatus = status
        dbSTable = []
        for s in dbStatus:
            count = numDBStatus[m]
            m = m + 1

            name = JOB_STATUS[s]
            if (numDBJobs):
                perc = round((count / numDBJobs) * 10000)
                perc = perc / 100
            else:
                perc = 0
            dbSTable.append({"name": name, "val": int(count), "perc": str(perc) + '%'})
        dbTable['table'] = dbSTable
        statusTable[str(database)] = dbTable
        self.circleDiagram(db_xy, dbStatus, numDBStatus, database, dbRadiusDiagram)

    def getImageMap(self):
        return imageMap

    def getTable(self):
        return statusTable

    def circleDiagram(self, xy, status, numStatus, location, radius):
        s = 0.0
        extentStatus = extent(numStatus)
        self.create_oval(xy, fill="white")
        for e, c in zip(extentStatus, status):
            if e == 360.0:
                self.create_oval(xy, fill=constants.JOB_STATUS_COLOR[c])
            else:
                id = self.create_arc(xy, start=s, extent=e, fill=constants.JOB_STATUS_COLOR[c])
                s = s + e
        self.create_text(xy[0] + radius, xy[1] + radius, text=location)



       