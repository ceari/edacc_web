# -*- coding: utf-8 -*-
"""
    edacc.plots
    -----------

    Plotting functions using rpy2 to interface with the statistics language R.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""
import os, math, random, numpy

from functools import wraps
from rpy2 import robjects
from rpy2.robjects.packages import importr
from edacc.utils import newline_split_string

grdevices = importr('grDevices') # plotting target devices
stats = importr('stats') # statistical methods
akima = importr('akima') # surface interpolation
fields = importr('fields') # image plotting

#with open(os.devnull) as devnull:
    # redirect the annoying np package import output to nirvana
#    stdout, stderr = sys.stdout, sys.stderr
#    sys.stdout = sys.stderr = devnull
np = importr('np') # non-parametric kernel smoothing methods
robjects.r("library('np')")
#    sys.stdout, sys.stderr = stdout, stderr

robjects.r.setEPS() # set some default options for postscript in EPS format

robjects.r("""plot.multi.dens <- function(s)
    {
    junk.x = NULL
junk.y = NULL
for(i in 1:length(s))
    {
    junk.x = c(junk.x, density(s[[i]])$x)
junk.y = c(junk.y, density(s[[i]])$y)
}
xr <- range(junk.x)
yr <- range(junk.y)
plot(density(s[[1]]), xlim = xr, ylim = yr, main = "")
for(i in 1:length(s))
    {
    lines(density(s[[i]]), xlim = xr, ylim = yr, col = i)
}
}""")

from threading import Lock
global_lock = Lock()

# list of colors used in the defined order for the different solvers/instance groups in plots
colors = [
    'red', 'green', 'blue', 'darkgoldenrod1', 'darkolivegreen',
    'darkorchid', 'deeppink', 'darkgreen', 'blue4'
] * 1000

def synchronized(f):
    """Thread synchronization decorator. Only allows exactly one thread
    to enter the wrapped function at any given point in time.
    """
    @wraps(f)
    def lockedfunc(*args, **kwargs):
        global_lock.acquire()
        try:
            return f(*args, **kwargs)
        finally:
            global_lock.release()
    return lockedfunc

@synchronized
def scatter(points, xlabel, ylabel, title, max_x, max_y, filename, format='png',
            xscale='', yscale='', diagonal_line=False, dim=700):
    """ Scatter plot of the points given in the list :points:
        Each element of points should be a tuple (x, y).
        Returns a list with the points in device (pixel) coordinates.
    """
    if format == 'png':
        grdevices.png(file=filename, units="px", width=800,
                      height=600, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite", height=7, width=9)
    elif format == 'eps':
        grdevices.postscript(file=filename, height=7, width=9)
    elif format == 'rscript':
        grdevices.postscript(file=os.devnull, height=7, width=9)
        file = open(filename, 'w')

    # set margins to fit in labels on the right and top
    robjects.r.par(mar = robjects.FloatVector([6, 6, 6, 17]))
    if format == 'rscript':
        file.write('par(mar=c(6,6,6,17))\n')

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

    xs = []
    ys = []
    for ig in points:
        xs += [p[0] for p in ig]
        ys += [p[1] for p in ig]

    robjects.r.options(scipen=10)
    if format == 'rscript':
        file.write('options(scipen=10)\n')

    min_x = 0
    min_y = 0

    min_x = min([x for x in xs if x > 0.0] or [0.01])
    min_y = min([y for y in ys if y > 0.0] or [0.01])

    log = ''
    if xscale == 'log':
        log += 'x'

    if yscale == 'log':
        log += 'y'

    min_v = min(min_x, min_y)

    legend_colors = []
    legend_strs = []
    legend_point_styles = []
    col = 0
    pch = 3 # 3 looks nice
    for ig in points:
        ig_xs = [p[0] for p in ig]
        ig_ys = [p[1] for p in ig]

        # plot running times
        robjects.r.plot(robjects.FloatVector(ig_xs), robjects.FloatVector(ig_ys),
                        type='p', col=colors[col % len(colors)], las = 1,
                        xlim=robjects.r.c(min_v,max_x), ylim=robjects.r.c(min_v,max_y),
                        xaxs='i', yaxs='i', log=log,
                        xlab='', ylab='', pch=pch, tck=0.015,
                        **{'cex.axis': 1.2, 'cex.main': 1.5})
        robjects.r.par(new=1)
        legend_colors.append(colors[col % len(colors)])
        legend_point_styles.append(pch)
        legend_strs.append('Group %d' % (col))
        col += 1
        pch += 1

    # plot labels and axis
    robjects.r.axis(side=4, tck=0.015, las=1,
                    **{'cex.axis': 1.2, 'cex.main': 1.5}) # plot right axis
    robjects.r.axis(side=3, tck=0.015, las=1,
                    **{'cex.axis': 1.2, 'cex.main': 1.5}) # plot top axis
    robjects.r.mtext(ylabel, side=4, line=4, cex=1.2) # right axis label
    robjects.r.mtext(xlabel, side=3, padj=0, line=3, cex=1.2) # top axis label
    robjects.r.mtext(title, padj=-1.7, side=3, line=3, cex=1.7) # plot title

    robjects.r.par(xpd=True)
    robjects.r.legend("right", inset=-0.35,
                      legend=robjects.StrVector(legend_strs),
                      col=robjects.StrVector(legend_colors),
                      pch=robjects.IntVector(legend_point_styles))

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

    pts = []
    for ig in points:
        xs = [p[0] for p in ig]
        ys = [p[1] for p in ig]
        pts.append(zip(robjects.r.grconvertX(robjects.FloatVector(xs), "user", "device"),
              robjects.r.grconvertY(robjects.FloatVector(ys), "user", "device")))
    grdevices.dev_off()
    return pts


@synchronized
def cactus(solvers, instance_groups_count, colored_instance_groups, max_x, max_y, min_y,
           log_property, flip_axes, ylabel, title, filename, format='png'):
    """ Cactus plot of the passed solvers configurations. `solvers` has to be
        a list of dictionaries with the keys `xs`, `ys` and `name`. For each
        y in `ys` the corresponding x in `xs` should be the number of
        instances solved within y seconds.
    """
    if format == 'png':
        grdevices.png(file=filename, units="px", width=800,
                      height=600, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite", height=7, width=9)
    elif format == 'eps':
        grdevices.postscript(file=filename, height=7, width=9)
    elif format == 'rscript':
        grdevices.postscript(file=os.devnull, height=7, width=9)
        file = open(filename, 'w')

    robjects.r.par(mar = robjects.FloatVector([5, 4, 4, 15]))
    if format == 'rscript':
        file.write('par(mar=c(5,4,4,15))\n')

    log = ''
    if log_property:
        log = 'y'
        if flip_axes: log = 'x'

    min_x = 0.0
    if flip_axes:
        max_x, max_y = max_y, max_x
        min_x, min_y = min_y, min_x

    robjects.r.options(scipen=10)
    # plot without data to create the frame
    robjects.r.plot(robjects.FloatVector([]), robjects.FloatVector([]),
                    type='p', col='red', las = 1, log=log,
                    xlim=robjects.r.c(min_x,max_x), ylim=robjects.r.c(min_y,max_y),
                    xaxs='i', yaxs='i',
                    xlab='',ylab='', **{'cex.main': 1.5})
    robjects.r.par(new=1)
    if format == 'rscript':
        file.write('options(scipen=10)\n')
        file.write(('plot(c(), c(), type="p", col="red", las=1, log="%s",' +
                    'xlim=c(%f,%f), ylim=c(%f,%f), xaxs="i", yaxs="i",' +
                    'xlab="", ylab="", cex.main=1.5)\n') % (log, min_x, max_x, min_y, max_y))
        file.write('par(new=1)\n\n\n\n')

    legend_strs = []
    legend_colors = []
    legend_point_styles = []

    if colored_instance_groups:
        point_styles = {}
        color_styles = dict((i, colors[i % len(colors)]) for i in xrange(instance_groups_count))
        point_style = 0
        for s in solvers:
            if not s['name'] in point_styles:
                point_styles[s['name']] = point_style
                point_style += 1
    else:
        point_styles = dict((i, i) for i in xrange(instance_groups_count))
        color_styles = {}
        i = 0
        for s in solvers:
            if not s['name'] in color_styles:
                color_styles[s['name']] = colors[i % len(colors)]
                i += 1

    for s in solvers:
        xs = s['xs']
        ys = s['ys']

        if flip_axes:
            xs, ys = ys, xs

        # plot points
        if colored_instance_groups:
            col = color_styles[s['instance_group']]
            pch = point_styles[s['name']]
        else:
            col = color_styles[s['name']]
            pch = point_styles[s['instance_group']]

        robjects.r.plot(robjects.FloatVector(xs), robjects.FloatVector(ys),
                        type='p', col=col, pch=pch, log=log,
                        xlim=robjects.r.c(min_x,max_x), ylim=robjects.r.c(min_y,max_y),
                        xaxs='i', yaxs='i',
                        xaxt='n', yaxt='n',
                        axes=False, xlab='',ylab='', **{'cex.main': 1.5})
        robjects.r.par(new=1)
        if format == 'rscript':
            file.write(('plot(c(%s), c(%s), type="p", col="%s", pch=%d, log="%s", ' +
                        'xlim=c(%f,%f), ylim=c(%f,%f), xaxs="i", yaxs="i", xaxt="n", yaxt="n", axes=0,' +
                        'xlab="", ylab="", cex.main=1.5)\n')
                        % (','.join(map(str, xs)), ','.join(map(str, ys)), col, pch, log, min_x, max_x, min_y, max_y))
            file.write('par(new=1)\n')

        # plot lines
        robjects.r.plot(robjects.FloatVector(xs), robjects.FloatVector(ys),
                        type='l', col=col,lty=1, log=log,
                        xlim=robjects.r.c(min_x,max_x), ylim=robjects.r.c(min_y,max_y),
                        xaxs='i', yaxs='i',
                        xaxt='n', yaxt='n',
                        axes=False, xlab='',ylab='', **{'cex.main': 1.5})
        robjects.r.par(new=1)
        if format == 'rscript':
            file.write(('plot(c(%s), c(%s), type="l", col="%s", lty=1, log="%s",' +
                        'xlim=c(%f,%f), ylim=c(%f,%f), xaxs="i", yaxs="i", xaxt="n", yaxt="n", axes=0,' +
                        'xlab="", ylab="", cex.main=1.5)\n')
                        % (','.join(map(str, xs)), ','.join(map(str, ys)), col, log, min_x, max_x, min_y, max_y))
            file.write('par(new=1)\n\n\n')


        legend_strs.append('%s (G%d)' % (newline_split_string(s['name'], 30), s['instance_group']))
        legend_colors.append(col)
        legend_point_styles.append(pch)

    # plot labels and axes
    if flip_axes:
        robjects.r.mtext(ylabel, side=1,
                         line=3, cex=1.2) # bottom axis label
        robjects.r.mtext('number of solved instances', side=2, padj=0,
                         line=3, cex=1.2) # left axis label
    else:
        robjects.r.mtext('number of solved instances', side=1,
                         line=3, cex=1.2) # bottom axis label
        robjects.r.mtext(ylabel, side=2, padj=0,
                         line=3, cex=1.2) # left axis label
    robjects.r.mtext(title,
                     padj=1, side=3, line=3, cex=1.7) # plot title
    robjects.r.par(xpd=True)

    if format == 'rscript':
        if flip_axes:
            file.write('mtext("%s", side=1, line=3, cex=1.2)\n'% (ylabel))
            file.write('mtext("number of solved instances", side=2, padj=0, line=3, cex=1.2)\n')
        else:
            file.write('mtext("number of solved instances", side=1, line=3, cex=1.2)\n')
            file.write('mtext("%s", side=2, padj=0, line=3, cex=1.2)\n' % (ylabel))
        file.write('mtext("%s", padj=1, side=3, line=3, cex=1.7)\n' % (title))
        file.write('par(xpd=1)\n')

    # plot legend
    robjects.r.legend("right", inset=-0.40,
                      legend=robjects.StrVector(legend_strs),
                      col=robjects.StrVector(legend_colors),
                      pch=robjects.IntVector(legend_point_styles), lty=1, cex=0.75, **{'y.intersp': 1.1})
    if format == 'rscript':
        file.write('legend("right", inset=-0.40, legend=c(%s), col=c(%s), y.intersp=1.4, pch=c(%s), lty=1)\n'
                    % (','.join(map(lambda s: '"' + s + '"', legend_strs)).replace('\n',''),
                      ','.join(map(lambda s: '"' + s + '"', legend_colors)),
                      ','.join(map(str, legend_point_styles))))
        file.close()

    grdevices.dev_off()


@synchronized
def result_property_comparison(results1, results2, solver1, solver2, result_property_name, log_property, dim=700,
                               filename='', format='png'):
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
    elif format == 'rscript':
        grdevices.postscript(file=os.devnull, height=7, width=9)
        file = open(filename, 'w')

    if len(results1) == len(results2) == 0:
        robjects.r.frame()
        robjects.r.mtext('not enough data', padj=5, side=3, line=3, cex=1.7)
        grdevices.dev_off()

        if format == "rscript":
            file.write("frame()\nmtext('not enough data', padj=5, side=3, cex=1.7)\n")
        return

    max_x = max([max(results1), max(results2)])

    if log_property:
        log = 'x'
        min_x = min([min(results1), min(results2)])
    else:
        log = ''
        min_x = 0

    # plot without data to create the frame
    robjects.r.plot(robjects.FloatVector([]), robjects.FloatVector([]),
                    type='p', col='red', las = 1, log=log,
                    xlim=robjects.r.c(min_x, max_x), ylim=robjects.r.c(-0.05, 1.05),
                    xaxs='i', yaxs='i',
                    xlab='',ylab='', **{'cex.main': 1.5})
    robjects.r.par(new=1)

    # plot the two distributions
    robjects.r.plot(robjects.r.ecdf(robjects.FloatVector(results1)),
                    main='', xaxt='n', yaxt='n', log=log,
                    xlab='', ylab='', xaxs='i', yaxs='i', las=1, col='red',
                    xlim=robjects.r.c(min_x,max_x), ylim=robjects.r.c(-0.05, 1.05))
    robjects.r.par(new=1)
    robjects.r.plot(robjects.r.ecdf(robjects.FloatVector(results2)),
                    main='', xaxt='n', yaxt='n', log=log,
                    xlab='', ylab='', xaxs='i', yaxs='i', las=1, col='blue',
                    xlim=robjects.r.c(min_x,max_x), ylim=robjects.r.c(-0.05, 1.05))

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

    if format == "rscript":
        file.write("plot(c(), c(), type='p', col='red', las=1, log='%s', xlim=c(%f, %f), ylim=c(-0.05, 1.05), xaxs='i', yaxs='i', xlab='', ylab='', cex.main=1.5)\n" \
                    % (log, min_x, max_x))
        file.write("par(new=T)\n")
        file.write("plot(ecdf(c(%s), main='', xaxt='n', yaxt='n', log='%s', " \
                    "xlab='', ylab='', xaxs='i', yaxs='i', las=1, col='red', " \
                    "xlim=c(%f,%f), ylim=c(-0.05, 1.05))\n" \
                    % (','.join(map(str, results1)), log, min_x, max_x))
        file.write("par(new=T)\n")
        file.write("plot(ecdf(c(%s), main='', xaxt='n', yaxt='n', log='%s', "\
                   "xlab='', ylab='', xaxs='i', yaxs='i', las=1, col='red', "\
                   "xlim=c(%f,%f), ylim=c(-0.05, 1.05))\n"\
                    % (','.join(map(str, results2)), log, min_x, max_x))
        file.write("mtext('%s', side=1, line=3, cex=1.2)\n" % (result_property_name,))
        file.write("mtext('P(X <= x)', side=2, padj=0, line=3, cex=1.2)\n")
        file.write("mtext('Result property distribution comparison', padj=1, side=3, line=3, cex=1.7)\n")

    grdevices.dev_off()


@synchronized
def property_distributions(results, property_name, log_property, filename, format='png'):
    """Runtime distribution plots for multiple result vectors.
    results is expected to be a list of tuples (sc, data)
    where data is the result vector of the solver configuration sc.
    """
    if format == 'png':
        grdevices.png(file=filename, units="px", width=800,
                      height=600, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite", height=7, width=9)
    elif format == 'eps':
        grdevices.postscript(file=filename, height=7, width=9)
    elif format == 'rscript':
        grdevices.postscript(file=os.devnull, height=7, width=9)
        file = open(filename, 'w')

    max_x = max([max(r[1] or [0]) for r in results] or [0])

    if log_property:
        log = 'x'
        min_x = min([min(r[1] or [0.1]) for r in results] or [0.1])
    else:
        log = ''
        min_x = 0
        
    robjects.r.par(mar = robjects.FloatVector([5, 4, 4, 15]))
    # plot without data to create the frame
    robjects.r.plot(robjects.FloatVector([]), robjects.FloatVector([]),
                    type='p', col='red', las = 1, log=log,
                    xlim=robjects.r.c(min_x, max_x), ylim=robjects.r.c(-0.05, 1.05),
                    xaxs='i', yaxs='i',
                    xlab='',ylab='', **{'cex.main': 1.5})
    robjects.r.par(new=1)

    if format == "rscript":
        file.write("par(mar=c(5,4,4,15))\n")
        file.write("plot(c(), c(), type='p', col='red', las=1, log='%s', xlim=c(%f, %f), ylim=c(-0.05, 1.05), xaxs='i', yaxs='i', xlab='', ylab='', cex.main=1.5)\n" \
                    % (log, min_x, max_x))
        file.write("par(new=T)\n")

    # list of colors used in the defined order for the different solvers
    colors = [
        'red', 'green', 'blue', 'darkgoldenrod1', 'darkolivegreen',
        'darkorchid', 'deeppink', 'darkgreen', 'blue4'
    ] * 10

    # plot the distributions
    point_style = 0
    for res in results:
        if len(res[1]) > 0:
            robjects.r.plot(robjects.r.ecdf(robjects.FloatVector(res[1])),
                            main='', col=colors[point_style % len(colors)], pch=point_style, log=log,
                            xlab='', ylab='', xaxs='i', yaxs='i', las=1,
                            xaxt='n', yaxt='n',
                            xlim=robjects.r.c(min_x,max_x), ylim=robjects.r.c(-0.05, 1.05))
            robjects.r.par(new=1)

            if format == "rscript":
                file.write("ecdf(c(%s), main='', col='%s', pch=%d, log='%s', xlab='', ylab='', xaxs='i', yaxs='i', las=1, xaxt='n', yaxt='n', xlim=c(%f, %f), ylim=c(-0.05, 1.05))\n" \
                        % (','.join(map(str, res[1])), colors[point_style % len(colors)], point_style, log, min_x, max_x))
                file.write("par(new=T)\n")

            point_style += 1



    # plot labels and axes
    robjects.r.mtext(property_name, side=1,
                     line=3, cex=1.2) # bottom axis label
    robjects.r.mtext('P(X <= x)', side=2, padj=0,
                     line=3, cex=1.2) # left axis label
    robjects.r.mtext(property_name + ' distributions',
                     padj=1, side=3, line=3, cex=1.7) # plot title
    robjects.r.par(xpd=True)

    # plot legend
    robjects.r.legend("right", inset=-0.4,
                      legend=robjects.StrVector([newline_split_string(str(r[0]), 23) for r in results]),
                      col=robjects.StrVector(colors[:len(results)]),
                      pch=robjects.IntVector(range(len(results))), lty=1, **{'y.intersp': 1.4})

    if format == "rscript":
        file.write("mtext('%s', side=1, line=3, cex=1.2)\n" % (property_name,))
        file.write("mtext('P(X <= x), side=2, padj=0, line=3, cex=1.2)\n")
        file.write("mtext('%s distributions', padj=1, side=3, line=3, cex=1.7)\n" % (property_name, ))
        file.write("par(xpd=T)\n")
        file.write("legend('right', inset=-0.4, legend=c(%s), col=c(%s), pch=c(%s), lty=1, y.intersp=1.4)\n" \
                    % (','.join([newline_split_string(str(r[0]), 23) for r in results]),
                       ','.join(colors[:len(results)]), ','.join(map(str, range(len(results)))),
            ))

    grdevices.dev_off()


@synchronized
def box_plot(data, property_label, filename, format='png'):
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
    elif format == 'rscript':
        grdevices.postscript(file=os.devnull, height=7, width=9)
        file = open(filename, 'w')

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

        if format == "rscript":
            file.write("boxplot(c(%s), main='', names=c(%s), horizontal=T)\n" \
                    % (','.join(map(str, [data[k] for k in data])), ','.join(map(str, [key for key in data]))))
            file.write("mtext('%s', side=1, line=3, cex=1.2)\n" % (property_label,))
    else:
        robjects.r.frame()
        robjects.r.mtext('not enough data', padj=5, side=3, line=3, cex=1.7)
        if format == "rscirpt":
            file.write("frame()\nmtext('not enough data', padj=5, side=3, line=3, cex=1.7)\n")

    grdevices.dev_off()


@synchronized
def property_distribution(results_by_sc, property_name, log_property, restart_strategy, filename, format='png'):
    """Plot of a property distributions.

    :param results: result vector
    """
    if format == 'png':
        grdevices.png(file=filename, units="px", width=800,
                      height=600, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite")
    elif format == 'eps':
        grdevices.postscript(file=filename)
    elif format == 'rscript':
        grdevices.postscript(file=os.devnull, height=7, width=9)
        file = open(filename, 'w')

    max_x = 0
    for sc in results_by_sc:
        max_x = max(max(results_by_sc[sc]), max_x)

    if log_property:
        log = 'x'
        min_x = max_x
        for sc in results_by_sc:
            min_x = min(min(results_by_sc[sc]), min_x)
    else:
        log = ''
        min_x = 0

    robjects.r.par(mar = robjects.FloatVector([5, 4, 4, 15]))

    # plot without data to create the frame
    robjects.r.plot(robjects.FloatVector([]), robjects.FloatVector([]),
                    type='p', col='red', las = 1, log=log,
                    xlim=robjects.r.c(min_x, max_x), ylim=robjects.r.c(-0.05, 1.05),
                    xaxs='i', yaxs='i',
                    xlab='',ylab='', **{'cex.main': 1.5})
    robjects.r.par(new=1)

    if format == "rscript":
        file.write("plot(c(), c(), type='p', col='red', las=1, log='%s', xlim=c(%f, %f), ylim=c(-0.05, 1.05), xaxs='i', yaxs='i', xlab='', ylab='', cex.main=1.5)\n" \
                % (log, min_x, max_x))
        file.write("par(new=T)\n")

    # list of colors used in the defined order for the different solvers
    colors = [
                 'red', 'green', 'blue', 'darkgoldenrod1', 'darkolivegreen',
                 'darkorchid', 'deeppink', 'darkgreen', 'blue4'
             ] * 10
    col = 0
    point_style = 0

    for sc in results_by_sc:
        if restart_strategy and len(results_by_sc) == 1:
            mean = numpy.mean(results_by_sc[sc] or [0])
            best_i, best_ti, best_mean = 0, 0, None
            for i, t_i in zip(range(1, len(results_by_sc[sc])+1), sorted(results_by_sc[sc])):
                mp = t_i * len(results_by_sc[sc]) / float(i)
                if best_mean is None or mp - mean < best_mean - mean:
                    best_mean = mp
                    best_i = i
                    best_ti = t_i

            robjects.r.abline(v=best_ti, col='red')
            robjects.r.abline(v=best_mean, col='blue')
            robjects.r.abline(v=mean, col='green')
            robjects.r.par(new=1)

            if format == "rscript":
                file.write("abline(v=%f, col='red')\n" % (best_ti, ))
                file.write("par(new=T)\n")

        robjects.r.plot(robjects.r.ecdf(robjects.FloatVector(results_by_sc[sc] or [0])),
                        main='', xaxt='n', yaxt='n', log=log, col=colors[col % len(colors)], pch=point_style,
                        xlab='', ylab='', xaxs='i', yaxs='i', las=1,
                        xlim=robjects.r.c(min_x,max_x), ylim=robjects.r.c(-0.05, 1.05))



        robjects.r.par(new=1)

        col += 1
        point_style += 1

    if format == "rscript":
        file.write("plot(ecdf(c(%s)), main='', xaxt='n', yaxt='n', log='%s', xlab='', ylab='', xaxs='i', yaxs='i', las=1, xlim=c(%f, %f), ylim=c(-0.05, 1.05))\n"\
        % (','.join(map(str, results or [0])), log, min_x, max_x))
        file.write("mtext('%s', side=1, line=3, cex=1.2)\n" % (property_name, ))
        file.write("mtext('P(X <= x)', side=2, padj=0, line=3, cex=1.2)\n")
        file.write("mtext('%s', padj=1, side=3, line=3, cex=1.7)\n" \
                    % (property_name + ' distribution' + (u', t_rs = ' + str(round(best_ti, 4)) if restart_strategy and len(results_by_sc) == 1 else ''), ))

    # plot labels and axes
    robjects.r.mtext(property_name, side=1,
        line=3, cex=1.2) # bottom axis label
    robjects.r.mtext('P(X <= x)', side=2, padj=0,
        line=3, cex=1.2) # left axis label
    robjects.r.mtext(property_name + ' distribution' + (u', t_rs = ' + str(round(best_ti, 4)) if restart_strategy and len(results_by_sc) == 1 else ''),
        padj=1, side=3, line=3, cex=1.7) # plot title

    robjects.r.par(xpd=True)
    # plot legend
    robjects.r.legend("right", inset=-0.4,
        legend=robjects.StrVector([newline_split_string(str(sc), 23) for sc in results_by_sc]),
        col=robjects.StrVector(colors[:len(results_by_sc)]),
        pch=robjects.IntVector(range(len(results_by_sc))), lty=1, **{'y.intersp': 1.4})

    if not results_by_sc:
        robjects.r.mtext('not enough data', padj=5, side=3, line=3, cex=1.7)

        if format == "rscript":
            file.write("mtext('not enough data', padj=5, side=3, line=3, cex=1.7)\n")

    grdevices.dev_off()


@synchronized
def kerneldensity(results_by_sc, property_name, log_property, restart_strategy, filename, format='png'):
    """Non-parametric kernel density estimation plots of result vectors."""
    if format == 'png':
        grdevices.png(file=filename, units="px", width=800,
                      height=600, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite")
    elif format == 'eps':
        grdevices.postscript(file=filename)
    elif format == 'rscript':
        grdevices.postscript(file=os.devnull, height=7, width=9)
        file = open(filename, 'w')

    max_x = 0
    for sc in results_by_sc:
        max_x = max(max(results_by_sc[sc]), max_x)

    if log_property:
        log = 'x'
        min_x = max_x
        for sc in results_by_sc:
            min_x = min(min(results_by_sc[sc]), min_x)
    else:
        log = ''
        min_x = 0

    robjects.r.par(mar = robjects.FloatVector([5, 4, 4, 15]))

    col = 0
    point_style = 0

    robjects.r("plot.multi.dens")((robjects.r("list"))(*map(robjects.FloatVector, results_by_sc.values())))

    # plot labels and axes
    if restart_strategy and len(results_by_sc) == 1:
        sc = results_by_sc.keys()[0]
        mean = numpy.mean(results_by_sc[sc] or [0])
        best_i, best_ti, best_mean = 0, 0, None
        for i, t_i in zip(range(1, len(results_by_sc[sc])+1), sorted(results_by_sc[sc])):
            mp = t_i * len(results_by_sc[sc]) / float(i)
            if best_mean is None or mp - mean < best_mean - mean:
                best_mean = mp
                best_i = i
                best_ti = t_i
        robjects.r.par(new=1)
        robjects.r.abline(v=best_ti, col='red')
        robjects.r.abline(v=best_mean, col='blue')
        robjects.r.abline(v=mean, col='green')

        if format == "rscript":
            file.write("par(new=T)\n")
            file.write("abline(v=%f, col='red')\n" % (best_ti,))
            file.write("abline(v=%f, col='blue')\n" % (best_mean,))
            file.write("abline(v=%f, col='green')\n" % (mean,))

    # plot labels and axes

    robjects.r.mtext('Kernel density estimation' + (u', t_rs = ' + str(round(best_ti, 4)) if restart_strategy and len(results_by_sc) == 1 else ''),
                     padj=1, side=3, line=3, cex=1.7) # plot title

    if format == "rscript":
        file.write("mtext('Kernel density estimation%s', padj=1, side=3, line=3, cex=1.7)\n" \
                    % ((u', t_rs = ' + str(round(best_ti, 4)) if restart_strategy and len(results_by_sc) == 1 else ''),))

    robjects.r.par(xpd=True)
    # plot legend
    robjects.r.legend("right", inset=-0.4,
        legend=robjects.StrVector([newline_split_string(str(sc), 23) for sc in results_by_sc]),
        col=robjects.StrVector(range(1, len(results_by_sc)+1)), lty=1, **{'y.intersp': 1.4})

    if not results_by_sc:
        robjects.r.frame()
        robjects.r.mtext('not enough data', padj=5, side=3, line=3, cex=1.7)

        if format == "rscript":
            file.write("frame()\n")
            file.write("mtext('not enough data', padj=5, side=3, line=3, cex=1.7)\n")

    grdevices.dev_off()

@synchronized
def barplot(values, filename, format='png'):
    if format == 'png':
        grdevices.png(file=filename, units="px", width=400,
                      height=400, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite")
    elif format == 'eps':
        grdevices.postscript(file=filename)
    elif format == 'rscript':
        grdevices.postscript(file=os.devnull, height=7, width=9)
        file = open(filename, 'w')

    robjects.r.par(mar = robjects.FloatVector([2, 2, 2, 2]))
    robjects.r.barplot(robjects.IntVector(values),
                       names=robjects.StrVector(['>', '=?', '<']))

    if format == "rscript":
        file.write("par(mar=c(2,2,2,2))\n")
        file.write("barplot(c(%s), names=c('>', '=?', '<'))\n" % (','.join(map(str, values)),))

    grdevices.dev_off()
    
@synchronized
def runtime_matrix_plot(flattened_rtmatrix, num_sorted_solver_configs, num_sorted_instances, measure, filename, format='png'):
    if format == 'png':
        grdevices.png(file=filename, units="px", width=840,
                      height=700, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite")
    elif format == 'eps':
        grdevices.postscript(file=filename)
    elif format == 'rscript':
        grdevices.postscript(file=os.devnull, height=7, width=9)
        file = open(filename, 'w')
    
    if None in flattened_rtmatrix:
        robjects.r.frame()
        robjects.r.mtext('Missing results for some instances\nor configs', padj=5, side=3, line=3, cex=1.7)
        grdevices.dev_off()

        if format == "rscript":
            file.write("frame()\n")
            file.write("mtext('Missing results for some instances or configs', padj=5, side=3, line=3, cex=1.7)\n")
        return

    m = robjects.r.matrix(robjects.FloatVector(flattened_rtmatrix), nrow=num_sorted_solver_configs)
    m = robjects.r.t(robjects.r.log10(m))

    if format == "rscript":
        file.write("m = matrix(c(%s), nrow=%d)\n" % (','.join(map(str, flattened_rtmatrix)), num_sorted_solver_configs))
        file.write("m = t(log10(m))\n")
    
    min_val = math.log10(min(flattened_rtmatrix))
    max_val = math.log10(max(flattened_rtmatrix))

    robjects.r.layout(robjects.r.matrix(robjects.IntVector([1,2]), nrow=1, ncol=2),
                      widths=robjects.IntVector([4,1]), heights=robjects.IntVector([1,1]))
    
    color_ramp = robjects.r.rgb(robjects.r.seq(0,1,length=256),
                                robjects.r.seq(0,1,length=256),
                                robjects.r.seq(0,1,length=256))
    color_levels = robjects.r.seq(min_val, max_val, length=robjects.r.length(color_ramp))

    if format == "rscript":
        file.write("layout(matrix(c(1,2), nrow=1, ncol=2), widths=c(4,1), heights=c(1,1))\n")
        file.write("color_ramp = rgb(seq(0,1,length=256), seq(0,1,length=256), seq(0,1,length=256))\n")
        file.write("color_levels = seq(%f, %f, length=length(color_ramp))\n" % (min_val, max_val))

    
    robjects.r.par(mar = robjects.FloatVector([5,5,2.5,3]))

    robjects.r.image(robjects.IntVector(range(1, num_sorted_instances+1)), robjects.IntVector(range(1, num_sorted_solver_configs+1)),
                     m, col=color_ramp, xlab="", ylab="", ylim=robjects.IntVector([num_sorted_solver_configs, 1]),
                     zlim=robjects.FloatVector([min_val, max_val]))

    if format == "rscript":
        file.write("par(mar=c(5,5,2.5,3))\n")
        file.write("image(c(%s), c(%s), m, col=color_ramp, xlab='', ylab='', ylim=c(%d, 1), zlim=c(%f, %f))\n" \
                    % (','.join(map(str, range(1, num_sorted_instances+1))), ','.join(map(str, range(1, num_sorted_solver_configs+1))),
                        num_sorted_solver_configs, min_val, max_val))
    
    robjects.r.mtext("instance (sorted by %s)" % (measure,), side=1, line=3, cex=1.2) # bottom axis label
    robjects.r.mtext("config (sorted by %s)" % (measure,), side=2, line=3, cex=1.2) # left axis label
    robjects.r.title('Runtime Matrix Plot', cex=1.4)

    if format == "rscript":
        file.write("mtext('instance (sorted by %s)', side=1, line=3, cex=1.2)\n" % (measure,))
        file.write("mtext('config (sorted by %s)', side=2, line=3, cex=1.2)\n" % (measure,))
        file.write("title('Runtime Matrix Plot', cex=1.4)\n")
    
    robjects.r.par(mar = robjects.FloatVector([5,2.5,2.5,3]))
    robjects.r.image(1, color_levels, robjects.r.matrix(data=color_levels, ncol=robjects.r.length(color_levels), nrow=1),
                     col=color_ramp, xlab="", ylab="", xaxt="n")
    robjects.r.layout(1)

    if format == "rscript":
        file.write("par(mar=c(5,2.5,2.5,3))\n")
        file.write("image(1, color_levels, matrix(data=color_levels, ncol=length(color_levels), nrow=1), col=color_ramp, xlab='', ylab='', xaxt='n')\n")
        file.write("layout(1)\n")

    grdevices.dev_off()

@synchronized
def parameter_plot_1d(data, parameter_name, measure, runtime_cap, log_x, log_y, filename, format='png'):
    if format == 'png':
        grdevices.png(file=filename, units="px", width=1200,
            height=600, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite", height=7, width=9)
    elif format == 'eps':
        grdevices.postscript(file=filename, height=7, width=9)
    elif format == 'rscript':
        grdevices.postscript(file=os.devnull, height=7, width=9)
        file = open(filename, 'w')

    try:
        # set margins to fit in labels on the right and top
        robjects.r.par(mar = robjects.FloatVector([5, 4, 4, 15]))
        if format == 'rscript':
            file.write('par(mar=c(5,4,4,15))\n')

        robjects.r.options(scipen=10)
        if format == 'rscript':
            file.write('options(scipen=10)\n')

        xs = [p[0] for p in data]
        ys = [min(p[1], runtime_cap) for p in data]

        col = 0
        pch = 3 # 3 looks nice

        log = ''
        if log_x: log += 'x'
        if log_y: log += 'y'

        # plot running times
        robjects.r.plot(robjects.FloatVector(xs), robjects.FloatVector(ys), log=log,
            type='p', col=colors[col % len(colors)], las = 1, main=measure + ' runtime against ' + parameter_name,
            xlim=robjects.FloatVector([min(xs), max(xs)]), ylim=robjects.FloatVector([0.0 if not log_y else 0.000000001, max(ys)]),
            xaxs='i', yaxs='i', cex=1.2,
            xlab=parameter_name, ylab=measure, pch=pch, tck=0.015,
            **{'cex.axis': 1.2, 'cex.main': 1.5})

        if format == "rscript":
            file.write("plot(c(%s), c(%s), log='%s', type='p', col='%s', las=1, main='%s', xlim=c(%f, %f), ylim=c("+str(0.0 if not log_y else 0.000000001) + ", %f), xaxs='i', yaxs='i', cex=1.2, xlab='%s', ylab='%s', pch=%d, tck=0.015, cex.axis=1.2, cex.main=1.5)\n"
                % (','.join(map(str,xs)), ','.join(map(str, ys)), log, colors[col % len(colors)], measure + " runtime against " + parameter_name, min(xs), max(xs), max(ys), parameter_name, measure, pch))
            file.close()
    except Exception as ex:
        raise ex
    finally:
        grdevices.dev_off()

@synchronized
def parameter_plot_2d(data, parameter1_name, parameter2_name, measure, surface_interpolation, runtime_cap, log_x, log_y, log_cost, filename, format='png'):
    if format == 'png':
        grdevices.png(file=filename, units="px", width=1000,
            height=800, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite", height=7, width=9)
    elif format == 'eps':
        grdevices.postscript(file=filename, height=7, width=9)
    elif format == 'rscript':
        grdevices.postscript(file=os.devnull, height=7, width=9)
        file = open(filename, 'w')

        file.write("library(akima)\nlibrary(fields)\n")

    try:
        # set margins to fit in labels on the right and top
        robjects.r.par(mar = robjects.FloatVector([5, 4, 4, 5]))
        if format == 'rscript':
            file.write('par(mar=c(5,4,4,5))\n')

        robjects.r.options(scipen=10)
        if format == 'rscript':
            file.write('options(scipen=10)\n')

        xs = [p[0] for p in data]
        ys = [p[1] for p in data]
        costs = [min(p[2], runtime_cap) for p in data]

        log = ''
        if log_x: log += 'x'
        if log_y: log += 'y'
        if log_cost:
            costs = map(lambda x: 0.0 if x <= 0.000000001 else math.log10(x), costs)

        min_cost_point = data[costs.index(min(costs))]

        #if log_x: min_cost_point = 0.0 if min_cost_point[0] <= 0.000000001 else math.log10(min_cost_point[0]), min_cost_point[1], min_cost_point[2]
        #if log_y: min_cost_point = min_cost_point[0], 0.0 if min_cost_point[1] <= 0.000000001 else math.log10(min_cost_point[1]), min_cost_point[2]
        if log_cost: min_cost_point = min_cost_point[0], min_cost_point[1], 0.0 if min_cost_point[2] <= 0.000000001 else math.log10(min_cost_point[2])

        if not surface_interpolation:
            min_cost = min(costs)
            max_cost = max(costs) + 0.0000000001
            costs = map(lambda c: 1 + int( (c - min_cost) * (200.0/(max_cost-min_cost))), costs)
            cols = robjects.r("heat.colors(256)[c(" + ','.join(map(str, costs)) + ")]")
            title = "Minimum: (%s, %s) with cost: %s" % (round(min_cost_point[0], 4), round(min_cost_point[1], 4), round(min_cost_point[2], 4))

            if format == 'rscript':
                file.write("cols = heat.colors(256)[c(" + ','.join(map(str, costs)) + ")]\n")
                file.write("plot(c(%s), c(%s), log='%s', type='p', col=cols, pch=19, xlab='%s', ylab='%s', xaxs='i', yaxs='i', cex=1.5, xlim=c(%f, %f), ylim=c(%f, %f), main='%s')\n"\
                % (','.join(map(str, xs)), ','.join(map(str, ys)), log, parameter1_name, parameter2_name, min(xs), max(xs), min(ys), max(ys), title))
                file.write("par(new=1)\n")
                file.write("points(c(%f), c(%f), type='p', pch=3, col='red', cex=3)\n" % (min_cost_point[0], min_cost_point[1]))
                file.close()

            robjects.r.plot(robjects.FloatVector(xs), robjects.FloatVector(ys), log=log, type='p', col=cols, pch=19,
                xlab=parameter1_name, ylab=parameter2_name, xaxs='i', yaxs='i', cex=1.5,
                xlim=robjects.FloatVector([min(xs), max(xs)]), ylim=robjects.FloatVector([min(ys), max(ys)]),
                main=title)
            robjects.r.par(new=1)
            robjects.r.points(robjects.FloatVector([min_cost_point[0]]), robjects.FloatVector([min_cost_point[1]]),  type='p', pch=3, col='red', cex=3)
        else:
            xs = map(lambda x: 0.0 if x <= 0.000000001 else math.log10(x), xs)
            ys = map(lambda x: 0.0 if x <= 0.000000001 else math.log10(x), ys)

            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)

            surf = akima.interp(robjects.FloatVector(xs), robjects.FloatVector(ys), robjects.FloatVector(costs),
                            xo=robjects.r.seq(min_x, max_x, (max_x - min_x) / 1000.0), yo=robjects.r.seq(min_y, max_y, (max_y - min_y) / 800.0),
                            duplicate="mean")
            title = "Minimum: (%s, %s) with cost: %s" % (round(min_cost_point[0], 4), round(min_cost_point[1], 4), round(min_cost_point[2], 4))

            if log_cost: measure = 'log10(' + measure + ')'

            if format == 'rscript':
                file.write("surf = interp(c(%s), c(%s), c(%s), xo=seq(%f, %f, %f), yo=seq(%f, %f, %f), duplicate='mean')\n"\
                % (','.join(map(str, xs)), ','.join(map(str, ys)), ','.join(map(str, costs)), min_x, max_x, (max_x - min_x) / 1000.0, min_y, max_y, (max_y - min_y) / 800.0))
                file.write("image.plot(surf, nlevel=256, xlab='%s', ylab='%s', xaxs='i', yaxs='i', xlim=c(%f, %f), ylim=c(%f, %f), main='%s', legend.lab='%s', legend.mar=4.5)\n"\
                % (parameter1_name, parameter2_name, min_x, max_x, min_y, max_y, title, measure))
                file.write("par(new=1)\n")
                file.write("points(c(%f), c(%f), type='p', pch=3, col='red', cex=2)\n" % (min_cost_point[0], min_cost_point[1]))
                file.close()

            robjects.r("image.plot")(surf, nlevel=256,
                xlab=parameter1_name, ylab=parameter2_name, xaxs='i', yaxs='i',
                xlim=robjects.FloatVector([min_x, max_x]), ylim=robjects.FloatVector([min_y, max_y]),
                main=title,
                **{'legend.lab': measure, 'legend.mar': 4.5})
            robjects.r.par(new=1)
            robjects.r.points(robjects.FloatVector([min_cost_point[0]]), robjects.FloatVector([min_cost_point[1]]), type='p', pch=3, col='red', cex=2)
    except Exception as ex:
        raise ex
    finally:
        grdevices.dev_off()

@synchronized
def make_error_plot(text, filename, format='png'):
    if format == 'png':
        grdevices.png(file=filename, units="px", width=800,
            height=400, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite", height=7, width=9)
    elif format == 'eps':
        grdevices.postscript(file=filename, height=7, width=9)
    elif format == 'rscript':
        grdevices.postscript(file=os.devnull, height=7, width=9)
        file = open(filename, 'w')
    try:
        robjects.r.plot(0, xaxt='n', yaxt='n', bty='n', pch='', ylab='', xlab='', main=text)
        if format == "rscript":
            file.write('error.')
            file.close()
    finally:
        grdevices.dev_off()

@synchronized
def perc_solved_alone(perc_solved_by_solver, filename, format='png'):
    if format == 'png':
        grdevices.png(file=filename, units="px", width=800,
            height=max(200, 50*len(perc_solved_by_solver)), type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite", height=9, width=7)
    elif format == 'eps':
        grdevices.postscript(file=filename, height=7, width=9)
    elif format == 'rscript':
        grdevices.postscript(file=os.devnull, height=7, width=9)
        file = open(filename, 'w')

    try:
        values = []
        names = []
        for k, v in perc_solved_by_solver.iteritems():
            values.append(v)
            names.append(k.name)
        data = zip(names, values)
        data.sort(key=lambda x: x[1])
        robjects.r.par(mar = robjects.FloatVector([5, 20, 4, 5]))
        robjects.r.barplot(robjects.FloatVector([t[1] for t in data]), horiz=True, names=robjects.StrVector([t[0] for t in data]), las=1, xlim=robjects.FloatVector([0.0, 1.0]))
    except Exception as ex:
        raise ex
    finally:
        grdevices.dev_off()