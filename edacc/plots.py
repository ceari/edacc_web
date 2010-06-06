# -*- coding: utf-8 -*-

import matplotlib
matplotlib.use('Agg')
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from cStringIO import StringIO

def draw():
    fig = Figure(frameon=False)
    canvas = FigureCanvas(fig)
    
    
    ax = fig.add_subplot(111, xlabel='x' ,label="Y over X")
    ax.set_title('Hello World', {'size': '28'})
    ax.scatter([1,2,3,4,5], [5,2,7,2,7], s=100, marker='+')
    
    ax2 = fig.add_subplot(111, xlabel='x' ,label="Y over X")
    ax2.scatter([1,2,3,4,5], [2,4,3,1,5], s=100, marker='^', c='black')

    ax2 = fig.add_subplot(111, xlabel='x' ,label="Y over X")
    ax2.plot([0,10],[0,10], '--', c='black')

    s = StringIO()
    canvas.print_png(s)
    return s.getvalue()
