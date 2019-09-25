# kill-engine-io
DoS python-engineio / python-socketio / Flask-SocketIO via the long polling transport.

By default the engineio server's `max_http_buffer_size` is set to 10e7 bytes.
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

kill-socket-io.py crafts and sends a large payload which tries to abuse this code path
and cause the server to hang on full CPU usage.

The payload contains many small packets (processing is O(n^2) in number of packets).
See https://github.com/bcaller/kill-engine-io/commit/bd5f433335a45ecf1766cc462d0571a56d8f8b4f
for explanation of non-ASCII character to abuse `encoded_payload.decode('utf-8', errors='ignore')`.

## Run

Start test server with `python serve.py` or `python serve.py 2>/dev/null`.
Send payload using code in kill-socket-io.py.
With eventlet (just `pip install eventlet`), a single payload appears to DoS the entire server until processing completes.
Without eventlet, the non-production server remains responsive until the thread pool is exhausted as it launches actual threads.
