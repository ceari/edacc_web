# -*- coding: utf-8 -*-
"""
    edacc.plots
    -----------

    Plotting functions using rpy2 to interface with the statistics language R.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""
from functools import wraps
from rpy2 import robjects
from rpy2.robjects.packages import importr

grdevices = importr('grDevices') # plotting target devices
np = importr('np') # non-parametric kernel smoothing methods
stats = importr('stats') # statistical methods

robjects.r.setEPS() # set some default options for postscript in EPS format

from threading import Lock
global_lock = Lock()

def synchronized(f):
    """Thread synchronization decorator. Only allows exactly one thread
    to enter the wrapped function at any given point in time.
    """
    @wraps(f)
    def lockedfunc(*args, **kwargs):
        try:
            global_lock.acquire()
            try:
                return f(*args, **kwargs)
            except Exception, e:
                raise
        finally:
            global_lock.release()
    return lockedfunc

@synchronized
def scatter(points, xlabel, ylabel, title, max_x, max_y, filename, format='png', xscale='', yscale='', diagonal_line=False, dim=700):
    """ Scatter plot of the points given in the list :points:
        Each element of points should be a tuple (x, y).
        Returns a list with the points in device (pixel) coordinates.
    """
    if format == 'png':
        grdevices.png(file=filename, units="px", width=dim,
                      height=dim, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite")
    elif format == 'eps':
        grdevices.postscript(file=filename)
    elif format == 'rscript':
        file = open(filename, 'w')

    # set margins to fit in labels on the right and top
    robjects.r.par(mar=robjects.FloatVector([4,4,6,6]))
    if format == 'rscript':
        file.write('par(mar=c(4,4,6,6))\n')

    if ((xscale == 'log' and yscale == 'log') or (xscale == '' and yscale == '')) and diagonal_line:
        # plot dashed line from (0,0) to (max_x,max_y)
        robjects.r.plot(robjects.FloatVector([0,max_x]),
                        robjects.FloatVector([0,max_y]),
                        type='l', col='black', lty=2,
                        xlim=robjects.r.c(0,max_x), ylim=robjects.r.c(0,max_y),
                        xaxs='i', yaxs='i',
                        xaxt='n', yaxt='n',
                        xlab='', ylab='')
        # to be able to plot in the same graph again
        robjects.r.par(new=1)

        if format == 'rscript':
            file.write(('plot(c(0, %f), c(0, %f), type="l", col="black", lty=2,' + \
                       'xlim=c(0, %f), ylim=c(0, %f), xaxs="i", yaxs="i", xaxt="n",' + \
                       'yaxt="n", xlab="", ylab="")\n') % (max_x, max_y, max_x, max_y))
            file.write('par(new=1)\n')


    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    robjects.r.options(scipen=10)
    if format == 'rscript':
        file.write('options(scipen=10)\n')

    min_x = 0
    min_y = 0

    log = ''
    if xscale == 'log':
        log += 'x'
        min_x = min([x for x in xs if x > 0.0] or [0.01])
        min_y = min([y for y in ys if y > 0.0] or [0.01])

    if yscale == 'log':
        log += 'y'
        min_x = min([x for x in xs if x > 0.0] or [0.01])
        min_y = min([y for y in ys if y > 0.0] or [0.01])

    min_v = min(min_x, min_y)

    # plot running times
    robjects.r.plot(robjects.FloatVector(xs), robjects.FloatVector(ys),
                    type='p', col='red', las = 1,
                    xlim=robjects.r.c(min_v,max_x), ylim=robjects.r.c(min_v,max_y),
                    xaxs='i', yaxs='i', log=log,
                    xlab='', ylab='', pch=3, tck=0.015,
                    **{'cex.axis': 1.2, 'cex.main': 1.5})

    # plot labels and axis
    robjects.r.axis(side=4, tck=0.015, las=1,
                    **{'cex.axis': 1.2, 'cex.main': 1.5}) # plot right axis
    robjects.r.axis(side=3, tck=0.015, las=1,
                    **{'cex.axis': 1.2, 'cex.main': 1.5}) # plot top axis
    robjects.r.mtext(ylabel, side=4, line=3, cex=1.2) # right axis label
    robjects.r.mtext(xlabel, side=3, padj=0, line=3, cex=1.2) # top axis label
    robjects.r.mtext(title, padj=-1.7, side=3, line=3, cex=1.7) # plot title
    if format == 'rscript':
        file.write(('plot(c(%s), c(%s), type="p", col="red", las=1,' + \
                   'xlim=c(%f, %f), ylim=c(%f, %f),' + \
                   'xaxs="i", yaxs="i", log="%s",' + \
                   'xlab="", ylab="", pch=3, tck=0.015,' + \
                   'cex.axis=1.2, cex.main=1.5)\n') % (','.join(map(str, xs)), ','.join(map(str, ys)),
                                                     min_v, max_x, min_v, max_y, log))
        file.write('axis(side=4, tck=0.015, las=1, cex.axis=1.2, cex.main=1.5)\n')
        file.write('axis(side=3, tck=0.015, las=1, cex.axis=1.2, cex.main=1.5)\n')
        file.write('mtext("%s", side=4, line=3, cex=1.2)\n' % (ylabel,))
        file.write('mtext("%s", side=3, padj=0, line=3, cex=1.2)\n' % (xlabel,))
        file.write('mtext("%s", padj=-1.7, side=3, line=3, cex=1.7)\n' % (title,))
        file.close()

    pts = zip(robjects.r.grconvertX(robjects.FloatVector(xs), "user", "device"),
              robjects.r.grconvertY(robjects.FloatVector(ys), "user", "device"))
    grdevices.dev_off()
    return pts


@synchronized
def cactus(solvers, max_x, max_y, ylabel, title, filename, format='png'):
    """ Cactus plot of the passed solvers configurations. `solvers` has to be
        a list of dictionaries with the keys `xs`, `ys` and `name`. For each
        y in `ys` the corresponding x in `xs` should be the number of
        instances solved within y seconds.
    """
    if format == 'png':
        grdevices.png(file=filename, units="px", width=600,
                      height=600, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite")
    elif format == 'eps':
        grdevices.postscript(file=filename)

    # list of colors used in the defined order for the different solvers
    colors = [
        'red', 'green', 'blue', 'darkgoldenrod1', 'darkolivegreen',
        'darkorchid', 'deeppink', 'darkgreen', 'blue4'
    ]

    # plot without data to create the frame
    robjects.r.plot(robjects.FloatVector([]), robjects.FloatVector([]),
                    type='p', col='red', las = 1,
                    xlim=robjects.r.c(0,max_x), ylim=robjects.r.c(0,max_y),
                    xaxs='i', yaxs='i',
                    xlab='',ylab='', **{'cex.main': 1.5})
    robjects.r.par(new=1)

    point_style = 0
    for s in solvers:
        xs = s['xs']
        ys = s['ys']

        # plot points
        robjects.r.plot(robjects.FloatVector(xs), robjects.FloatVector(ys),
                        type='p', col=colors[point_style], pch=point_style,
                        xlim=robjects.r.c(0,max_x), ylim=robjects.r.c(0,max_y),
                        xaxs='i', yaxs='i',
                        xaxt='n', yaxt='n',
                        axes=False, xlab='',ylab='', **{'cex.main': 1.5})
        robjects.r.par(new=1)

        # plot lines
        robjects.r.plot(robjects.FloatVector(xs), robjects.FloatVector(ys),
                        type='l', col=colors[point_style],lty=1,
                        xlim=robjects.r.c(0,max_x), ylim=robjects.r.c(0,max_y),
                        xaxs='i', yaxs='i',
                        xaxt='n', yaxt='n',
                        axes=False, xlab='',ylab='', **{'cex.main': 1.5})
        robjects.r.par(new=1)

        point_style += 1

    # plot labels and axes
    robjects.r.mtext('number of solved instances', side=1,
                     line=3, cex=1.2) # bottom axis label
    robjects.r.mtext(ylabel, side=2, padj=0,
                     line=3, cex=1.2) # left axis label
    robjects.r.mtext(title,
                     padj=1, side=3, line=3, cex=1.7) # plot title

    # plot legend
    robjects.r.legend("topleft", inset=0.01,
                      legend=robjects.StrVector([s['name'] for s in solvers]),
                      col=robjects.StrVector(colors[:len(solvers)]),
                      pch=robjects.IntVector(range(len(solvers))), lty=1)

    grdevices.dev_off()


@synchronized
def result_property_comparison(results1, results2, solver1, solver2, result_property_name, filename, format='png', dim=700):
    """Result property distribution comparison.
    Plots an cumulative empirical distribution function for the result vectors
    results1 and results2 in the same diagram with 2 different colors.
    """
    if format == 'png':
        grdevices.png(file=filename, units="px", width=dim,
                      height=dim, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite")
    elif format == 'eps':
        grdevices.postscript(file=filename)

    if len(results1) == len(results2) == 0:
        robjects.r.frame()
        robjects.r.mtext('not enough data', padj=5, side=3, line=3, cex=1.7)
        grdevices.dev_off()
        return

    max_x = max([max(results1), max(results2)])

    # plot without data to create the frame
    robjects.r.plot(robjects.FloatVector([]), robjects.FloatVector([]),
                    type='p', col='red', las = 1,
                    xlim=robjects.r.c(0, max_x), ylim=robjects.r.c(-0.05, 1.05),
                    xaxs='i', yaxs='i',
                    xlab='',ylab='', **{'cex.main': 1.5})
    robjects.r.par(new=1)

    # plot the two distributions
    robjects.r.plot(robjects.r.ecdf(robjects.FloatVector(results1)),
                    main='', xaxt='n', yaxt='n',
                    xlab='', ylab='', xaxs='i', yaxs='i', las=1, col='red',
                    xlim=robjects.r.c(0,max_x), ylim=robjects.r.c(-0.05, 1.05))
    robjects.r.par(new=1)
    robjects.r.plot(robjects.r.ecdf(robjects.FloatVector(results2)),
                    main='', xaxt='n', yaxt='n',
                    xlab='', ylab='', xaxs='i', yaxs='i', las=1, col='blue',
                    xlim=robjects.r.c(0,max_x), ylim=robjects.r.c(-0.05, 1.05))

    # plot labels and axes
    robjects.r.mtext(result_property_name, side=1,
                     line=3, cex=1.2) # bottom axis label
    robjects.r.mtext('P(X <= x)', side=2, padj=0,
                     line=3, cex=1.2) # left axis label
    robjects.r.mtext('Result property distribution comparison',
                     padj=1, side=3, line=3, cex=1.7) # plot title

    # plot legend
    robjects.r.legend("bottomright", inset=.01,
                      legend=robjects.StrVector([solver1, solver2]),
                      col=robjects.StrVector(['red', 'blue']),
                      pch=robjects.IntVector([0,1]), lty=1)

    grdevices.dev_off()


@synchronized
def property_distributions(results, filename, property_name, format='png'):
    """Runtime distribution plots for multiple result vectors.
    results is expected to be a list of tuples (sc, data)
    where data is the result vector of the solver configuration sc.
    """
    if format == 'png':
        grdevices.png(file=filename, units="px", width=600,
                      height=600, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite")
    elif format == 'eps':
        grdevices.postscript(file=filename)

    max_x = max([max(r[1] or [0]) for r in results] or [0])

    # plot without data to create the frame
    robjects.r.plot(robjects.FloatVector([]), robjects.FloatVector([]),
                    type='p', col='red', las = 1,
                    xlim=robjects.r.c(0.0, max_x), ylim=robjects.r.c(-0.05, 1.05),
                    xaxs='i', yaxs='i',
                    xlab='',ylab='', **{'cex.main': 1.5})
    robjects.r.par(new=1)

    # list of colors used in the defined order for the different solvers
    colors = [
        'red', 'green', 'blue', 'darkgoldenrod1', 'darkolivegreen',
        'darkorchid', 'deeppink', 'darkgreen', 'blue4'
    ]

    # plot the distributions
    point_style = 0
    for res in results:
        if len(res[1]) > 0:
            robjects.r.plot(robjects.r.ecdf(robjects.FloatVector(res[1])),
                            main='', col=colors[point_style], pch=point_style,
                            xlab='', ylab='', xaxs='i', yaxs='i', las=1,
                            xaxt='n', yaxt='n',
                            xlim=robjects.r.c(0.0,max_x), ylim=robjects.r.c(-0.05, 1.05))
            robjects.r.par(new=1)
            point_style += 1

    # plot labels and axes
    robjects.r.mtext(property_name, side=1,
                     line=3, cex=1.2) # bottom axis label
    robjects.r.mtext('P(X <= x)', side=2, padj=0,
                     line=3, cex=1.2) # left axis label
    robjects.r.mtext(property_name + ' distributions',
                     padj=1, side=3, line=3, cex=1.7) # plot title

    # plot legend
    robjects.r.legend("bottomright", inset=.01,
                      legend=robjects.StrVector([str(r[0]) for r in results]),
                      col=robjects.StrVector(colors[:len(results)]),
                      pch=robjects.IntVector(range(len(results))), lty=1)

    grdevices.dev_off()


@synchronized
def box_plot(data, filename, property_label, format='png'):
    """Box plot for multiple result vectors.

    :param data: data dictionary with one entry for each result vector, the
                 key is used as label for each box.
    """
    if format == 'png':
        grdevices.png(file=filename, units="px", width=600,
                      height=600, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite")
    elif format == 'eps':
        grdevices.postscript(file=filename)

    any_data = False
    for key in data:
        if len(data[key]) > 0:
            any_data = True
        data[key] = robjects.FloatVector(data[key])

    if any_data:
        robjects.r.boxplot(robjects.Vector([data[k] for k in data]), main="",
                           names=robjects.StrVector([key for key in data]), horizontal=True)
        robjects.r.mtext(property_label, side=1,
                         line=3, cex=1.2) # bottom axis label
    else:
        robjects.r.frame()
        robjects.r.mtext('not enough data', padj=5, side=3, line=3, cex=1.7)


    grdevices.dev_off()


@synchronized
def property_distribution(results, filename, property_name, format='png'):
    """Plot of a single property distribution.

    :param results: result vector
    """
    if format == 'png':
        grdevices.png(file=filename, units="px", width=600,
                      height=600, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite")
    elif format == 'eps':
        grdevices.postscript(file=filename)

    max_x = max(results or [0])

    # plot without data to create the frame
    robjects.r.plot(robjects.FloatVector([]), robjects.FloatVector([]),
                    type='p', col='red', las = 1,
                    xlim=robjects.r.c(0, max_x), ylim=robjects.r.c(-0.05, 1.05),
                    xaxs='i', yaxs='i',
                    xlab='',ylab='', **{'cex.main': 1.5})
    robjects.r.par(new=1)

    if len(results) > 0:
        robjects.r.plot(robjects.r.ecdf(robjects.FloatVector(results or [0])),
                        main='', xaxt='n', yaxt='n',
                        xlab='', ylab='', xaxs='i', yaxs='i', las=1,
                        xlim=robjects.r.c(0,max_x), ylim=robjects.r.c(-0.05, 1.05))

        # plot labels and axes
        robjects.r.mtext(property_name, side=1,
                         line=3, cex=1.2) # bottom axis label
        robjects.r.mtext('P(X <= x)', side=2, padj=0,
                         line=3, cex=1.2) # left axis label
        robjects.r.mtext(property_name + ' distribution',
                         padj=1, side=3, line=3, cex=1.7) # plot title
    else:
        robjects.r.mtext('not enough data', padj=5, side=3, line=3, cex=1.7)

    grdevices.dev_off()


@synchronized
def kerneldensity(data, filename, format='png'):
    """Non-parametric kernel density estimation plot of a result vector.

    :param data: result vector
    """
    if format == 'png':
        grdevices.png(file=filename, units="px", width=600,
                      height=600, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite")
    elif format == 'eps':
        grdevices.postscript(file=filename)

    if len(data) > 0:
        # add some pseudo value to data because R crashes when the data is constant
        # and takes python down with it ...
        robjects.r.plot(np.npudens(robjects.FloatVector(data + [max(data or [0]) + 0.00001])),
                        main='', xaxt='n', yaxt='n',
                        xlab='', ylab='', xaxs='i', yaxs='i', las=1)
        # plot labels and axes
        robjects.r.mtext('Nonparametric kernel density estimation',
                         padj=1, side=3, line=3, cex=1.7) # plot title
    else:
        robjects.r.frame()
        robjects.r.mtext('not enough data', padj=5, side=3, line=3, cex=1.7)

    grdevices.dev_off()