I took the plunge and decided to re-implement what I had in Python using C++. I had to change up my structure a bit, but I made the switch because of the following reasons\:


* The Qt Framework. While there are bindings for Python, I really liked Qt-Creator. Also, Qt is extremely cross platform (at least that is how it seems) and has a large amount of libraries. I've been messing around with it now for a bit trying to get a few things to work.


* This is redundant of the above, but I really like the Qt Plugin system. After struggling with it for a bit, I finally was able to get a plugin to load. I will explain a little bit below exactly what I plan on doing with these.


* As awesome as Python is, it doesn't support true multithreading (it does multiprocessing...and to do what I wanted to do using multiprocessing would have required me to jump through some hula hoops)


* C++ should have the potential to run faster than Python for mathematical things, which in this situation is a good trade off for ease of programming.


* Writing the application entirely in C++ with Qt lowers the number of dependencies that would have to be installed on a client machine.



Now, the biggest advantages I see are\: Speed and Extensibility. Python is extremely extensible, but it doesn't have the greatest speed. C++ has the potential to run faster and then by using Qt, the extensibility part was brought in. I also prefer strongly typed systems since they keep me from stepping on my toes programmatically.

By far the coolest part of all this is the Plugins. After discovering that ALL communication between Plugins and the application must be done using interfaces, I realized that if I were to implement the entire thing using interfaces it could be extended to do many awesome things. So far, however, I have only really added interfaces to allow for adding computational "blocks" to the system for use in schematics. The system itself will define no blocks since I have decided to separate the engine from the actual blocks.

I will be posting later a bit about Qt plugins since that is what I have spent the most time on. Google was definitely my friend on that one. Most people it seems just use Qt Plugins for extending Qt itself rather than doing the "low level" extending the application stuff.

In terms of development time, C++ is quite a bit slower for me than Python. However, my potential to write good code is much higher since I am much more familiar with C++ coding conventions and I am more able to clean code while being confident nothing is being broken since in Python, there are no compile-time errors to tell you that you switched the arguments to a function.

.. rstblog-settings::
   :title: Simulink clone...now in C++
   :date: 2012/10/21
   :url: /2012/10/21/simulink-clone-now-in-c