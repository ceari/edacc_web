Plots
=====

.. automodule:: edacc.plots

   .. autofunction:: scatter(points, xlabel, ylabel, title, max_x, max_y, filename, format='png', xscale='', yscale='', diagonal_line=False, dim=700)
   .. autofunction:: cactus(solvers, max_x, max_y, ylabel, title, filename, format='png')
   .. autofunction:: result_property_comparison(results1, results2, solver1, solver2, result_property_name, filename, format='png', dim=700)
   .. autofunction:: property_distributions(results, filename, property_name, format='png')
   .. autofunction:: box_plot(data, filename, format='png')
   .. autofunction:: property_distribution(results, filename, property_name, format='png')
   .. autofunction:: kerneldensity(data, filename, format='png')
