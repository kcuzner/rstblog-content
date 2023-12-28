Well, here it is. The moment I have been anticipating for a good while\: The boards came in and I assembled them. I made a few videos and took a few pictures. I won't post the videos yet since I am still going through them and making sure that I don't go and make a fool of myself.













After getting that far, I believe my camera died. Anyways, I assembled the breakout board and completed all the parts of the display. I did not solder down all the display modules to the pcb because I am going to be fiddling around with the resistors on the column sinks and I didn't want to have to desolder a display before being able to do anything else. The next day, I started testing\:



As for testing and stuff, it mostly works. I made a few errors in both the hardware and the software, but I at least got the LEDs to turn on (I have not, however, gotten them to turn off properly...). My original program which should have been immediately portable to the hardware did not work so well and I ended up writing the entire display portion of the program in assembler\: Apparently doing a variable bit shift on a 32 bit number takes up a very...long...time when compiled in C for the PIC18F. The main issue with the original program was that when I expanded the display size to 40x16 it suddenly had no refresh rate to speak of. This was mainly a product of the way I had organized memory. I had stuck the entire display into an array of long ints so that access to individual pixels could be done almost entirely by index. Sadly, when the size of the display was multiplied by 10 the computation of the bitmask began to take too long and made it impossible to properly refresh the rows. The assembly program I made to replace this organizes memory in the same fashion that I believe VGA cards organize the memory\: Everything in one big long array which has no end-of-row designation and just wraps around when it is displayed. This ended up being much faster and hopefully it will work for the finished product.

As for the hardware problems, I have several. First of all, I made the primary mechanical engineering mestake when designing the package footprints\: I didn't factor in tolerances. All the through-hole parts BARELY fit. In fact, I have to coax everything in using a craft knife to get the pins lined up exactly before the part will even go in. The button pins are going to have to be sanded down since there is a taper to the pins that was not in the datasheet which makes the pins too large for the holes. The next big problem is that the column sinks are behaving very strangely. After the voltage into the LEDs passes above 3.3V or so some of the columns just stop sinking while others stay on. I have a few ideas to find out exactly what is going on here, but I have no real plan of action to fix that as of yet. My final problem is that I somehow managed to lift a pad when soldering down a resistor. How this happened I am not sure, but I think it has to do with cheap board construction and using a solder wik that is too big. I barely managed to find a trace to solder to, so it is kind of fragile even with the hot glue I used to secure the wirewrapping wire I used as a trace extender. The next time I do this I am putting a via in EVERY trace that runs into a pad, even if it doesn't need one just for this sort of situation.

Anyway, aside from the mentioned problems the boards turned out pretty well. Olimex was fast and relatively polite. Their construction wasn't too bad (aside from the pad, but that may have been mostly my fault) and the boards shipped right on time and arrived right on time (to the day, in fact). Overall I would say this whole board experience wasn't bad and since it mostly worked I will say I didn't waste my money.

.. rstblog-settings::
   :title: Dot Matrix Clock: Display board assembly
   :date: 2009/10/07
   :url: /2009/10/07/dot-matrix-clock-display-board-assembly