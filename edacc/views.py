# -*- coding: utf-8 -*-

from flask import render_template as render
from flask import Response, abort

from edacc import app, plots
from edacc.models import session, Experiment, Solver, ExperimentResult
from edacc import config

if config.CACHING:
    from werkzeug.contrib.cache import MemcachedCache
    cache = MemcachedCache([config.MEMCACHED_HOST])

@app.route('/')
def index():
    # show a list of all experiments in the database
    experiments = session.query(Experiment).all()

    return render('experiments.html', experiments=experiments)
    
@app.route('/<int:experiment_id>')
def experiment(experiment_id):
    # show menu with links to info and evaluation pages
    
    return u'to be implemented'

@app.route('/<int:experiment_id>/results')
def experiment_results(experiment_id):
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
                time_avg = sum(j.time for j in jobs) / float(len(jobs))
                row.append({'time_avg': time_avg})
            results.append({'instance': instance, 'times': row})
            
        if config.CACHING:
            cache.set('experiment_results_' + str(experiment_id), results, timeout=config.CACHE_TIMEOUT)
        
    return render('experiment_results.html', experiment=experiment,
                    instances=instances, solver_configs=solver_configs,
                    results=results)



@app.route('/imgtest')
def imgtest():
    return Response(response=plots.draw(), mimetype='image/png')