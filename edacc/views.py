# -*- coding: utf-8 -*-

import json, time, hashlib, os

from flask import render_template as render
from flask import Response, abort, Headers, Environment, request, session

from edacc import app, plots, config, utils
from edacc.models import session, Experiment, Solver, ExperimentResult, Instance, SolverConfiguration, joinedload
from edacc.constants import JOB_FINISHED, JOB_ERROR

if config.CACHING:
    from werkzeug.contrib.cache import MemcachedCache
    cache = MemcachedCache([config.MEMCACHED_HOST])
    
@app.before_request
def make_unique_id():
    """ Attach an unique ID to the request (hash of current server time and request headers) """
    hash = hashlib.md5()
    hash.update(str(time.time()) + str(request.headers))
    request.unique_id = hash.hexdigest()

@app.after_request
def shutdown_session(response):
    session.remove()
    return response

@app.route('/')
def index():
    """ Show a list of all experiments in the database """
    experiments = session.query(Experiment).all()
    experiments.sort(key=lambda e: e.name.lower())

    return render('experiments.html', experiments=experiments)
    
@app.route('/experiment/<int:experiment_id>/')
def experiment(experiment_id):
    """ Show menu with links to info and evaluation pages """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    
    return render('experiment.html', experiment=experiment)

@app.route('/experiment/<int:experiment_id>/solvers')
def experiment_solvers(experiment_id):
    """ Show a list of all solvers used in the experiment """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    
    # remove duplicates introduced by a solver being used with more than one configuration
    solvers = list(set(sc.solver for sc in experiment.solver_configurations))
    solvers.sort(key=lambda s: s.name)
    
    return render('experiment_solvers.html', solvers=solvers, experiment=experiment)
    
@app.route('/experiment/<int:experiment_id>/solver-configurations')
def experiment_solver_configurations(experiment_id):
    """ List all solver configurations (solver + parameter set) used in the experiment """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    
    solver_configurations = experiment.solver_configurations
    solver_configurations.sort(key=lambda sc: sc.solver.name.lower())
    
    return render('experiment_solver_configurations.html', experiment=experiment, solver_configurations=solver_configurations)
    
@app.route('/experiment/<int:experiment_id>/instances')
def experiment_instances(experiment_id):
    """ Show information about all instances used in the experiment """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    
    instances = experiment.instances
    instances.sort(key=lambda i: i.name)
    
    return render('experiment_instances.html', instances=instances, experiment=experiment)

