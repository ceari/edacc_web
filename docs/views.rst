View functions
==============

View functions are the request handlers of incoming HTTP requests.
URLs are mapped to python functions that handle requests and return HTTP responses.

.. automodule:: edacc.views.accounts

    .. autofunction:: register(database)
    .. autofunction:: login(database)
    .. autofunction:: logout(database)
    .. autofunction:: manage(database)
    .. autofunction:: submit_benchmark(database)
    .. autofunction:: submit_solver(database, id=None)
    .. autofunction:: list_solvers(database)
    .. autofunction:: list_benchmarks(database)
    .. autofunction:: download_solver(database, id)
    .. autofunction:: download_solver_code(database, id)

.. automodule:: edacc.views.analysis

    .. autofunction:: solver_ranking(database, experiment_id)
    .. autofunction:: cactus_plot(database, experiment_id)
    .. autofunction:: result_property_comparison(database, experiment_id)
    .. autofunction:: property_distributions(database, experiment_id)
    .. autofunction:: scatter_2solver_1property(database, experiment_id)
    .. autofunction:: scatter_1solver_instance_vs_result_property(database, experiment_id)
    .. autofunction:: scatter_1solver_result_vs_result_property(database, experiment_id)
    .. autofunction:: property_distribution(database, experiment_id)
    .. autofunction:: probabilistic_domination(database, experiment_id)
    .. autofunction:: box_plots(database, experiment_id)

.. automodule:: edacc.views.frontend

    .. autofunction:: index()
    .. autofunction:: experiments_index(database)
    .. autofunction:: categories(database)
    .. autofunction:: competition_overview(database)
    .. autofunction:: competition_schedule(database)
    .. autofunction:: competition_rules(database)
    .. autofunction:: experiment(database, experiment_id)
    .. autofunction:: experiment_solver_configurations(database, experiment_id)
    .. autofunction:: experiment_instances(database, experiment_id)
    .. autofunction:: experiment_results(database, experiment_id)
    .. autofunction:: experiment_results_by_solver(database, experiment_id)
    .. autofunction:: experiment_results_by_instance(database, experiment_id)
    .. autofunction:: experiment_progress(database, experiment_id)
    .. autofunction:: experiment_progress_ajax(database, experiment_id)
    .. autofunction:: solver_config_results(database, experiment_id, solver_configuration_id, instance_id)
    .. autofunction:: instance_details(database, instance_id)
    .. autofunction:: instance_download(database, instance_id)
    .. autofunction:: solver_configuration_details(database, experiment_id, solver_configuration_id)
    .. autofunction:: experiment_result(database, experiment_id, result_id)
    .. autofunction:: solver_output_download(database, experiment_id, result_id)
    .. autofunction:: launcher_output_download(database, experiment_id, result_id)
    .. autofunction:: watcher_output_download(database, experiment_id, result_id)
    .. autofunction:: verifier_output_download(database, experiment_id, result_id)

.. automodule:: edacc.views.plot

    .. autofunction:: scatter_2solver_1property_points(db, exp, sc1, sc2, instances, solver_property, run)
    .. autofunction:: scatter_2solver_1property(database, experiment_id)
    .. autofunction:: scatter_1solver_instance_vs_result_property_points(db, exp, solver_config, instances, instance_property, solver_property, run)
    .. autofunction:: scatter_1solver_instance_vs_result_property(database, experiment_id)
    .. autofunction:: scatter_1solver_result_vs_result_property_plot(db, exp, solver_config, instances, solver_property1, solver_property2, run)
    .. autofunction:: scatter_1solver_result_vs_result_property(database, experiment_id)
    .. autofunction:: cactus_plot(database, experiment_id)
    .. autofunction:: result_property_comparison_plot(database, experiment_id)
    .. autofunction:: property_distributions_plot(database, experiment_id)
    .. autofunction:: property_distribution(database, experiment_id)
    .. autofunction:: kerneldensity(database, experiment_id)
    .. autofunction:: box_plots(database, experiment_id)
