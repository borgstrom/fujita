import logging
import signal
import time
import uuid

from tornado import ioloop, process

class ActionException(Exception):
    pass

class Runner(object):
    """
    This interface provides a mechanism for launching a process via a command
    line and then fires callbacks when lines of output are available as well
    as status updates (STOPPED or RUNNING)

    The callbacks for lines and status are dispatched via a 'waiters' system,
    allowing for multiple people to be accessing the Tornado instance at the
    same time. 

    Waiters will receive lists with four items, the first is a UUID to id the
    specific message, the second a timestamp for the message, the third is the
    file handle the message came in on (0 for stdout, 1 for stderr) and the
    last is the line received.
    """

    STOPPED = 0
    RUNNING = 1

    def __init__(self, command, name='Command', **process_kwargs):
        logging.info("Initializing %s Runner: %s" % (name, command))
        self.name = name

        # setup our variables used to track callbacks and manage the cache
        self.line_waiters = set()
        self.cache = []
        self.cache_size = 500

        self.status_waiters = set()
        self.set_status(Runner.STOPPED, "Ready to Start")

        # prepare the command & kwargs for the subprocess
        if isinstance(command, list):
            command = " ".join(command)

        # Set shell, stdout & stderr in our kwargs to ensure that we use the
        # proper values. We need to use the shell to ensure that we maintain
        # streams to stdout & stderr so that as the django server restarts
        # our subprocess stays connected
        if not process_kwargs:
            process_kwargs = dict()

        process_kwargs.update(dict(
            shell=True,
            stdout=process.Subprocess.STREAM,
            stderr=process.Subprocess.STREAM
        ))

        self.process = None
        self.process_command = command
        self.process_kwargs = process_kwargs

        self.action = None
        self.action_name = None
        self.action_command = None

    def start(self):
        if not self.process:
            # start the process and begin reading our streams
            logging.info("Starting subprocess: %s" % self.process_command)
            self.process = process.Subprocess(self.process_command, **self.process_kwargs)
            self.read_line(self.process.stdout, self.handle_stdout)
            self.read_line(self.process.stderr, self.handle_stderr)
            self.set_status(Runner.RUNNING, "%s is running" % self.name)

            # setup an exit callback
            self.process.set_exit_callback(self.process_exit)

    def stop(self):
        if self.process:
            self.process.proc.terminate()

    def run_action(self, name, command):
        if self.action:
            errmsg = "Failed to start action %s, " \
                     "another action is already running (%s)" % (
                         name,
                         self.action_name
                     )
            logging.error(errmsg)
            raise ActionException(errmsg)

        logging.info("Starting action: %s" % self.action_name)
        self.action = process.Subprocess(command, **self.process_kwargs)
        self.read_line(self.action.stdout, self.handle_stdout)
        self.read_line(self.action.stderr, self.handle_stderr)
        self.action.set_exit_callback(self.process_action_exit)
        self.action_name = name
        self.action_command = command

    def process_action_exit(self, retcode):
        self.action = None

    def process_exit(self, retcode):
        logging.info("%s exited with return code %d" % (self.name, retcode))
        if retcode != signal.SIGTERM:
            status_msg = "%s is not running (return code %d)" % (self.name, retcode)
        else:
            status_msg = "%s is not running"
        self.set_status(Runner.STOPPED, status_msg)
        self.process = None

    def set_status(self, code, status):
        self.status = status
        self.status_code = code

        for callback in self.status_waiters:
            callback(code, status)

    def add_line_waiter(self, callback):
        logging.debug("Adding new line_waiter %s. Sending %d cache items" % (callback, len(self.cache)))
        for id, ts, fd, line in self.cache:
            callback(id, ts, fd, line)

        self.line_waiters.add(callback)

    def remove_line_waiter(self, callback):
        logging.debug("Removing line_waiter %s" % callback)
        self.line_waiters.remove(callback)

    def send_line_to_waiters(self, fd, line):
        # generate an id & timestap and add it to the cache
        id = str(uuid.uuid4())
        ts = time.time()
        self.cache.append((id, ts, fd, line))

        # send it to the waiters
        for callback in self.line_waiters:
            callback(id, ts, fd, line)

        # trim cache, if necessary
        if len(self.cache) > self.cache_size:
            self.cache = self.cache[-self.cache_size:]

    def read_line(self, stream, callback):
        stream.read_until("\n", callback)

    def handle_stdout(self, line):
        self.send_line_to_waiters(0, line)
        self.read_line(self.process.stdout, self.handle_stdout)

    def handle_stderr(self, line):
        self.send_line_to_waiters(1, line)
        self.read_line(self.process.stderr, self.handle_stderr)

    def add_status_waiter(self, callback):
        logging.debug("Adding new status waiter %s" % callback)
        callback(self.status_code, self.status)
        self.status_waiters.add(callback)

    def remove_status_waiter(self, callback):
        logging.debug("Removing status waiter %s" % callback)
        self.status_waiters.remove(callback)
