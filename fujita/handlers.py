import logging

from tornado import web, websocket

from .runner import ActionException

class IndexHandler(web.RequestHandler):
    def get(self):
        self.render("index.html",
            name=self.application.runner.name,
            actions=self.application.actions)

class LogHandler(websocket.WebSocketHandler):
    def open(self):
        self.application.runner.add_line_waiter(self.new_line)

    def on_close(self):
        self.application.runner.remove_line_waiter(self.new_line)

    def new_line(self, id, ts, fd, line):
        self.write_message({
            'id': id,
            'ts': ts,
            'fd': fd,
            'line': line
        })

class StatusHandler(websocket.WebSocketHandler):
    def open(self):
        self.application.runner.add_status_waiter(self.new_status)

    def on_close(self):
        self.application.runner.remove_status_waiter(self.new_status)

    def new_status(self, code, status):
        self.write_message({
            'code': code,
            'status': status
        })

class StartHandler(web.RequestHandler):
    def post(self):
        self.application.runner.start()
        self.write({'status': 'ok'})

class StopHandler(web.RequestHandler):
    def post(self):
        self.application.runner.stop()
        self.write({'status': 'ok'})

class ActionHandler(web.RequestHandler):
    def post(self, action):
        try:
            self.application.runner.run_action(action, self.application.actions[action])
            self.write({'status': 'ok'})
        except (IndexError, ActionException):
            self.write({'status': 'fail'})
