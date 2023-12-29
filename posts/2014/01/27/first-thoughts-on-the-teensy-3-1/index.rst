.. rstblog-settings::
   :title: First thoughts on the Teensy 3.1
   :date: 2014/01/27
   :url: /2014/01/27/first-thoughts-on-the-teensy-3-1

Wow it has been a while; I have not written since August.

I entered a contest of sorts this past week which involves building an autonomous turret which uses an ultrasonic sensor to locate a target within 10 feet and fire at it with a tiny dart gun. The entire assembly is to be mounted on servos. This is something my University is doing as an extra-curricular for engineers and so when a friend of mine asked if I wanted to join forces with him and conquer, I readily agreed.

The most interesting part to me, by far, is the processor to be used. It is going to be a Teensy 3.1\:



This board contains a Freescale ARM Cortex-M4 microcontroller along with a smaller non-user-programmable microcontroller for assistance in the USB bootloading process (the exact details of that interaction are mostly unknown to me at the moment). I have never used an ARM microcontroller before and never a microcontroller with as many peripherals as this one has. The datasheet is 1200 pages long and is not really even being very verbose in my opinion. It could easily be 3000 pages if they included the level of detail usually included in AVR and PIC datasheets (code examples, etc). The processor runs at 96Mhz as well, making it the most powerful embedded computer I have used aside from my Raspberry Pi.

The Teensy 3.1 is Arduino-compliant and is designed that way. However, it can also be used without the Arduino software. I have not used an Arduino before since I rather enjoy using microcontrollers in a bare-bones fashion. However, it is become increasingly more difficult for me to be able to experiment with the latest in microcontroller developments using breadboards since the packages are becoming increasingly more surface mount.

The Arduino IDE
---------------


Oh my goodness. Worst ever. Ok, not really, but I really have a hard time justifying using it other than the fact that it makes downloading to the Teensy really easy. This post isn't meant to be a review of the arduino IDE, but the editor could use some serious improvements IMHO\:


* Tab indentation level\: Some of us would like to use something other than 2 spaces, thank you very much. We don't live in the 70's where horizontal space is at a premium and I prefer 4 spaces. Purely personal preference, but I feel like the option should be there


* Ability to reload files\: The inability to reload the files and the fact that it seems to compile from a cache rather than from the file itself makes the arduino IDE basically incompatible with git or any other source control system. This is a serious problem, in my opinion, and requires me to restart the editor frequently whenever I check out a different branch.


* Real project files\: I understand the aim for simplicity here, but when you have a chip with 256Kb of flash on it, your program is not going to be 100 lines and fit into one file. At the moment, the editor just takes everything in the directory and compiles it by file extension. No subdirectories and every file will be displayed as a separate tab with no way to close it. I am in the habit of separating my source and not having the ability to structure my files how I please really makes me feel hampered. To make matters worse, the IDE saves the original sketch file (which is just a cpp file that will be run through their preprocessor) with its own special file extension (\*.ino) which makes it look like it should be a project file, but in reality it is not.



There are few things I do like, however. I do like their library of things that make working with this new and foreign processor rather easy. I also like that their build system is very cross-platform and easy to use.

First impression of the processor
---------------------------------


I must first say that the level of work that has gone into the surrounding software (the header files, the teensy loader, etc) truly shows and makes it a good experience to use the Teensy, even if the Arduino IDE sucks. I tried a Makefile approach using Code\:\:Blocks, but it was difficult for me to get it to compile cross-platform and I was afraid that I would accidentally overwrite some bootloader code that I hadn't known about. So, I ended up just going with the Ardiuno IDE for safety reasons.

The peripherals on this processor are many and it is hard at times to figure out basic functions, such as the GPIO. The manual for the peripherals is in the neighborhood of 60 chapters long, with each chapter describing a peripheral. So far, I have messed with just the GPIOs and pin interrupts, but I plan on moving on to the timer module very soon. This project likely won't require the DMA or the variety of onboard bus modules (CAN, I2C, SPI, USB, etc), but in the future I hope to have a Teensy of my own to experiment on. The sheer number of registers combined with the 32-bit width of everything is a totally new experience for me. Combine that with the fact that I don't have to worry as much about the overhead of using certain C constructs (struct and function pointers for example) and I am super duper excited about this processor. Tack on the stuff that PJRC created for using the Teensy such as the nice header files and the overall compatibility with some Arduino libraries, and I have had an easier time getting this thing to work than with most of my other projects I have done.

Conclusion
----------


Although the Teensy is for a specific contest project right now, at the price of $19.80 for the amount of power that it gives, I believe I will buy one for myself to mess around with. I am looking forward to getting more familiar with this processor and although I resent the IDE I have to work with at the moment, I hope that I will be able to move along to better compilation options that will let me move away from the arduino IDE.