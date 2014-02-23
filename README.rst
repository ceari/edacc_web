EDACC Web Frontend
==================

Experiment Design and Administration for Computer Clusters for SAT Solvers.
See http://edacc.github.io/ for the EDACC project.

An instance of this web frontend is running at http://edacc2.informatik.uni-ulm.de

Description
-----------

This project provides a simple way to publish experiment information and results on
the web that can be accessed using a web browser.

It features graphical and statistical analysis options, using the language R
to draw various graphs and lets users see the solver configurations and instances used in an experiment
as well as the individual jobs that were run.

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
- Flask 0.8 (Micro Webframework)
- Flask-WTF 0.3.3 (Flask extension for WTForms)
- Flask-Actions 0.5.2 (Flask extension)
- Flask-Mail (Flask extension)
- Flask-KVSession (Flask extension)
- Werkzeug 0.8 (Webframework, Flask dependency)
- Jinja2 2.5 (Template Engine)
- PyLZMA 0.4.2 (Python LZMA SDK bindings)
- rpy2 2.1.4 (Python R interface)
- pbkdf2 (Python PBKDF2 hash function implementation)
- PIL 1.1.7
- numpy 1.5.1
- pygame 1.9
- lxml 2.3
- scikits.learn (borgexplorer plugin dependency)
- scipy (borgexplorer plugin dependency)
- R 2.11 (language for statistical computing and graphics)
- R packages 'np', 'ellipse', 'fields', 'surv2sample', 'akima', 'RColorBrewer' (available via CRAN)
- python-memcached v1.45 + memcached 1.4.5 (optional, enable/disable in config.py)

Development Installation Guide
------------------------

To illustrate an installation here's what you would have to do on a linux system (assuming Python, python-pip and python-virtualenv are installed,
using e.g. the distribution's package manager) to get the development server running. The development server is not suited
for anything but personal use.

To get rpy2 working the GNU linker (ld) has to be able to find libR.so. Add the folder containing
libR.so (usually /usr/lib/R/lib) to the ld config: Create a file called R.conf containing the
path in the folder /etc/ld.so.conf.d/ and run ldconfig without parameters as root to update.
Additionally, you have to install the R package 'np' which provides non-parametric statistical
methods. This package can be installed by running "install.packages('np')" within the R interpreter.

1. Install R and configure ld as described above
2. Create a virtual python environment in some directory outside(!) the extracted edacc_web-1.0/ directory::

   > virtualenv env

3. Activate the virtual environment: (This will set up some environment variables in your bash session so
   Python packages are installed to the virtual environment)::

   > source env/bin/activate

4. Install the web frontend python package into the virtual environment. If there are errors read 5) and run setup.py again after::

   > python setup.py install

5. Install the dependencies that can't be installed by the setup procedure. Some of them need to be compiled and require the
   appropriate libraries. On most linux distributions you can find binaries in the package manager.
   This applies mostly to numpy, mysql-python, rpy2 and pygame::

   > Ubuntu: apt-get install python-numpy python-pygame python-mysqldb python-rpy2
   > Arch Linux: pacman -S python-pygame python2-numpy mysql-python

6. Adjust the configuration in "env/lib/python<PYTHONVERSION>/site-packages/edacc_web-1.0-py<PYTHONVERSION>.egg/edacc/local_config.py"

7. Copy the server.py file from the edacc_web-1.0 directory to some directory and delete the edacc_web-1.0 directory.

8. Run "python server.py" which will start a web server on port 5000 listening on all IPs of the machine (Make sure
   the virtual environment is activated, see 3.)

Summary:
pip install mysql-python pil pylzma numpy scipy flask flask-cache flask-wtf flask-actions flask-mail flask-kvsession rpy2 lxml scikits.learn sqlalchemy
   
Installation
------------

The preferred installation method is behind a full scale web server like Apache instead of the builtin development server.

To get rpy2 working the GNU linker (ld) has to be able to find libR.so. Add the folder containing
libR.so (usually /usr/lib/R/lib) to the ld config: Create a file called R.conf containing the
path in the folder /etc/ld.so.conf.d/ and run ldconfig without parameters as root to update.
Additionally, you have to install the R package 'np' which provides non-parametric statistical
methods. This package can be installed by running "install.packages('np')" within the R interpreter (as root).

The following installation example outlines the step that have to be taken to install the web frontend on Ubuntu 10.04
running on the Apache 2.2.14 web server. For performance reasons (e.g. query latency) the web frontend should run on the
same machine that the EDACC database runs on::

    - Install Apache and the WSGI module:
    > apt-get install apache2 libapache2-mod-wsgi

    - Copy the web frontend files to /srv/edacc_web/, create an empty error.log file and change their ownership to the Apache user: 
    > touch /srv/edacc_web/error.log
    > chown www-data:www-data -R /srv/edacc_web

    - Create an Apache virtual host file at /etc/apache2/sites-available/edacc_web, containing:
    <VirtualHost *:80>
    ServerAdmin email@email.com
    ServerName foo.server.com

    LimitRequestLine 51200000

    WSGIDaemonProcess edacc processes=1 threads=15
    WSGIScriptAlias / /srv/edacc_web/edacc_web.wsgi

    Alias /static/ /srv/edacc_web/edacc/static/

    <Directory /srv/edacc_web>
        WSGIProcessGroup edacc
        WSGIApplicationGroup %{GLOBAL}
        Order deny,allow
        Allow from all
    </Directory>

    <Directory /srv/edacc_web/edacc/static>
        Order allow,deny
        Allow from all
    </Directory>
    </VirtualHost>

    - Install dependencies and create a virtual environment for Python libraries:
    > apt-get install python-pip python-virtualenv python-scipy python-pygame python-imaging python-numpy python-lxml
    > virtualenv /srv/edacc_web/env
    > apt-get build-dep python-mysqldb
    > apt-get install r-base
    > echo "/usr/lib/R/lib" > /etc/ld.so.conf.d/R.config
    > ldconfig
    > source /srv/edacc_web/env/bin/activate
    > pip install mysql-python
    > pip install rpy2
    > pip install flask flask-wtf flask-actions flask-mail flask-cache flask-kvsession
    > pip install sqlalchemy pylzma pbkdf2

    - Install R libraries ("R" launches the R interpreter):
    > R
    > (in R) install.packages('np')

    - Create a WSGI file at /srv/edacc_web/edacc_web.wsgi with the following content:
    import site, sys, os
    site.addsitedir('/srv/edacc_web/env/lib/python2.6/site-packages')
    sys.path.append('/srv/edacc_web')
    sys.path.append('/srv/edacc_web/edacc')
    os.environ['PYTHON_EGG_CACHE'] = '/tmp'
    sys.stdout = sys.stderr
    from edacc.web import app as application

    - Configure the web frontend by editing /srv/edacc_web/edacc/config.py
    - Enable the Apache virtual host created earlier:
    > a2ensite edacc_web
    > service apache2 restart

The web frontend should now be running under http://foo.server.com/
