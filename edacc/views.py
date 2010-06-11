# -*- coding: utf-8 -*-

from flask import render_template as render
from flask import Response, abort, Headers, Environment, request

from edacc import app, plots, config, utils
from edacc.models import session, Experiment, Solver, ExperimentResult, Instance, SolverConfiguration
from edacc.constants import JOB_FINISHED, JOB_ERROR

if config.CACHING:
    from werkzeug.contrib.cache import MemcachedCache
    cache = MemcachedCache([config.MEMCACHED_HOST])

@app.route('/')
def index():
    """ Show a list of all experiments in the database """
    experiments = session.query(Experiment).all()

    return render('experiments.html', experiments=experiments)
    
@app.route('/experiment/<int:experiment_id>/')
def experiment(experiment_id):
    """ Show menu with links to info and evaluation pages """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    
    return render('experiment.html', experiment=experiment)

@app.route('/experiment/<int:experiment_id>/solvers')
def experiment_solvers(experiment_id):
    """ Show information for all solvers used in the experiment """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    
    # remove duplicates introduced by a solver being used with more than one configuration
    solvers = list(set(sc.solver for sc in experiment.solver_configurations))
    solvers.sort(key=lambda s: s.name)
    
    return render('experiment_solvers.html', solvers=solvers)
    
@app.route('/experiment/<int:experiment_id>/solver-configurations')
def experiment_solver_configurations(experiment_id):
    """ List all solver configurations (solver + parameter set) used in the experiment """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    
    solver_configurations = experiment.solver_configurations
    solver_configurations.sort(key=lambda sc: sc.solver.name.lower())
    
    return render('experiment_solver_configurations.html', experiment=experiment, solver_configurations=solver_configurations)
    
@app.route('/experiment/<int:experiment_id>/instances')
def experiment_instances(experiment_id):
    """ Show information for all instances used in the experiment """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    
    instances = experiment.instances
    instances.sort(key=lambda i: i.name)
    
    return render('experiment_instances.html', instances=instances)

@app.route('/experiment/<int:experiment_id>/results')
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
    
@app.route('/experiment/<int:experiment_id>/result/<int:solver_configuration_id>/<int:instance_id>')
def solver_config_results(experiment_id, solver_configuration_id, instance_id):
    """ Displays list of results (all jobs) for a solver configuration and instance """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    solver_configuration = session.query(SolverConfiguration).get(solver_configuration_id) or abort(404)
    instance = session.query(Instance).filter_by(idInstance=instance_id).first() or abort(404)
    if solver_configuration not in experiment.solver_configurations: abort(404)
    if instance not in experiment.instances: abort(404)
    
    jobs = session.query(ExperimentResult) \
                    .filter_by(experiment=experiment) \
                    .filter_by(solver_configuration=solver_configuration) \
                    .filter_by(instance=instance) \
                    .all()
    
    completed = len(filter(lambda j: j.status in JOB_FINISHED or j.status in JOB_ERROR, jobs))
    
    return render('solver_config_results.html', experiment=experiment, solver_configuration=solver_configuration,
                  instance=instance, results=jobs, completed=completed)
    
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
    
    return render('instance_details.html', instance=instance, instance_text=instance_text, blob_size=len(instance.instance))
    
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

@app.route('/experiment/<int:experiment_id>/solver-configurations/<int:solver_configuration_id>')
def solver_configuration_details(experiment_id, solver_configuration_id):
    """ Show solver configuration details """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    solver_config = session.query(SolverConfiguration).get(solver_configuration_id) or abort(404)
    solver = solver_config.solver
    parameters = solver_config.parameter_instances
    parameters.sort(key=lambda p: p.parameter.order)
    
    def launch_command(solver, parameters):
        """ returns a string of what the solver launch command looks like """
        args = []
        for p in parameters:
            args.append(p.parameter.prefix)
            if p.parameter.hasValue:
                if p.value == "": # if value not set, use default value from parameters table
                    args.append(p.parameter.value)
                else:
                    args.append(p.value)
        return "./" + solver.binaryName + " " + " ".join(args)
    
    return render('solver_configuration_details.html', launch_command=launch_command(solver, parameters),
                  solver_config=solver_config, solver=solver, parameters=parameters,)
    

@app.route('/imgtest/<int:experiment_id>')
def imgtest(experiment_id):
    exp = session.query(Experiment).get(experiment_id) or abort(404)
    import random
    random.seed()
    
    # 2 random solverconfigs
    sc1 = random.choice(exp.solver_configurations)
    sc2 = random.choice(exp.solver_configurations)
    
    results1 = session.query(ExperimentResult).filter_by(experiment=exp, solver_configuration=sc1)
    results2 = session.query(ExperimentResult).filter_by(experiment=exp, solver_configuration=sc2)
    xs = []
    ys = []
    for instance in exp.instances:
        r1 = results1.filter_by(instance=instance).all()[0].time
        r2 = results2.filter_by(instance=instance).all()[0].time
        xs.append(r1)
        ys.append(r2)
    
    if request.args.has_key('pdf'):
        headers = Headers()
        headers.add('Content-Disposition', 'attachment', filename=sc1.solver.name + '_vs_' + sc2.solver.name + '.pdf')
        return Response(response=plots.scatter(xs,ys,sc1.solver.name,sc2.solver.name, format='pdf'), mimetype='application/pdf', headers=headers)
    elif request.args.has_key('svg'):
        return Response(response=plots.scatter(xs,ys,sc1.solver.name,sc2.solver.name, format='svg'), mimetype='image/svg+xml')
    else:
        p = plots.scatter(xs,ys,sc1.solver.name,sc2.solver.name)
        return Response(response=p, mimetype='image/png')