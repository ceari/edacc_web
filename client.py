#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Simple EDACC client fetching a random job from an experiment for testing purposes """

import time, sys, subprocess, os, resource, StringIO, shlex, threading, multiprocessing
from datetime import datetime
from edacc import models
from edacc.utils import launch_command
from sqlalchemy.sql.expression import func

def setlimits(cputime, mem):
    resource.setrlimit(resource.RLIMIT_CPU, (cputime, cputime + 10))
    resource.setrlimit(resource.RLIMIT_AS, (mem, mem))

def fetch_resources(experiment_id, db):
    try:
        os.mkdir('/tmp/edacc')
        os.mkdir('/tmp/edacc/solvers')
        os.mkdir('/tmp/edacc/instances')
    except: pass
    
    experiment = db.session.query(db.Experiment).get(experiment_id)
    
    for i in experiment.instances:
        if not os.path.exists('/tmp/edacc/instances/' + i.name):
            f = open('/tmp/edacc/instances/' + i.name, 'w')
            f.write(i.instance)
            f.close()
    
    for s in set(sc.solver for sc in experiment.solver_configurations):
        if not os.path.exists('/tmp/edacc/solvers/' + s.binaryName):
            f = open('/tmp/edacc/solvers/' + s.binaryName, 'w')
            f.write(s.binary)
            f.close()
            os.chmod('/tmp/edacc/solvers/' + s.binaryName, 0744)
            
class EDACCClient(threading.Thread):
    count = 0
    def __init__(self, experiment_id, db):
        super(EDACCClient, self).__init__(group=None)
        self.experiment = db.session.query(db.Experiment).get(experiment_id)
        self.name = str(EDACCClient.count)
        self.db = db
        EDACCClient.count += 1
        
    def run(self):
        if self.experiment is None: return
        experiment = self.experiment
        db = self.db
        while True:
            job = None
            try:
                job = db.session.query(db.ExperimentResult) \
                        .filter_by(experiment=self.experiment) \
                        .filter_by(status=-1) \
                        .order_by(func.rand()).limit(1).first()
                job.status = 0
                db.session.commit()
            except:
                db.session.rollback()
        
            if job:
                job.startTime = func.now()
                db.session.commit()
                
                client_line = '/usr/bin/time -f ";%U;" '
                client_line += '/tmp/edacc/solvers/' + launch_command(job.solver_configuration)[2:]
                client_line += '/tmp/edacc/instances/' + job.instance.name + ' ' + str(job.seed)
                print "running job", job.idJob, client_line
                stdout = open(self.name + 'stdout~', 'w')
                stderr = open(self.name + 'stderr~', 'w')
                start = time.time()
                p = subprocess.Popen(shlex.split(client_line), preexec_fn=setlimits(experiment.timeOut, experiment.memOut * 1024 * 1024), stdout = stdout, stderr = stderr)
                p.wait()
                print "Job", job.idJob, "done .. Realtime:", str(time.time() - start), "s"
                stdout.close()
                stderr.close()
                
                stdout = open(self.name + 'stdout~', 'r')
                stderr = open(self.name + 'stderr~', 'r')
                time_output = stderr.read()
                tstart = time_output.find(";")
                tend = time_output.find(";", tstart+1)
                runtime = float(time_output[tstart+1:tend])
                
                job.resultFile = stdout.read()
                stdout.close()
                stderr.close()
                
                job.time = runtime
                
                cpuinfo = open('/proc/cpuinfo')
                job.clientOutput = cpuinfo.read()
                cpuinfo.close()
                
                print "retcode", p.returncode
                
                if p.returncode == 24:
                    job.status = 2
                else:
                    job.status = 1
                print "             CPU time:", runtime, "s"
                db.session.commit()
            else:
                if db.session.query(db.ExperimentResult) \
                        .filter_by(experiment=self.experiment) \
                        .filter_by(status=-1) \
                        .order_by(func.rand()).count() == 0: break
            
    

if __name__ == '__main__':
    username = raw_input('Enter database username: ').strip()
    password = raw_input('Enter password: ').strip()
    database = raw_input('Enter database name: ').strip()
    try:
        models.add_database(username, password, database,'')
    except Exception as e:
        print "Can't connect to database: " + str(e)
        sys.exit(0)
    db = models.get_database(database)
    
    exp_name = raw_input('Enter experiment name: ').strip()
    experiment = db.session.query(db.Experiment).filter_by(name=exp_name).first()
    
    if experiment is None:
        print "Experiment doesn't exist"
        sys.exit(0)
    
    exp_id = experiment.idExperiment
    
    fetch_resources(exp_id, db)
    
    print "Starting up .. using " + str(experiment.grid_queue[0].numCPUs) + " threads"
    clients = [EDACCClient(exp_id, db) for _ in xrange(experiment.grid_queue[0].numCPUs)]
    for c in clients:
        c.start()
    for c in clients:
        c.join()
