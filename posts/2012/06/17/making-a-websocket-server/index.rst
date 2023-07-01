For the past few weeks I have been experimenting a bit with HTML5 WebSockets. I don't normally focus only on software when building something, but this has been an interesting project and has allowed me to learn a lot more about the nitty gritty of sockets and such. I have created a github repository for it (it's my first time using git and I'm loving it) which is here\: `https\://github.com/kcuzner/python-websocket-server <https://github.com/kcuzner/python-websocket-server>`_

The server I have runs on a port which is considered a dedicated port for WebSocket-based services. The server is written in `python <http://www.python.org/>`_ and defines a few base classes for implementing a service. The basic structure is as follows\:

[caption id="attachment_189" align="aligncenter" width="300"].. image:: WebSocketServer_diagram.png
   :target: http://kevincuzner.com/wp-content/uploads/2012/05/WebSocketServer_diagram.png

 Super-basic flowchart[/caption]

Each service has its own `thread <http://docs.python.org/library/threading.html#thread-objects>`_ and inherits from a base class which is a thread plus a queue for accepting new clients. The clients are a `socket <http://docs.python.org/library/socket.html#socket-objects>`_ object returned by socket.accept which are wrapped in a class that allows for communication to the socket via queues. The actual communication to sockets is managed by a separate thread that handles all the encoding and decoding to websocket frames. Since adding a client doesn't produce much overhead, this structure potentially could be expanded very easily to handle many many clients.

A few things I plan on adding to the server eventually are\:
* Using processes instead of threads for the services. Due to the global interpreter lock, if this is run using CPython (which is what most people use as far as I know and also what comes installed by default on many systems) all the threads will be locked to use the same CPU since the python interpreter can't be used by more than one thread at once (however, it can for processes). The difficult part of all this is that it is hard to pass actual objects between processes and I have to do some serious re-structuring for the code to work without needing to pass objects (such as sockets) to services.


* Creating a better structure for web services (currently only two base classes are really available) including a generalized database binding that is thread safe so that a service could potentially split into many threads while not overwhelming the database connection.



Currently, the repository includes a demo chatroom service for which I should have the client side application done soon and uploaded. Currently it supports multiple chatrooms and multiple users, but there is no authentication really and there are a few features I would like to add (such as being able to see who is in the chatroom).

.. rstblog-settings::
   :title: Making a WebSocket server
   :date: 2012/06/17
   :url: /2012/06/17/making-a-websocket-server