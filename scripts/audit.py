import os, sys
try:
    import pyflakes.scripts.pyflakes as flakes
except ImportError:
    print "Missing dependency: PyFlakes"
    sys.exit(-1)

print 

warnings = 0
for dir, subdirs, files in os.walk(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../edacc')):
    for filename in files:
        if filename.endswith('.py'):
            warnings += flakes.checkPath(os.path.join(dir, filename))

if warnings > 0:
    print "%d warnings" % warnings
else:
    print "No problems found"
