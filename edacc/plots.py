# -*- coding: utf-8 -*-

from rpy2 import robjects
from rpy2.robjects.packages import importr
from edacc.utils import synchronized
grdevices = importr('grDevices')
#cairo = importr('Cairo')
#cairo.CairoFonts(regular="Bitstream Vera Sans:style=Regular",bold="Bitstream Vera Sans:style=Bold",italic="Bitstream Vera Sans:style=Italic",bolditalic="Bitstream Vera Sans:style=Bold Italic,BoldItalic",symbol="Symbol")

@synchronized()
def scatter(xs, ys, xlabel, ylabel, timeout, filename, format='png'):
    if format == 'png':
        #cairo.CairoPNG(file=filename, units="px", width=600, height=600, bg="white", pointsize=14)
        grdevices.bitmap(file=filename, units="px", width=600, height=600)
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
    robjects.r.mtext(xlabel + ' vs. ' + ylabel, padj=-1.7, side=3, line=3, cex=1.7) # plot title
    
    grdevices.dev_off()

@synchronized()
def cactus(solvers, max_x, max_y, filename, format='png'):
    if format == 'png':
        #cairo.CairoPNG(file=filename, units="px", width=600, height=600, bg="white", pointsize=14)
        grdevices.bitmap(file=filename, units="px", width=600, height=600)
    elif format == 'pdf':
        grdevices.bitmap(file=filename, type="pdfwrite")
        
    robjects.r.plot(robjects.FloatVector([]), robjects.FloatVector([]), type='p', col='red', las = 1,
                    xlim=robjects.r.c(0,max_x), ylim=robjects.r.c(0,max_y), xaxs='i', yaxs='i',
                    xlab='',ylab='', **{'cex.main': 1.5})
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'black']
    robjects.r.par(new=1)
    point_style = 0
    for s in solvers:
        xs = s['xs']
        ys = s['ys']
        
        robjects.r.plot(robjects.FloatVector(xs), robjects.FloatVector(ys), type='p', col=colors[point_style], pch=point_style,
                        xlim=robjects.r.c(0,max_x), ylim=robjects.r.c(0,max_y), xaxs='i', yaxs='i',
                        axes=False, xlab='',ylab='', **{'cex.main': 1.5})
        robjects.r.par(new=1)
        robjects.r.plot(robjects.FloatVector(xs), robjects.FloatVector(ys), type='l', col=colors[point_style],lty=1,
                        xlim=robjects.r.c(0,max_x), ylim=robjects.r.c(0,max_y), xaxs='i', yaxs='i',
                        axes=False, xlab='',ylab='', **{'cex.main': 1.5})
        robjects.r.par(new=1)
        
        point_style += 1
        
    # plot labels and axis
    robjects.r.mtext('number of solved instances', side=1, line=3, cex=1.2) # right axis label
    robjects.r.mtext('CPU Time (s)', side=2, padj=0, line=3, cex=1.2) # top axis label
    robjects.r.mtext('Number of solved instances within a given amount of time', padj=1, side=3, line=3, cex=1.7) # plot title

    grdevices.dev_off()