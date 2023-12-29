.. rstblog-settings::
   :title: A followup on the Dot Matrix Clock
   :date: 2012/02/03
   :url: /2012/02/03/a-followup-on-the-dot-matrix-clock

Since I never quite finished the story about my dot matrix clock, I see no reason why I shouldn't write a bit of a continuation of my current developments. Shortly before I left on my mission for my church in November 2009, `I received my boards for the dot matrix clock and assembled them <http://cuznersoft.com/wordpress/?p=97>`__. However, I ran into a `problem <http://www.youtube.com/watch?v=C79hFcPYrOQ>`__\: The displays would turn off after the voltages on the gates of the row driving mosfets reached a certain voltage and when the voltage was at a level where it would turn on the display, it had some problems with turning on and off the LEDs. Now, after I left on my mission I would think about this once in a while and I figured out the problem\: I was using N-Channel mosfets with only 5V or less of gate driving voltage so they wouldn't turn on/off all the way. I am sure there are more problems than just that, but I keep kicking myself for using N-Channel mosfets instead of using P-Channel. Had I used P-Channel, the problem would have been avoided and this whole thing would have worked great. For the moment, however, this project is on hold since I am designing and building a few things that I will need in the long term here at college since I can't lug around a power supply and an oscilloscope.

So, in summary, if I were to do a re-design I would change the following\:


* The row drivers would be P-Channel mosfets. This would require using something other than a 4->16 demux for a gate driver unless I could find one with inverted outputs. Even with that I would probably put some very small gate drivers (if they exist...the size restriction might be too much) as a buffer to ensure the mosfets were turning on and off properly.


* I would factor in larger tolerances. If there was one design lesson I learned from getting these boards it is that I need to make sure that I make the holes for things a little larger. It would definitely make assembly easier.


* The PIC18F4550 would be replaced for a ATMega of some sort or maybe even a small FPGA. I was running into speed problems with the 18F4550 with getting refresh rates up (I know this is contrary to previous posts, but I was starting to have problems getting 30-60fps like I wanted...even though the image wasn't showing up anyway because of the mosfets). The 12MIPS speed was just a tad too slow and so I think if I were to use a 20MIPS ATMega it would work a lot better. Also, the tools for ATMega seem to be a little more opensourced than the ones for the PIC. I say this because avrgcc runs much better on my Linux machines than the various C compilers for the PIC series. Also, my AVR programmer (a `USBASP <http://www.fischl.de/usbasp/>`__) has very good native Linux support.



Now all that is left for me to do is to figure out how I can modify the boards I have so that I wouldn't have to drop $70 again...