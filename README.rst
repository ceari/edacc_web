EDACC Web Frontend
==================

Experiment Design and Administration for Computer Clusters for SAT Solvers.
See http://sourceforge.net/projects/edacc/ for the EDACC project.

An instance of this web frontend is running at http://edacc2.informatik.uni-ulm.de

Description
-----------

This project accompanies the EDACC Java Swing application and provides a simple way to publish
experiment information and results on the web that can be accessed using a web browser.

It features the same graphical analysis options as the Java application using the language R
to draw various graphs and lets users see the solver configurations and instances used in an experiment
aswell as the individual jobs that were run.

Additionally, you can set up an EDACC database to run a solver competition, where users can register
and submit solvers using the web frontend.

Implementation
--------------

This web application is written in Python and due to using Werkzeug and Flask (web frameworks) it is
WSGI-compatible, which means it can be deployed on any web server supporting Python and WSGI.
(e.g. Apache (using mod_wsgi), lighttpd, nginx, Tornado, just to name a few)

Dependencies
------------

- Python 2.6.5 or 2.7.1 http://www.python.org
- SQLAlchemy 0.6.5 (SQL Toolkit and Object Relational Mapper)
- mysql-python 1.2.3c1 (Python MySQL adapter)
- Flask 0.6 (Micro Webframework)
- Flask-WTF 0.3.3 (Flask extension for WTForms)
- Flask-Actions 0.5.2 (Flask extension)
- Werkzeug 0.6.2 (Webframework, Flask dependency)
- Jinja2 2.5 (Template Engine)
- PyLZMA 0.4.2 (Python LZMA SDK bindings)
- rpy2 2.1.4 (Python R interface)
- R 2.11 (language for statistical computing and graphics)
- R package 'np' (available via CRAN)
- python-memcached v1.45 + memcached 1.4.5 (optional, enable/disable in config.py)

Installation
------------

The required Python libraries can most likely be installed using the
package management tool of your favorite Linux distribution.
However, they are also available in the Python Package Index "PyPi" http://pypi.python.org/pypi
and can be installed using easy_install or pip. (http://pypi.python.org/pypi/setuptools  http://pypi.python.org/pypi/pip)

It is recommended not to install these libraries system-wide but in a virtual
python environment to prevent any conflicts and ensure that the correct versions are
available for the web frontend.

To get rpy2 working the GNU linker (ld) has to be able to find libR.so. Add the folder containing
libR.so (usually /usr/lib/R/lib) to the ld config: Create a file called R.conf containing the
path in the folder /etc/ld.so.conf.d/ and run ldconfig without parameters as root to update.
Additionally, you have to install the R package 'np' which provides non-parametric statistical
methods. This package can be installed by running "install.packages('np')" within the R interpreter.

For further information see http://flask.pocoo.org/docs/installation/ and http://flask.pocoo.org/docs/deploying/

Quick Installation Guide
------------------------

To illustrate an installation here's what you would have to do on a linux system (assuming Python and pip are installed,
using e.g. the distribution's package manager) to get the development server running.

1. Install R and configure ld as described above
2. Install virtualenv: "pip install virtualenv"
3. Create a virtual python environment in the subdirectory env of the current directory: "virtualenv env"
4. Activate the virtual environment: "source env/bin/activate" (This will set up some environment variables so
   Python packages are installed to the virtual environment)
5. Install the dependencies: "pip install mysql-python sqlalchemy flask rpy2 flask-wtf flask-actions mysql-python pylzma numpy" (some of them need to be compiled and require the appropriate libraries. On Windows and some linux distributions you can find binaries)
6. Change to the folder containing the file server.py that comes with the web frontend
7. Adjust the configuration in ./edacc/config.py
8. Run "python server.py" which will start a web server on port 5000 listening on all IPs of the machine (Make sure
   the virtual environment is activated)
