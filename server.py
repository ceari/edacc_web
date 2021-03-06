#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Development server, using Flask's builtin server
    run 'python server.py' from a terminal to launch
"""

#from tornado.wsgi import WSGIContainer
#from tornado.httpserver import HTTPServer
#from tornado.ioloop import IOLoop
#from edacc.web import app

#if __name__ == '__main__':
#    http_server = HTTPServer(WSGIContainer(app))
#    http_server.listen(5000)
#    IOLoop.instance().start()


from edacc.web import app
from edacc.config import DEBUG

#from werkzeug.contrib.profiler import ProfilerMiddleware
#app.wsgi_app = ProfilerMiddleware(app.wsgi_app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=DEBUG)
