from flask import Flask
import json

app = Flask(__name__)


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


if __name__ == '__main__':
    config = json.load(open("config.json"))

    app.run()
