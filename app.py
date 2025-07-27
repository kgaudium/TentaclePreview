import signal
import sys

from flask import Flask
from TentaclePreview import output
import time
from TentaclePreview import tentacle_preview as tentacle

app = Flask(__name__)


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


def graceful_shutdown(*_):
    print()
    output.log("Got shutdown signal", "warning")
    tentacle.stop_tentacles()
    sys.exit(0)

signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)

if __name__ == '__main__':
    tentacle.init()
    while True:
        time.sleep(1)
    # app.run()
