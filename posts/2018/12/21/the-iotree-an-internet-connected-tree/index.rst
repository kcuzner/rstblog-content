For this Christmas I decided to do something fun with my Christmas tree\: Hook it up to the internet.

**Visit the IoTree here (available through the 1st week of January 2019)\:**


`http\://kevincuzner.com/iotree <http://kevincuzner.com/iotree>`_


**The complete source can be found here\:**


`http\://github.com/kcuzner/iotree <http://github.com/kcuzner/iotree>`_



[caption id="attachment_649" align="alignright" width="1125"].. image:: Christmas-Tree-in-Action-Cropped.png
   :target: http://kevincuzner.com/wp-content/uploads/2018/12/Christmas-Tree-in-Action-Cropped.png

 The IoTree[/caption]

The IoTree is an interface that allows anyone to control the pattern of lights shown on the small Christmas tree on my workbench. It consists of the following components\:
* My Kinetis KL26 breakout board (`http\://github.com/kcuzner/kl2-dev <http://github.com/kcuzner/kl2-dev>`_). This controls a string of 50 WS2811 LEDs which are zip-tied to the tree.


* A Raspberry Pi (mid-2012 vintage) which parses pattern commands coming from the cloud into LED sequences which are downloaded to the KL26 over SPI. It also hosts a webcam and periodically throws the image back up to the cloud so that the masses can see the results of their labors.


* A cloud server which hosts a Redis instance and python application to facilitate the user interface and communication down to the Raspberry Pi.



I'm going to go into brief detail about each of these pieces and some of the challenges I had with getting everything to work.


.. rstblog-break::


WS2811 Control\: A Freescale Kinetis KL26 Microcontroller
=========================================================

My first foray into ARM microcontrollers was a Freescale K20 on the Teensy 3.1. I thought the Kinetis family was awesome, I started designing myself a development/breakout board based on the KL26 some years ago and actually built one up. What I didn't realize at the time was that compared to other ARM Cortex microcontroller lines, the documentation and tools for the Kinetis family is severely lacking. I had a very difficult time getting it to program. I put the project on the shelf and didn't get it out again until several months ago when I `learned <https://learn.adafruit.com/programming-microcontrollers-using-openocd-on-raspberry-pi/overview>`_ that there was a "raspberrypi-native" config script available that is enabled by a compile-time option. I compiled openocd with that option, wired up the KL26, and managed to flash a blinking program! However, I found that the reset procedure using the raspberrypi-native interface wasn't quite as reliable as the reset procedure for the STM32 using the STLink-v2 and I would often have to fiddle with the exact reset/init procedure if something went wrong during the previous programming cycle.

My interest soon declined and I put the KL26 back on the shelf again until this project, since I realized that it was pretty much my only dev/breakout board with an ARM microcontroller on it that I had available. I stuck the KL26 breakout on a breadboard and hooked it up to the WS2811 light string I had purchased off ebay. At first, I tried to get the USB working so I could build myself a little WS2811-USB dongle, but I ended up settling for a simpler SPI-based approach after it was started taking too long to debug the myriad issues I was having with the clocking system and USB peripheral (I believe I didn't have the crystal wired properly to the KL26 on my dev board and it was somewhat unstable).

The SPI peripheral in the KL26 leaves much to be desired when operating in slave mode. While I just ended up having it receive blocks of 150 bytes (1 byte for each of the red, green, and blue values of the 50 LEDs), determining when the Raspberry Pi had stopped sending data turned out to be somewhat difficult. There isn't a nice obvious way for it to signal to the firmware that the slave-select signal had been deasserted. I probably could have found information about how to accomplish this, but the documentation on their SPI module is particularly lacking on that subject.

In the end, I ended up settling for a dead-reckoning approach where I just send 150 bytes at a time to the microcontroller and the microcontroller expects 150 bytes. I effectively ignore the slave-select pin other than hooking it up to the peripheral so that it can appropriately ignore the SCK and MOSI signals when needed. So long as I don't drop any bytes, I shouldn't see any misalignment. And if there is misalignment, the tree would still be colorful, even if it wasn't the right colors.

Raspberry Pi Webcam Stream\: Fun with v4l2!
===========================================

While getting the Raspberry Pi to send things over SPI was pretty easy, getting frames from the webcam was not nearly as straightforward as I would have liked. My original plan was to use OpenCV to grab the frames and then use `Redis' PUBSUB <https://redis.io/topics/pubsub>`_ functionality to throw the captured frames up to the cloud. I found that there were two problems with this approach\:
#. It is difficult to install OpenCV for Arch on the raspberry pi and have it cooperate with Python. I was trying to use virtualenv to keep things encapsulated so that I wouldn't start depending on Arch system packages.


#. Latency with PUBSUB was going to be a problem, since there isn't a way to "skip ahead" in the stream if the server got behind. Redis also drops connections which are causing the pubsub pipeline to back up, which would require additional error handling in my webapp later.



What I ended up doing was using v4l2 directly in order to grab the frames from the camera and then simply SET'ing the acquired frame to a value in Redis (with some expiration). With `Redis Keyspace Notifications <https://redis.io/topics/notifications>`_ turned on, the web application could be notified and retrieve the very latest frame at its leisure. Frames could easily be dropped if anyone got behind, but considering that the nature of this project is to see semi-instantaneous reactions to your LED control inputs, that seemed to be desirable behavior.

Getting V4L2 to work took some effort as well, since I ended up running into some performance issues. I still haven't solved these fully and the Raspberry Pi tops out at 7fps at 720p. I found `this blog post <https://jayrambhia.com/blog/capture-v4l2>`_ about V4L2 in C/C++ to be quite useful and I ended up borrowing a lot of the sequence for starting the capture and such from it (along with heavy consultation with the `v4l2 documentation <https://linuxtv.org/downloads/v4l-dvb-apis/>`_). My webcam supports a raw YUV format and a M-JPEG format. I ended up using the M-JPEG even though it doesn't return proper JPEG images (some encoding table at the beginning of the image is missing, which is apparently very common for M-JPEG). I simply post the binary data for the JPEG into Redis.

The final result is here\: `https\://github.com/kcuzner/iotree/blob/master/raspi/webcam.py <https://github.com/kcuzner/iotree/blob/master/raspi/webcam.py>`_

Python, Flask, Vue, Streaming, and Websockets
=============================================

The webapp side of this whole project I decided to do in Python because it seemed the fastest way for me to get going. I made a really simple Flask application that serves a single page, a few static files, and the video stream. Most of this was pretty straightforward since its a very common thing to do, but one thing I want to mention briefly was the way I ended up creating the video stream.

I am 99% sure I picked the wrong way to do a video stream, but it seems to work for me. Here's the entirety of the Flask endpoint that produces a continuous video stream\:

.. code-block:: {lang}



   @app.route('/video')
   def video_feed():
       """
       Streams images from the server
       """
       db_stream = open_redis(settings)
       db_image = open_redis(settings)
       ps = db_stream.pubsub()
       ps.subscribe('__keyspace@0__:image')

       streamon = True

       def generate():
           while streamon:
               for message in ps.listen():
                   if message['channel'] == b'__keyspace@0__:image' and\
                           message['data'] == b'set':
                       data = db_image.get('image')
                       yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + data + b'\r\n')

       response = Response(generate(),
               mimetype='multipart/x-mixed-replace; boundary=frame')

       @response.call_on_close
       def done():
           streamon = False
           ps.close()

   return response

