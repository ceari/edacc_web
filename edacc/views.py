# -*- coding: utf-8 -*-

from flask import render_template as render
from flask import Response, abort, Headers

from edacc import app, plots
from edacc.models import session, Experiment, Solver, ExperimentResult, Instance
from edacc import config
from edacc.constants import JOB_FINISHED, JOB_ERROR

if config.CACHING:
    from werkzeug.contrib.cache import MemcachedCache
    cache = MemcachedCache([config.MEMCACHED_HOST])

@app.route('/')
def index():
    """ Show a list of all experiments in the database """
    experiments = session.query(Experiment).all()

    return render('experiments.html', experiments=experiments)
    
@app.route('/<int:experiment_id>/')
def experiment(experiment_id):
    """ Show menu with links to info and evaluation pages """
    
    return u'to be implemented'

@app.route('/<int:experiment_id>/solvers')
def experiment_solvers(experiment_id):
    """ Show information for all solvers used in the experiment """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    
    # remove duplicates introduced by a solver being used with more than one configuration
    solvers = list(set(sc.solver for sc in experiment.solver_configurations))
    solvers.sort(key=lambda s: s.name)
    
    return render('experiment_solvers.html', solvers=solvers)
    
@app.route('/<int:experiment_id>/instances')
def experiment_instances(experiment_id):
    """ Show information for all instances used in the experiment """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    
    instances = experiment.instances
    instances.sort(key=lambda i: i.name)
    
    return render('experiment_instances.html', instances=instances)

@app.route('/<int:experiment_id>/results')
def experiment_results(experiment_id):
    """ Show table with instances and solver configurations used in the experiment """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    
    instances = experiment.instances
    solver_configs = experiment.solver_configurations
    
    if config.CACHING:
        results = cache.get('experiment_results_' + str(experiment_id))
    else:
        results = None
    
    if results is None:
        results = []
        for instance in instances:
            row = []
            for solver_config in solver_configs:
                jobs = session.query(ExperimentResult) \
                                .filter_by(experiment=experiment) \
                                .filter_by(solver_configuration=solver_config) \
                                .filter_by(instance=instance) \
                                .all()
                completed = len(filter(lambda j: j.status in JOB_FINISHED or j.status in JOB_ERROR, jobs))
                time_avg = sum(j.time for j in jobs) / float(len(jobs))
                row.append({'time_avg': time_avg,
                            'completed': completed,
                            'total': len(jobs),
                            'solver_config': solver_config
                            })
            results.append({'instance': instance, 'times': row})
            
        if config.CACHING:
            cache.set('experiment_results_' + str(experiment_id), results, timeout=config.CACHE_TIMEOUT)
        
    return render('experiment_results.html', experiment=experiment,
                    instances=instances, solver_configs=solver_configs,
                    results=results)
    
@app.route('/instance/<int:instance_id>')
def instance_details(instance_id):
    """ Show instance details """
    instance = session.query(Instance).filter_by(idInstance=instance_id).first() or abort(404)
        
    instance_blob = instance.instance
    if len(instance_blob) > 1024:
        # show only the first and last 512 characters if the instance is larger than 1kB
        instance_text = instance_blob[:512] + "\n\n... [truncated " + str(int((len(instance_blob) - 1024) / 1024.0)) + " kB]\n\n" + instance_blob[-512:]
    else:
        instance_text = instance_blob
    
    return render('instance_details.html', instance=instance, instance_text=instance_text)
    
@app.route('/instance/<int:instance_id>/download')
def instance_download(instance_id):
    """ Return HTTP-Response containing the instance blob """
    instance = session.query(Instance).filter_by(idInstance=instance_id).first() or abort(404)
    
    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename=instance.name)
    
    return Response(response=instance.instance, headers=headers)

@app.route('/solver/<int:solver_id>')
def solver_details(solver_id):
    """ Show solver details """
    solver = session.query(Solver).get(solver_id) or abort(404)
    
    return render('solver_details.html', solver=solver)


@app.route('/imgtest')
def imgtest():
    import random
    random.seed()
    xs = random.sample(xrange(1200), 50)
    ys = random.sample(xrange(1200), 50)

    return Response(response=plots.scatter(xs,ys), mimetype='image/png')