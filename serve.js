const server = require('http').createServer();
const io = require('socket.io')(server);
io.on('connection', client => {
  client.on('my event', data => {
    console.log('Received message', data)
    client.emit(data)
  });
});
console.log("Listening on port 5000");
const bufferSize = io.eio.maxHttpBufferSize || io.eio.opts.maxHttpBufferSize
console.log(`Max HTTP Buffer Size: ${bufferSize} = 1e${Math.log10(bufferSize)}`);
server.listen(5000);
