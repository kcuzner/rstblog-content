After spending way to much time thinking about exactly how to do it, I have got multiprocessing working with the WebSocketServer.

I have learned some interesting things about multiprocessing with Python\:
* Basically no complicated objects can be sent over queues.


* Since pickle is used to send the objects, the object must also be serializable


* Methods (i.e. callbacks) cannot be sent either


* Processes can't have new queues added after the initial creation since they aren't picklable, so when the process is created, it has to be given its queues and that's all the queues its ever going to get



So the new model for operation is as follows\:

[caption id="attachment_194" align="aligncenter" width="300"].. image:: /wp-content/uploads/2012/06/WebSocketServer_diagram2-300x267.png
   :target: http://kevincuzner.com/wp-content/uploads/2012/06/WebSocketServer_diagram2.png

 WebSocketServer Diagram[/caption]

Sadly, because of the lack of ability to share methods between processes, there is a lot of polling going on here. A lot. The service has to poll its queues to see if any clients or packets have come in, the server has to poll all the client socket queues to see if anything came in from them and all the service queues to see if the services want to send anything to the clients, etc. I guess it was a sacrifice that had to be made to be able to use multiprocessing. The advantage gained now is that services have access to their own interpreter and so they aren't all forced to share the same CPU. I would imagine this would improve performance with more intensive servers, but the bottleneck will still be with the actual sending and receiving to the clients since every client on the server still has to share the same thread.

So now, the plan to proceed is as follows\:
* Figure out a way to do a pre-forked server so that client polling can be done by more than one process


* Extend the built in classes a bit to simplify service creation and to make it a bit more intuitive.



As always, the source is available at `https\://github.com/kcuzner/python-websocket-server <https://github.com/kcuzner/python-websocket-server>`_

.. rstblog-settings::
   :title: Multiprocessing with the WebSocketServer
   :date: 2012/06/20
   :url: /2012/06/20/multiprocessing-with-the-websocketserver