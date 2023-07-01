So, this last week I got an email from rackspace saying that my server was thrashing the hard drives and lowering performance of everyone else on that same machine. In consequence, they had rebooted my server for me.

I made a few mistakes in the setup of this first iteration of my server\: I didn't restart it after kernel updates, I ran folding@home on it while running nodejs, and I didn't have backups turned on. I had it running for well over 200 days without a reboot while there had been a dozen or so kernel updates. When they hard rebooted my server, it wouldn't respond at all to pings, ssh, or otherwise. In fact, it behaved like the firewalls were shut (hanging on the "waiting" step rather than saying "connection refused"). I ended up having to go into their handy rescue mode and copy out all the files. I only copied my www directory and the mysql binary table files, but as you can see, I was able to restore the server from those.

This gave me an excellent opportunity to actually set up my server correctly. I no longer have to be root to edit my website files (yay!), I have virtual hosts set up in a fashion that makes sense and actually works, and overall performance seems to be improved. From now on, I will be doing the updates less frequently and when I do I will be rebooting the machine. That should fix the problem with breaking everything if a hard reboot happens.

I do pay for the hosting for this, 1.5 cents per hour per 256Mb of RAM with extra for bandwidth. I only have 256Mb and since I don't make any profit off this server whatsoever at the moment, I plan on keeping it that way for now. Considering that back in the day, 256Mb was a ton of memory, it clearly no longer suffices for running too much on my server (httpd + mysql + nodejs + folding@home = crash and burn).

.. rstblog-settings::
   :title: 256Mb doesn't do what it used to...
   :date: 2013/02/26
   :url: /2013/02/26/256mb-doesnt-do-what-it-used-to