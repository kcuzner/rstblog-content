After looking at my design of a few days back I decided it definately needed another revision. For one thing, I switced out the serial->parallel chips to a more common chip that I can get off of digikey (497-5746-1-ND) for $3.30 apiece which isn't too bad (it's not the best though...but it will save on shipping). I also got rid of most of that empty space that I was not using and managed to compress the entire thing so that it is as small as it can get unless I drastically change my design.

 

[caption id="attachment_29" align="alignright" width="610" caption="Dot Matrix revision 2"].. image:: dotmatrix_8x8_v2.png

[/caption]

Major Changes
-------------

As you yan see I have moved all of the chips underneath the displays. I had not done this before because I thought the autorouter wouldn't be able to handle it and I would be left with 100 airwires to resolve. However, when I upgraded the chips the package size had to go up from SSOP to SOIC. This drastically reduced the complexity of routing and made it possible to fit everything beneath the displays. I was a bit sad about this change, but I could only find SOIC versions of the more popular chip (I enjoy soldering small chips because of bragging rights).

Another major change is the position of the mosfets. I have moved them from more or less a column into two "blocks" which are more or less symetrical. I had never thought of this before and it made the airwire ratnest much less dense in the long run with being able to position the column sink chips underneath the adjacent dot matrix module. The mosfets I am using are BSS138LT1GOSDKR-ND (say that 5 times fast) and are $0.58 apiece for 20 (they only way I could find them was on digireel, so the price changes with quantity).

The final major change was an error correction. I found that I had accidentally named all of my clock lines CLK. I have probably 4 different clocks and they were all connected together. I had to separate them and that pretty much broke the last design since I didn't feel like layout out the board in exactly that pattern again.

Releasing my designs
--------------------

I have decided that I am going to publicize my designs if anyone wants them. However, I will not be giving out the eagle files for my own reasons. Eventually I will export the schematic in JPG (I have to clean it up a bit) and I will include the board as gerber and excellon files. This could take time, so don't expect them for a bit.

Fabrication
-----------

I am now thinking of how to get this board fabricated. I have found one company, olimex, who will do it for around $40 per board (no minimum quantity) which is really quite cheap. The also allow panelizing and will cut your boards for you if you want, so I might wait until I have the entire clock finished before sending it off for fabbing. The only problem so far is that my board is .3" too wide for their smaller double sided panel. The upgrade is over $100 and adds about 6" on every side to the space which I don't need unless I decided to make two clocks and panelize all the parts into one board. Hopefully it isn't too hard to get these fabricated since I kind of need them to be fabricated before I can do serious testing on my software.