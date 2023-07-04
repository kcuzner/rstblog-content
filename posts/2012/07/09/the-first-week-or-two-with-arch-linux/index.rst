After some frustrating times involving Ubuntu 12.04, hibernation, suspending, and random freezing I decided I needed to try something different. Being a Sandy Bridge desktop, my computer naturally seems to have a slight problem with Linux support in general. Don't get me wrong, I really like my computer and my processor...however, the hardware drivers at times frustrate me. So, at my wits end I decided to do something crazy and take the plunge to a bleeding edge rolling release linux\: Arch Linux.

Arch Linux is interesting for me since its the first time I have not been using an operating system with the "version" paradigm. Since its a rolling release it is prone to more problems, but it also gives the advantage of always being up to date. Since my computer's hardware is relatively new (it has been superseded by Ivy Bridge, but even so its driver support still seems to be being built), I felt that I had more to gain from doing a rolling release where new updates and such would come out (think kernel 3.0 to 3-2...Sandy Bridge processors suddenly got much better power management) almost immediately. So, without further adieu, here are my plusses and minuses (note that this will end up comparing Ubuntu to Arch alot since that's all I know at the moment)\:

**Plusses\:**
* It was actually very easy to install. Since I have had problems with net installs, I did a core install and then updated it. I practiced several times beforehand on virtual machines, including using existing partitions and such. Although the initial downloads took some time (the lack of curl in the core install was kind of upsetting since I couldn't use rankmirrors to get better speeds), after that it was pretty fast. Thanks to considerable documentation and a few practice runs, getting an X enviroment set up using Gnome 3 (and gdm...I like the graphical logins) didn't take long at all. It took a bit of coaxing (read\: google + arch wiki) to get things such as networkmanager running and such, but with time I had it all figured out and I managed to get the whole system running more or less stably within a day.


* It boots faster than Ubuntu and is more explicit about what exactly it's doing. I liked the Ubuntu moving logo thing, but I do actually enjoy seeing what the computer is doing when it boots. Coming from pure asthetic reasons, it gives the computer more of a "raw" feel which for some strange masochistic reason, I enjoy. The slowest part is initializing the networks and if that didn't have to happen the entire system could boot in under 60 seconds after the bios gets done showing off its screen.


* The documentation is awesome. Clearly, people have spent lots and lots and lots of time writing the documentation in the wiki for Arch. It certainly made setting up easier since many of the random corner cases were in the troubleshooting section of severl articles and I ended up running into a couple of them. One thing that was easier to set up than in Ubuntu was suspending and hibernating (at least getting it to work reliably). With some help from the forum (see next point) and a few pages of documentationon pm-utils I got suspend, resume, and hibernate (!!!) running. I haven't even gotten hibernate to work in Windows.


* The community is great. I rarely have been able to get a question answered on the Ubuntu forums since they are so conjested. I asked a question on the arch bbs and in less than a day I had a response and was able to do some trial + error and troubleshooting involving the suspend and hibernate functionality of my computer.



**Minuses\:**
* The rolling release model breaks things occasionally. Recently, the linux-firmware package was updated and this caused my wireless card to stop working since it could no longer find the drivers. I wasn't sure why, but I have just downgraded the package and blacklisted it for upgrades. Hopefully that doesn't kill me later (it probably will), but if it does by then I hope to have figured out what is wrong.


* With great power comes great responsibility. The sheer flexibility is great since I don't have a bunch of extra packages I don't need, but at the same time when I was practicing with the VMs, I was able to get myself stuck in a hole where the only solution was to re-format the drive. However, ever since a mishap with Ubuntu (the themeing engine changed all my stuff to black on black or white on white for the text) I have separated out my home folder from the system so that I can easily re-format and re-install the system without losing all my stuff (all 132Gb of it).


* This isn't a problem for most people, but it doesn't access the hard drive as often as other distros. Why is that a con for me? Well, I have a western digital green hard drive which has an automated parking feature which parks the heads after 10 seconds of inactivity. Well, in windows this doesn't matter, but in linux since it touches the filesystem every 11-15 seconds or so, that results on a LOT of head parkings. Considering that the heads are only rated for 300K cycles and people have reported reaching that in less than a year, it is a real issue. I have a program (`wdantiparkd <www.sagaforce.com/~sound/wdantiparkd/>`__) which writes the hard drive every 7 seconds while watching to see if anything else has written to the hard drive so that it hangs up after 10 minutes rather than 10 seconds. It helps, but it worked better on Ubuntu.



Overall, this experience with Arch has allowed me to become much more familiar with Linux and its guts and slowely but surely I am getting better at fixing issues. If you are considering a switch from your present operating system and already have experience with Linux (especially the command line since that's what you are stuck with starting out before you install xfce, Gnome, KDE, etc), I would recommend this distribution. Of course, if you get easily frustrated with problems and don't enjoy solving them, perhaps a little more stability would be something to look for instead.

Here is my desktop as it stands\:

[caption id="attachment_206" align="aligncenter" width="1024"].. image:: /wp-content/uploads/2012/07/Screenshot-from-2012-07-09-085931-1024x640.png
   :target: http://kevincuzner.com/wp-content/uploads/2012/07/Screenshot-from-2012-07-09-085931.png

 Arch Linux with Gnome 3[/caption]

.. rstblog-settings::
   :title: The first week or two with Arch Linux
   :date: 2012/07/09
   :url: /2012/07/09/the-first-week-or-two-with-arch-linux