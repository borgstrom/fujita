import ConfigParser
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
define("config", type=str, help="The file that defines the commands to manage",
       metavar="FILE")
define("debug", type=bool, default=False, help="Tornado debugging")

def main():
    parse_command_line()
    if not options.config:
        print "ERROR: You must specify a config. See --help"
        return

    logging.info("Fujita - Starting up")

    module_dir = os.path.dirname(os.path.abspath(
        inspect.getfile(inspect.currentframe())
    ))

    handlers = [
        (r"/log", LogHandler),
        (r"/status", StatusHandler),
        (r"/start/([^/]+)", StartHandler),
        (r"/stop", StopHandler),
        (r"/", IndexHandler),
    ]
    settings = dict(
        debug=options.debug,
        template_path=os.path.join(module_dir, "templates"),
    )

    logging.info("Application listening on port %d" % options.port)
    application = web.Application(handlers, **settings)
    application.listen(options.port)

    # parse our config
    logging.info("Parsing config...")
    application.config = ConfigParser.ConfigParser()
    application.config.read(options.config)
    commands = application.config.sections()
    logging.info("Loaded %d commands: %s" % (
        len(commands),
        ", ".join(commands)
    ))

    # create the main runner
    application.runner = Runner()

    logging.info("Starting main IO loop...")
    ioloop.IOLoop.instance().start()
