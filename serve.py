from flask import Flask, render_template
from flask_socketio import SocketIO
from flask_socketio import send, emit


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)


@socketio.on('message')
def handle_message(message):
    print("Received message", len(message), message[:25])
    send(message)


@socketio.on('my event')
def handle_my_custom_event(json):
    emit('my response', json)


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    socketio.run(app)