@app.route('/experiment/<int:experiment_id>/results')
def experiment_results(experiment_id):
    """ Show a table with the solver configurations and their results on the instances of the experiment """
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
                query = session.query(ExperimentResult)
                query.enable_eagerloads(True).options(joinedload(ExperimentResult.instance, ExperimentResult.solver_configuration))
                jobs = query.filter_by(experiment=experiment) \
                            .filter_by(solver_configuration=solver_config) \
                            .filter_by(instance=instance) \
                            .all()
                completed = len(filter(lambda j: j.status in JOB_FINISHED or j.status in JOB_ERROR, jobs))
                runtimes = [j.time for j in jobs]
                runtimes.sort()
                time_median = runtimes[len(runtimes) / 2]
                time_avg = sum(runtimes) / float(len(jobs))
                time_max = max(runtimes)
                time_min = min(runtimes)
                row.append({'time_avg': time_avg,
                            'time_median': time_median,
                            'time_max': time_max,
                            'time_min': time_min,
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
    
@app.route('/experiment/<int:experiment_id>/progress')
def experiment_progress(experiment_id):
    """ Show a live information table of the experiment's progress """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    return render('experiment_progress.html', experiment=experiment)

@app.route('/experiment/<int:experiment_id>/progress-ajax')
def experiment_progress_ajax(experiment_id):
    """ Returns JSON-serialized data of the experiment results. Used by the jQuery datatable as ajax data source """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    
    query = session.query(ExperimentResult).enable_eagerloads(True).options(joinedload(ExperimentResult.instance))
    query.options(joinedload(ExperimentResult.solver_configuration))
    jobs = query.filter_by(experiment=experiment).all()
    
    aaData = []
    for job in jobs:
        iname = job.instance.name
        #if len(iname) > 30: iname = iname[0:30] + '...'
        aaData.append([job.idJob, job.solver_configuration.get_name(), utils.parameter_string(job.solver_configuration),
               iname, job.run, job.time, job.seed, utils.job_status(job.status)])
    
    return json.dumps({'aaData': aaData})
    
@app.route('/experiment/<int:experiment_id>/result/<int:solver_configuration_id>/<int:instance_id>')
def solver_config_results(experiment_id, solver_configuration_id, instance_id):
    """ Displays list of results (all jobs) of a solver configuration on an instance """
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
        instance_text = instance_blob[:512] + "\n\n... [truncated " + utils.download_size(len(instance_blob) - 1024) + "]\n\n" + instance_blob[-512:]
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
    
    return render('solver_configuration_details.html', solver_config=solver_config, solver=solver, parameters=parameters,)
    
@app.route('/experiment/<int:experiment_id>/result/<int:result_id>')
def experiment_result(experiment_id, result_id):
    """ Displays information about a single result (job) """
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    result = session.query(ExperimentResult).get(result_id) or abort(404)
    
    resultFile = result.resultFile
    clientOutput = result.clientOutput
    
    if clientOutput is not None:
        if len(clientOutput) > 4*1024:
            # show only the first and last 2048 characters if the resultFile is larger than 4kB
            clientOutput_text = clientOutput[:2048] + "\n\n... [truncated " + str(int((len(clientOutput) - 4096) / 1024.0)) + " kB]\n\n" + clientOutput[-2048:]
        else:
            clientOutput_text = clientOutput
    else: clientOutput_text = "No output"
    
    if resultFile is not None:
        if len(resultFile) > 4*1024:
            # show only the first and last 2048 characters if the resultFile is larger than 4kB
            resultFile_text = resultFile[:2048] + "\n\n... [truncated " + str(int((len(resultFile) - 4096) / 1024.0)) + " kB]\n\n" + resultFile[-2048:]
        else:
            resultFile_text = resultFile
    else: resultFile_text = "No result"
    
    return render('result_details.html', experiment=experiment, result=result, solver=result.solver_configuration.solver,
                  solver_config=result.solver_configuration, instance=result.instance, resultFile_text=resultFile_text,
                  clientOutput_text=clientOutput_text)
    
@app.route('/experiment/<int:experiment_id>/result/<int:result_id>/download')
def experiment_result_download(experiment_id, result_id):
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    result = session.query(ExperimentResult).get(result_id) or abort(404)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename=result.resultFileName)
    
    return Response(response=result.resultFile, headers=headers)
    
@app.route('/experiment/<int:experiment_id>/result/<int:result_id>/download-client-output')
def experiment_result_download_client_output(experiment_id, result_id):
    experiment = session.query(Experiment).get(experiment_id) or abort(404)
    result = session.query(ExperimentResult).get(result_id) or abort(404)

    headers = Headers()
    headers.add('Content-Type', 'text/plain')
    headers.add('Content-Disposition', 'attachment', filename="client_output_"+result.resultFileName)
    
    return Response(response=result.clientOutput, headers=headers)

@app.route('/imgtest/<int:experiment_id>')
def imgtest(experiment_id):
    exp = session.query(Experiment).get(experiment_id) or abort(404)
    
    import random
    random.seed()

    # 2 random solverconfigs
    sc1 = random.choice(exp.solver_configurations)
    sc2 = random.choice(exp.solver_configurations)
    
    results1 = session.query(ExperimentResult)
    results1.enable_eagerloads(True).options(joinedload(ExperimentResult.instance, ExperimentResult.solver_configuration))
    results1 = results1.filter_by(experiment=exp, solver_configuration=sc1)
    
    results2 = session.query(ExperimentResult)
    results2.enable_eagerloads(True).options(joinedload(ExperimentResult.instance, ExperimentResult.solver_configuration))
    results2 = results2.filter_by(experiment=exp, solver_configuration=sc2)
    
    xs = []
    ys = []
    for instance in exp.instances:
        r1 = results1.filter_by(instance=instance).all()[0].time
        r2 = results2.filter_by(instance=instance).all()[0].time
        xs.append(r1)
        ys.append(r2)
    
    if request.args.has_key('pdf'):
        filename = os.path.join(config.TEMP_DIR, request.unique_id) + '.pdf'
        plots.scatter(xs,ys,sc1.solver.name,sc2.solver.name, filename, format='pdf')
        headers = Headers()
        headers.add('Content-Disposition', 'attachment', filename=sc1.solver.name + '_vs_' + sc2.solver.name + '.pdf')
        response = Response(response=open(filename, 'rb').read(), mimetype='application/pdf', headers=headers)
        os.remove(filename)
        return response
    #elif request.args.has_key('svg'):
    #    return Response(response=plots.scatter(xs,ys,sc1.solver.name,sc2.solver.name, format='svg'), mimetype='image/svg+xml')
    else:
        filename = os.path.join(config.TEMP_DIR, request.unique_id) + '.png'
        plots.scatter(xs,ys,sc1.solver.name,sc2.solver.name, filename)
        response = Response(response=open(filename, 'rb').read(), mimetype='image/png')
        os.remove(filename)
        return response
        