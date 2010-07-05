# -*- coding: utf-8 -*-

from rpy2 import robjects
from rpy2.robjects.packages import importr
grdevices = importr('grDevices')
#cairo = importr('Cairo')
#cairo.CairoFonts(regular="Bitstream Vera Sans:style=Regular",bold="Bitstream Vera Sans:style=Bold",italic="Bitstream Vera Sans:style=Italic",bolditalic="Bitstream Vera Sans:style=Bold Italic,BoldItalic",symbol="Symbol")

def scatter(xs, ys, xlabel, ylabel, title, timeout, filename, format='png'):
    """ Scatter plot of the points given in the lists `xs` and `ys` """
    if format == 'png':
        #cairo.CairoPNG(file=filename, units="px", width=600, height=600, bg="white", pointsize=14)
        grdevices.png(file=filename, units="px", width=600, height=600, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite")

    robjects.r.par(mar=robjects.FloatVector([3,3,6,6])) # set margins to fit in labels on the right and top
    
    # plot dashed line from (0,0) to (timeout,timeout)
    robjects.r.plot(robjects.FloatVector([0,timeout]), robjects.FloatVector([0,timeout]), type='l', col='black', lty=2,
                    xlim=robjects.r.c(0,timeout), ylim=robjects.r.c(0,timeout), xaxs='i', yaxs='i',
                    xaxt='n', yaxt='n', xlab='', ylab='')
    robjects.r.par(new=1) # to be able to plot in the same graph again
    
    # plot running times
    robjects.r.plot(robjects.FloatVector(xs), robjects.FloatVector(ys), type='p', col='red', las = 1,
                    xlim=robjects.r.c(0,timeout), ylim=robjects.r.c(0,timeout), xaxs='i', yaxs='i',
                    xlab='', ylab='', pch=3, tck=0.015, **{'cex.axis': 1.2, 'cex.main': 1.5})
    
    # plot labels and axis
    robjects.r.axis(side=4, tck=0.015, las=1, **{'cex.axis': 1.2, 'cex.main': 1.5}) # plot right axis
    robjects.r.axis(side=3, tck=0.015, las=1, **{'cex.axis': 1.2, 'cex.main': 1.5}) # plot top axis
    robjects.r.mtext(ylabel, side=4, line=3, cex=1.2) # right axis label
    robjects.r.mtext(xlabel, side=3, padj=0, line=3, cex=1.2) # top axis label
    robjects.r.mtext(title, padj=-1.7, side=3, line=3, cex=1.7) # plot title
    
    grdevices.dev_off()

def cactus(solvers, max_x, max_y, filename, format='png'):
    """ Cactus plot of the passed solvers configurations. `solvers` has to be a list of dictionaries
        with the keys `xs`, `ys` and `name`. For each y in `ys` the corresponding x in `xs` should be
        the number of instances solved within y seconds """
    if format == 'png':
        #cairo.CairoPNG(file=filename, units="px", width=600, height=600, bg="white", pointsize=14)
        grdevices.png(file=filename, units="px", width=600, height=600, type="cairo")
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite")
    
    # list of colors used in the defined order for the different solvers
    colors = ['red', 'green', 'blue', 'darkgoldenrod1', 'darkolivegreen', 'darkorchid', 'deeppink', 'darkgreen', 'blue4']
    
    # plot without data to create the frame
    robjects.r.plot(robjects.FloatVector([]), robjects.FloatVector([]), type='p', col='red', las = 1,
                    xlim=robjects.r.c(0,max_x), ylim=robjects.r.c(0,max_y), xaxs='i', yaxs='i',
                    xlab='',ylab='', **{'cex.main': 1.5})
    robjects.r.par(new=1)

    point_style = 0
    for s in solvers:
        xs = s['xs']
        ys = s['ys']
        
        # plot points
        robjects.r.plot(robjects.FloatVector(xs), robjects.FloatVector(ys), type='p', col=colors[point_style], pch=point_style,
                        xlim=robjects.r.c(0,max_x), ylim=robjects.r.c(0,max_y), xaxs='i', yaxs='i',
                        axes=False, xlab='',ylab='', **{'cex.main': 1.5})
        robjects.r.par(new=1)
        
        # plot lines
        robjects.r.plot(robjects.FloatVector(xs), robjects.FloatVector(ys), type='l', col=colors[point_style],lty=1,
                        xlim=robjects.r.c(0,max_x), ylim=robjects.r.c(0,max_y), xaxs='i', yaxs='i',
                        axes=False, xlab='',ylab='', **{'cex.main': 1.5})
        robjects.r.par(new=1)
        
        point_style += 1
        
    # plot labels and axis
    robjects.r.mtext('number of solved instances', side=1, line=3, cex=1.2) # left axis label
    robjects.r.mtext('CPU Time (s)', side=2, padj=0, line=3, cex=1.2) # bottom axis label
    robjects.r.mtext('Number of instances solved within a given amount of time', padj=1, side=3, line=3, cex=1.7) # plot title
    
    # plot legend
    robjects.r.legend(1, max_y - (max_y * 0.03), legend=robjects.StrVector([s['name'] for s in solvers]), col=robjects.StrVector(colors[:len(solvers)]), pch=robjects.IntVector(range(len(solvers))),
                      lty=1)

    grdevices.dev_off()
