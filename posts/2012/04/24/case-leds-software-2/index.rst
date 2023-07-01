So, I have just cleaned up, documented a little better, and zipped up the firmware and host side driver for the case LEDs. The file does not contain the hardware schematic because it has some parts in it that I created myself and I don't feel like moving all the symbols around from my gEDA directory and getting all the paths to work correctly.

The host side driver only works on linux at the moment due to the usage of /proc/stat to get CPU usage, but eventually I plan on upgrading it to use `SIGAR <http://www.hyperic.com/products/sigar>`_ or something like that to support more platforms once I get a good environment for developing on Windows going. If you can't wait for me to do it, you could always do it yourself as well.

Anyway, the file is here\: `LED CPU Monitor Software <http://kevincuzner.com/wp-content/uploads/2012/04/ledcpu.tar.gz>`_

Here is the original post detailing the hardware along with a video tour/tutorial/demonstration\: `The Case LEDs 2.0 Completed <http://cuznersoft.com/wordpress/?p=164>`_

.. rstblog-settings::
   :title: Case LEDs Software
   :date: 2012/04/24
   :url: 2012/04/24/case-leds-software-2