This works by way of the "multipart/x-mixed-replace" content type. I hadn't even heard of this content type before I found a `blog post <https://blog.miguelgrinberg.com/post/video-streaming-with-flask>`_ describing it for use in a video stream. How it works is that a "boundary" string is defined and all data between that boundary string and the next is considered one "frame" of the image. When Chrome or Firefox (sorry IE) receive something with this type whose content-type ends up being image/jpeg, they will replace the image with the latest one received. In flask, I simply supply a generator that occasionally yields bytes containing the next frame. This works really well so far, but there are a couple downsides and quirks with this approach\:
* Each video stream has its own Redis connection. I did this on purpose so that a single slow client wouldn't slow everyone down. The downside here is that I now rely on Redis' dropping slow clients.


* Once a stream is interrupted, it is done. It cannot be resumed, since the server has now dropped that connection. I tried to remedy this with some kind of refresh logic, but see the next point.


* On desktop Firefox (and I think Chrome too), the onload event fires for the image every time a frame is received. This is super convenient and I was using it to create a little "buffering" popover that would suggest that the user refresh the page if the stream was interrupted. However, when I was testing with my phone (since I posted this on Facebook first and assumed many people would be using their phones to access it), I found that the onload event was only firing for the first frame. I ended up abandoning this functionality since I didn't want to spend much more time on this quirk.



Everything else with the webapp is pretty straightforward. I am using Apache to forward everything to the Flask application. The application is using eventlet since it claims to be a production-ready server, whereas the default Flask server is not. The use of eventlet brings me to my next quirk\: AWS Linux.

I did most of the development of the webapp on my desktop PC, which runs Arch Linux. Once I had gotten it working enough to publish, I pushed it up to my AWS cloud server which runs their Linux flavor. Since I had used virtualenv to encapsulate all the requirements and I managed to avoid requiring any system dependencies, I had assumed it would be all good and installation would proceed as usual via "pip install -r requirements.txt" with my "requirements.txt" containing all my package dependencies. Not so! Apparently, AWS Linux is not supported by the "manylinux1" wheel type. I am still not quite sure how that whole mechanism works, but the end result was that one of eventlet's dependencies (greenlet) could not be installed using "pip". Rather than try to mess with installed packages to get pip to recognize my system as manylinux1-compliant, I decided to fall back to the system packages. The downside here is that eventlet was only available for Python 2 through the AWS system packages. I ended up downgrading the webapp to python 2 just to support that one dependency.

Conclusion
==========

This project was a lot of fun. Once all the parts were running, seeing my Christmas Tree change in response to the commands of the internet mob turned into a great time for me. I have skipped some stuff (like figuring out a good-enough way to describe LED patterns programmatically, learning Vue for the first time, and other things), but that's what the github repository is for. I am going to shut down the tree in a week or two, since the AWS bandwidth charges per day with multiple simultaneous video streams are somewhat higher than what I am used to with this website and the holiday season will have ended, but I hope that the internet can have some fun with it while it's here.

If you have remarks or questions, feel free to leave them below in the comments.

.. rstblog-settings::
   :title: The IoTree: An internet-connected tree
   :date: 2018/12/21
   :url: /2018/12/21/the-iotree-an-internet-connected-tree