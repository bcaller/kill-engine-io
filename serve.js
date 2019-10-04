const server = require('http').createServer();
const io = require('socket.io')(server);
io.on('connection', client => {
  client.on('my event', data => {
    console.log('Received message', data)
    client.emit(data)
  });
});
server.listen(5000);
