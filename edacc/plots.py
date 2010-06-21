# -*- coding: utf-8 -*-

import matplotlib
matplotlib.use('Agg')
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle
from cStringIO import StringIO

matplotlib.rcParams['font.weight'] = 500

def scatter(xs, ys, xlabel, ylabel, format='png'):
    if format=='png':
        fig = Figure(frameon=True, dpi=80, facecolor='#FFFFFF', edgecolor='#FFFFFF')
    else:
        fig = Figure(frameon=False, dpi=300, facecolor='#FFFFFF', edgecolor='#FFFFFF')
    canvas = FigureCanvas(fig)
    
    fig.patch.set_fill(True)
    fig.patch.set_alpha(1)
    fig.patch.set_color('#FFFFFF')    

    ax = fig.add_subplot(111, xlabel=xlabel, ylabel=ylabel)
    t = ax.set_title('CPU time ' + xlabel +' vs '+ylabel, {'size': '16'})
    t.set_position((0.5, 1.05))
    ax.scatter(xs, ys, s=100, marker='+', c='#FF0000', edgecolors='#FF0000')
    ax.set_autoscale_on(False)
    
    ax2 = fig.add_subplot(111, xlabel=xlabel, ylabel=ylabel)
    ax2.get_xaxis().set_label_position('top')
    ax2.get_yaxis().set_label_position('right')
    ax2.set_autoscale_on(False)
    
    maxtime = 30
    
    ax.set_xlim([0,maxtime])
    ax.set_ylim([0,maxtime])
    ax2.set_xlim([0,maxtime])
    ax2.set_ylim([0,maxtime])
    ax2.plot([0,maxtime],[0,maxtime], '--', c='black')

    s = StringIO()
    if format == 'pdf':
        canvas.print_pdf(s)
    elif format == 'svg':
        canvas.print_svg(s)
    elif format == 'png':
        canvas.print_png(s)
    return s.getvalue()

#from rpy2 import robjects
#from rpy2.robjects.lib import grid
#from rpy2.robjects.packages import importr
#import time
#
#def test():
#    rprint = robjects.globalenv.get("print")
#    stats = importr('stats')
#    grdevices = importr('grDevices')
#    lattice = importr('lattice')
#    
#    x = [500, 600, 700, 800, 900]
#    y = [24200, 23323, 34434, 43431, 54523]
#    
#    d = {'x': robjects.IntVector(x), 'y': robjects.IntVector(y)}
#    dataf = robjects.DataFrame(d)
#    formula = robjects.Formula('y ~ x')
#    formula.getenvironment()['x'] = dataf.rx2('x')
#    formula.getenvironment()['y'] = dataf.rx2('y')
#    
#    p = lattice.xyplot(formula, pch=3, col="black")
#    
#    grdevices.bitmap(file="/tmp/test.pdf", type="pdfwrite")
#    robjects.r('trellis.par.set("fontsize", list(text=18, points=10))')
#    rprint(p)
#    grdevices.dev_off()
