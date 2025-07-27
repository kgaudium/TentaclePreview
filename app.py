from flask import Flask
from TentaclePreview import output
import time
from TentaclePreview import tentacle_preview as tentacle

app = Flask(__name__)


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


if __name__ == '__main__':
    tentacle.init()

    # app.run()
