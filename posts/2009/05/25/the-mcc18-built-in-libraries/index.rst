.. rstblog-settings::
   :title: The MCC18 built-in libraries
   :date: 2009/05/25
   :url: /2009/05/25/the-mcc18-built-in-libraries
   :tags: programming, wirelessusb

They suck. While waiting for my parts for the clock to come in I have been trying to get my WirelessUSB transmitter to communicate through the USART properly. I ended up discovering that it was having trouble syncing with the start and stop bits and was giving me a bunch of frame errors when receiving, but it had no problem transmitting. I was absolutely puzzled as to why this was happening and I asked around a few forums to see if anyone could shed some light on the subject. One forum (I can't remember which one) said I should try controlling the USART "manually" without using the MCC18 libraries. To my great astonishment, it started echoing back and reading my characters properly without throwing any errors. Obviously, the MCC18 libraries don't work right. I have had similar problems with the MSSP libraries, but I was unable to manually control it at the time because of my lack of experience with it (I could do it now). Basically, I now say\: DON'T USE THE MCC18 LIBRARIES