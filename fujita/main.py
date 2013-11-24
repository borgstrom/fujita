import inspect
import logging
import os

from tornado import ioloop, web
from tornado.options import define, options, parse_command_line

from .handlers import LogHandler, IndexHandler, StatusHandler, StartHandler, \
                      StopHandler
from .runner import Runner

define("port", type=int, default=5665, help="The port to run on",
       metavar="PORT")
define("command", type=str, help="The command to run",
       metavar="COMMANDLINE")
define("name", type=str, help="The name of the command, for info purposes",
       default="Command",
       metavar="NAME")

def main():
    parse_command_line()
    if not options.command:
        print "ERROR: You must specify a command. See --help"
        return

    logging.info("Fujita - Starting up %s" % options.name)

    module_dir = os.path.dirname(os.path.abspath(
        inspect.getfile(inspect.currentframe())
    ))

    handlers = [
        (r"/log", LogHandler),
        (r"/status", StatusHandler),
        (r"/start", StartHandler),
        (r"/stop", StopHandler),
        (r"/", IndexHandler),
    ]
    settings = dict(
        debug=True,
        template_path=os.path.join(module_dir, "templates"),
    )

    logging.info("Application listening on port %d" % options.port)
    application = web.Application(handlers, **settings)
    application.listen(options.port)

    # create the Django runner
    application.runner = Runner(options.command, name=options.name)

    logging.info("Starting main IO loop...")
    ioloop.IOLoop.instance().start()
