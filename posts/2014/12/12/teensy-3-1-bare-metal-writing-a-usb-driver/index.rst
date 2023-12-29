.. rstblog-settings::
   :title: Teensy 3.1 bare metal: Writing a USB driver
   :date: 2014/12/12
   :url: /2014/12/12/teensy-3-1-bare-metal-writing-a-usb-driver

One of the things that has intrigued me for the past couple years is making embedded USB devices. It's an industry standard bus that just about any piece of computing hardware can connect with yet is complex enough that doing it yourself is a bit of a chore.

Traditionally I have used the work of others, mainly the `V-USB <http://www.obdev.at/products/vusb/index.html>`__ driver for AVR, to get my devices connected. Lately I have been messing around more with the ARM processor on a Teensy 3.1 which has an integrated USB module. The last microcontrollers I used that had these were the PIC18F4550s that I used in my dot matrix project. Even with those, I used microchip's library and drivers.



Over the thanksgiving break I started cobbling together some software with the intent of writing a driver for the USB module in the Teensy myself. I started originally with `my bare metal stuff <http://kevincuzner.com/2014/04/28/teensy-3-1-bare-metal/>`__, but I ended up going with something closer to `Karl Lunt's solution <http://www.seanet.com/~karllunt/bareteensy31.html>`__. I configured code\:\:blocks to use the arm-none-eabi compiler that I had installed and created a code blocks project for my code and used that to build it (with a post-compile event translating the generated elf file into a hex file).

**This is a work in progress and the git repository will be updated as things progress since it's not a dedicated demonstration of the USB driver.** 

The github repository here will be eventually turned in to a really really rudimentary 500-800ksps oscilloscope.

**The code\:**  `https\://github.com/kcuzner/teensy-oscilloscope <https://github.com/kcuzner/teensy-oscilloscope>`__

The code for this post was taken from the following commit\:

`https\://github.com/kcuzner/teensy-oscilloscope/tree/9a5a4c9108717cfec0174709a72edeab93fcf2b8 <https://github.com/kcuzner/teensy-oscilloscope/tree/9a5a4c9108717cfec0174709a72edeab93fcf2b8>`__

At the end of this post, I will have outlined all of the pieces needed to have a simple USB device setup that responds with a descriptor on endpoint 0.

Contents
========


`USB Basics <usb-basics>`__

`The Freescale K20 Family and their USB module <freescale-usb>`__

`Part 1\: The clocks <part-1-clocks>`__

`Part 2\: The startup sequence <part-2-startup>`__

`Part 3\: The interrupt handler state machine <part-3-interrupts>`__

`Part 4\: Token processing & descriptors <part-4-tokens>`__

`Where to go from here <where-next>`__

`Conclusion <conclusion>`__

USB Basics
==========


I will actually not be talking about these here as I am most definitely no expert. However, I will point to the page that I found most helpful when writing this\:
`http\://www.usbmadesimple.co.uk/index.html <http://www.usbmadesimple.co.uk/index.html>`__


This site explained very clearly exactly what was going on with USB. Coupled with my previous knowledge, it was almost all I needed in terms of getting the protocol.




The Freescale K20 Family and their USB module
=============================================


The one thing that I don't like about all of these great microcontrollers that come out with USB support is that all of them have their very own special USB module which doesn't work like anyone else. Sure, there are similarities, but there are no two *exactly* alike. Since I have a Teensy and the K20 family of microcontrollers seem to be relatively popular, I don't feel bad about writing such specific software.

There are two documents I found to be essential to writing this driver\:


#. The family manual. Getting a correct version for the MK20DX256VLH7 (the processor on the Teensy) can be a pain. PJRC comes to the rescue here\: `http\://www.pjrc.com/teensy/K20P64M72SF1RM.pdf <http://www.pjrc.com/teensy/K20P64M72SF1RM.pdf>`__ (note, the Teensies based on the MK20DX128VLH5 use a different manual)


#. The Kinetis Peripheral Module Quick Reference\: `http\://cache.freescale.com/files/32bit/doc/quick_ref_guide/KQRUG.pdf <http://cache.freescale.com/files/32bit/doc/quick_ref_guide/KQRUG.pdf>`__. This specifies the initialization sequence and other things that will be needed for the module.



There are a few essential parts to understand about the USB module\:


* It needs a specific memory layout. Since it doesn't have any dedicated user-accessible memory, it requires that the user specify where things should be. There are specific valid locations for its Buffer Descriptor Table (more on that later) and the endpoint buffers. The last one bit me for several days until I figured it out.


* It has several different clock inputs and *all* of them must be enabled. Identifying the different signals is the most difficult part. After that, its not hard.


* The module only handles the electrical aspect of things. It doesn't handle sending descriptors or anything like that. The only real things it handles are the signaling levels, responding to USB packets in a valid manner, and routing data into buffers by endpoint. Other than that, its all user software.


* The module can act as both a host (USB On-the-go (OTG)) and a device. We will be exclusively focusing on using it as a device here.



In writing this, I must confess that I looked quite a lot at the Teensyduino code along with the V-USB driver code (even though V-USB is for AVR and is pure software). Without these "references", this would have been a very difficult project. Much of the structure found in the last to parts of this document reflects the Teensyduino USB driver since they did it quite efficiently and I didn't spend a lot of time coming up with a "better" way to do it, given the scope of this project. I will likely make more changes as I customize it for my end use-case.

Part 1\: The clocks
===================


The K20 family of microcontrollers utilizes a miraculous hardware module which they call the "Multipurpose Clock Generator" (hereafter called the MCG). This is a module which basically allows the microcontroller to take any clock input between a few kilohertz and several megahertz and transform it into a higher frequency clock source that the microcontroller can actually use. This is how the Teensy can have a rated speed of 96Mhz but only use a 16Mhz crystal. The configuration that this project uses is the Phase Locked Loop (PLL) from the high speed crystal source. The exact setup of this configuration is done by the `sysinit code <https://github.com/kcuzner/teensy-oscilloscope/blob/master/scope-teensy/common/sysinit.c>`__.

The PLL operates by using a divider-multiplier setup where we give it a divisor to divide the input clock frequency by and then a multiplier to multiply that result by to give us the final clock speed. After that, it heads into the System Integration Module (SIM) which distributes the clock. Since the Teensy uses a 16Mhz crystal and we need a 96Mhz system clock (the reason will become apparent shortly), we set our divisor to 4 and our multiplier to 24 (see `common.h <https://github.com/kcuzner/teensy-oscilloscope/blob/master/scope-teensy/include/common.h>`__). If the other type of Teensy 3 is being used (the one with the MK20DX128VLH5), the divisor would be 8 and the multiplier 36 to give us 72Mhz.

Every module on a K20 microcontroller has a gate on its clock. This saves power since there are many modules on the microcontroller that are not being used in any given application. Distributing the clock to each of these is expensive in terms of power and would be wasted if that module wasn't used. The SIM handles this gating in the SIM_SCGC\* registers. Before using any module, its clock gate must be enabled. If this is not done, the microcontroller will "crash" and stop executing when it tries to talk to the module registers (I think a handler for this can be specified, but I'm not sure). I had this happen once or twice while messing with this. So, the first step is to "turn on" the USB module by setting the appropriate bit in SIM_SCGC4 (per the family manual mentioned above, page 252)\:

.. code-block:: c



   SIM_SCGC4 |= SIM_SCGC4_USBOTG_MASK;

Now, the USB module is a bit different than the other modules. In addition to the module clock it needs a reference clock for USB. The USB module requires that this reference clock be at 48Mhz. There are two sources for this clock\: an internal source generated by the MCG/SIM or an external source from a pin. We will use the internal source\:

.. code-block:: c



   SIM_SOPT2 |= SIM_SOPT2_USBSRC_MASK | SIM_SOPT2_PLLFLLSEL_MASK;
   SIM_CLKDIV2 = SIM_CLKDIV2_USBDIV(1);

The first line here selects that the USB reference clock will come from an internal source. It also specifies that the internal source will be using the output from the PLL in the MCG (the other option is the FLL (frequency lock loop), which we are not using). The second line sets the divider needed to give us 48Mhz from the PLL clock. Once again there are two values\: The divider and the multiplier. The multiplier can only be 1 or 2 and the divider can be anywhere from 1 to 16. Since we have a 96Mhz clock, we simply divide by 2 (the value passed is a 1 since 0 = "divide by 1", 1 = "divide by 2", etc). If we were using the 72Mhz clock, we would first multiply by 2 before dividing by 3.

With that, the clock to the USB module has been activated and the module can now be initialized.

Part 2\: The startup sequence
=============================


The Peripheral Module Quick Reference guide mentioned earlier contains a flowchart which outlines the exact sequence needed to initialize the USB module to act as a device. I don't know if I can copy it here (yay copyright!), but it can be found on page 134, figure 15-6. There is another flowchart specifying the initialization sequence for using the module as a host.

Our startup sequence goes as follows\:

.. code-block:: c



   //1: Select clock source
   SIM_SOPT2 |= SIM_SOPT2_USBSRC_MASK | SIM_SOPT2_PLLFLLSEL_MASK; //we use MCGPLLCLK divided by USB fractional divider
   SIM_CLKDIV2 = SIM_CLKDIV2_USBDIV(1); //(USBFRAC + 0)/(USBDIV + 1) = (1 + 0)/(1 + 1) = 1/2 for 96Mhz clock

   //2: Gate USB clock
   SIM_SCGC4 |= SIM_SCGC4_USBOTG_MASK;

   //3: Software USB module reset
   USB0_USBTRC0 |= USB_USBTRC0_USBRESET_MASK;
   while (USB0_USBTRC0 & USB_USBTRC0_USBRESET_MASK);

   //4: Set BDT base registers
   USB0_BDTPAGE1 = ((uint32_t)table) >> 8;  //bits 15-9
   USB0_BDTPAGE2 = ((uint32_t)table) >> 16; //bits 23-16
   USB0_BDTPAGE3 = ((uint32_t)table) >> 24; //bits 31-24

   //5: Clear all ISR flags and enable weak pull downs
   USB0_ISTAT = 0xFF;
   USB0_ERRSTAT = 0xFF;
   USB0_OTGISTAT = 0xFF;
   USB0_USBTRC0 |= 0x40; //a hint was given that this is an undocumented interrupt bit

   //6: Enable USB reset interrupt
   USB0_CTL = USB_CTL_USBENSOFEN_MASK;
   USB0_USBCTRL = 0;

   USB0_INTEN |= USB_INTEN_USBRSTEN_MASK;
   //NVIC_SET_PRIORITY(IRQ(INT_USB0), 112);
   enable_irq(IRQ(INT_USB0));

   //7: Enable pull-up resistor on D+ (Full speed, 12Mbit/s)
   USB0_CONTROL = USB_CONTROL_DPPULLUPNONOTG_MASK;

The first two steps were covered in the last section. The next one is relatively straightfoward\: We ask the module to perform a "reset" on itself. This places the module to its initial state which allows us to configure it as needed. I don't know if the while loop is necessary since the manual says that the reset bit always reads low and it only says we must "wait two USB clock cycles". In any case, enough of a wait seems to be executed by the above code to allow it to reset properly.

The next section (4\: Set BDT base registers) requires some explanation. Since the USB module doesn't have a dedicated memory block, we have to provide it. The BDT is the "Buffer Descriptor Table" and contains 16 \* 4 entries that look like so\:

.. code-block:: c



   typedef struct {
       uint32_t desc;
       void* addr;
   } bdt_t;

"desc" is a descriptor for the buffer and "addr" is the address of the buffer. The exact bits of the "desc" are explained in the manual (p. 971, Table 41-4), but they basically specify ownership of the buffer (user program or USB module) and the USB token that generated the data in the buffer (if applicable).

Each entry in the BDT corresponds to one of 4 buffers in one of the 16 USB endpoints\: The RX even, RX odd, TX even, and TX odd. The RX and TX are pretty self explanatory...the module needs somewhere to read the data its going to send and somewhere to write the data it just received. The even and odd are a configuration that I have seen before in the PIC 18F4550 USB module\: Ping-pong buffers. While one buffer is being sent/received by the module, the other can be in use by user code reading/writing (ping). When the user code is done with its buffers, it swaps buffers, giving the usb module control over the ones it was just using (pong). This allows seamless communication between the host and the device and minimizes the need for copying data between buffers. I have declared the BDT in my code as follows\:

.. code-block:: c



   #define BDT_INDEX(endpoint, tx, odd) ((endpoint << 2) | (tx << 1) | odd)
   __attribute__ ((section(".usbdescriptortable"), used))
   static bdt_t table[(USB_N_ENDPOINTS + 1)*4]; //max endpoints is 15 + 1 control

One caveat of the BDT is that it must be aligned with a 512-byte boundary in memory. Our code above showed that only 3 bytes of the 4 byte address of "table" are passed to the module. This is because the last byte is basically the index along the table (the specification of this is found in section 41.4.3, page 970 of the manual). The #define directly above the declaration is a helper macro for referencing entries in the table for specific endpoints (this is used later in the interrupt). Now, accomplishing this boundary alignment requires some modification of the linker script. Before this, I had never had any need to modify a linker script. We basically need to create a special area of memory (in the above, it is called ".usbdescriptortable" and the attribute declaration tells the compiler to place that variable's reference inside of it) which is aligned to a 512-byte boundary in RAM. I declared mine like so\:

::



   .usbdescriptortable (NOLOAD) : {
   	. = ALIGN(512);
   	*(.usbdescriptortable*)
   } > sram


The position of this in the file is mildly important, so looking at the full `linker script <https://github.com/kcuzner/teensy-oscilloscope/blob/master/scope-teensy/common/Teensy31_flash.ld>`__ would probably be good. This particular declaration I more or less lifted from the Teensyduino linker script, with some changes to make it fit into my linker script.

Steps 5-6 set up the interrupts. There is only one USB interrupt, but there are two registers of flags. We first reset all of the flags. Interestingly, to reset a flag we write back a '1' to the particular flag bit. This has the effect of being able to set a flag register to itself to reset all of the flags since a flag bit is '1' when it is triggered. After resetting the flags, we enable the interrupt in the NVIC (Nested Vector Interrupt Controller). I won't discuss the NVIC much, but it is a fairly complex piece of hardware. It has support for lots and lots of interrupts (over 100) and separate priorities for each one. I don't have reliable code for setting interrupt priorities yet, but eventually I'll get around to messing with that. The "enable_irq()" call is a function that is provided in `arm_cm4.c <https://github.com/kcuzner/teensy-oscilloscope/blob/master/scope-teensy/common/arm_cm4.c>`__ and all that it does is enable the interrupt specified by the passed vector number. These numbers are specified in the datasheet, but we have a #define specified in the `mk20d7 header file <https://github.com/kcuzner/teensy-oscilloscope/blob/master/scope-teensy/include/MK20D7.h>`__ (warning! 12000 lines ahead) which gives us the number.

The very last step in initialization is to set the internal pullup on D+. According to the USB specification, a pullup on D- specifies a low speed device (1.2Mbit/s) and a pullup on D+ specifies a full speed device (12Mbit/s). We want to use the higher speed grade. The Kinetis USB module does not support high speed (480Mbit/s) mode.

Part 3\: The interrupt handler state machine
============================================


The USB protocol can be interpreted in the context of a state machine with each call to the interrupt being a "tick" in the machine. The interrupt handler must process all of the flags to determine what happened and where to go from there.

.. code-block:: c



   #define ENDP0_SIZE 64

   /**
    * Endpoint 0 receive buffers (2x64 bytes)
    */
   static uint8_t endp0_rx[2][ENDP0_SIZE];

   //flags for endpoint 0 transmit buffers
   static uint8_t endp0_odd, endp0_data = 0;

   /**
    * Handler functions for when a token completes
    * TODO: Determine if this structure really will work for all kinds of handlers
    *
    * I hope this looks like a dynamic jump table to the compiler
    */
   static void (*handlers[USB_N_ENDPOINTS + 2]) (uint8_t);

   void USBOTG_IRQHandler(void)
   {
       uint8_t status;
       uint8_t stat, endpoint;

       status = USB0_ISTAT;

       if (status & USB_ISTAT_USBRST_MASK)
       {
           //handle USB reset

           //initialize endpoint 0 ping-pong buffers
           USB0_CTL |= USB_CTL_ODDRST_MASK;
           endp0_odd = 0;
           table[BDT_INDEX(0, RX, EVEN)].desc = BDT_DESC(ENDP0_SIZE, 0);
           table[BDT_INDEX(0, RX, EVEN)].addr = endp0_rx[0];
           table[BDT_INDEX(0, RX, ODD)].desc = BDT_DESC(ENDP0_SIZE, 0);
           table[BDT_INDEX(0, RX, ODD)].addr = endp0_rx[1];
           table[BDT_INDEX(0, TX, EVEN)].desc = 0;
           table[BDT_INDEX(0, TX, ODD)].desc = 0;

           //initialize endpoint0 to 0x0d (41.5.23)
           //transmit, recieve, and handshake
           USB0_ENDPT0 = USB_ENDPT_EPRXEN_MASK | USB_ENDPT_EPTXEN_MASK | USB_ENDPT_EPHSHK_MASK;

           //clear all interrupts...this is a reset
           USB0_ERRSTAT = 0xff;
           USB0_ISTAT = 0xff;

           //after reset, we are address 0, per USB spec
           USB0_ADDR = 0;

           //all necessary interrupts are now active
           USB0_ERREN = 0xFF;
           USB0_INTEN = USB_INTEN_USBRSTEN_MASK | USB_INTEN_ERROREN_MASK |
               USB_INTEN_SOFTOKEN_MASK | USB_INTEN_TOKDNEEN_MASK |
               USB_INTEN_SLEEPEN_MASK | USB_INTEN_STALLEN_MASK;

           return;
       }
       if (status & USB_ISTAT_ERROR_MASK)
       {
           //handle error
           USB0_ERRSTAT = USB0_ERRSTAT;
           USB0_ISTAT = USB_ISTAT_ERROR_MASK;
       }
       if (status & USB_ISTAT_SOFTOK_MASK)
       {
           //handle start of frame token
           USB0_ISTAT = USB_ISTAT_SOFTOK_MASK;
       }
       if (status & USB_ISTAT_TOKDNE_MASK)
       {
           //handle completion of current token being processed
           stat = USB0_STAT;
           endpoint = stat >> 4;
           handlers[endpoint](stat);

           USB0_ISTAT = USB_ISTAT_TOKDNE_MASK;
       }
       if (status & USB_ISTAT_SLEEP_MASK)
       {
           //handle USB sleep
           USB0_ISTAT = USB_ISTAT_SLEEP_MASK;
       }
       if (status & USB_ISTAT_STALL_MASK)
       {
           //handle usb stall
           USB0_ISTAT = USB_ISTAT_STALL_MASK;
       }
   }

The above code will be executed whenever the IRQ for the USB module fires. This function is set up in the `crt0.S <https://github.com/kcuzner/teensy-oscilloscope/blob/master/scope-teensy/common/crt0.s>`__ file, but with a weak reference, allowing us to override it easily by simply defining a function called USBOTG_IRQHandler. We then proceed to handle all of the USB interrupt flags. If we don't handle all of the flags, the interrupt will execute again, giving us the opportunity to fully process all of them.

Reading through the code is should be obvious that I have not done much with many of the flags, including USB sleep, errors, and stall. For the purposes of this super simple driver, we really only care about USB resets and USB token decoding.

The very first interrupt that we care about which will be called when we connect the USB device to a host is the Reset. The host performs this by bringing both data lines low for a certain period of time (read the USB basics stuff for more information). When we do this, we need to reset our USB state into its initial and ready state. We do a couple things in sequence\:


#. Initialize the buffers for endpoint 0. We set the RX buffers to point to some static variables we have defined which are simply uint8_t arrays of length "ENDP0_SIZE". The TX buffers are reset to null since nothing is going to be transmitted. One thing to note is that the ODDRST bit is flipped on in the USB0_CTL register. This is very important since it "syncronizes" the USB module with our code in terms of knowing whether the even or odd buffer should be used next for transmitting. When we do ODDRST, it sets the next buffer to be used to be the even buffer. We have a "user-space" flag (endp0_odd) which we reset at the same time so that we stay in sync with the buffer that the USB module is going to use.


#. We enable endpoint 0. Specifically, we say that it can transmit, receive, and handshake. Enabled endpoints always handshake, but endpoints can either send, receive, or both. Endpoint 0 is specified as a reading and writing endpoint in the USB specification. All of the other endpoints are device-specific.


#. We clear all of the interrupts. If this is a reset we obviously won't be doing much else.


#. Set our USB address to 0. Each device on the USB bus gets an address between 0 and 127. Endpoint 0 is reserved for devices that haven't been assigned an address yet (i.e. have been reset), so that becomes our address. We will receive an address later via a command sent to endpoint 0.


#. Activate all necessary interrupts. In the previous part where we discussed the initialization sequence we only enabled the reset interrupt. After being reset, we get to enable all of the interrupts that we will need to be able to process USB events.



After a reset the USB module will begin decoding tokens. While there are a couple different types of tokens, the USB module has a single interrupt for all of them. When a token is decoded the module gives us information about what endpoint the token was for and what BDT entry should be used. This information is contained in the USB0_STAT register.

The exact method for processing these tokens is up to the individual developer. My choice for the moment was to make a dynamic jump table of sorts which stores 16 function pointers which will be called in order to process the tokens. Initially, these pointers point to dummy functions that do nothing. The code for the endpoint 0 handler will be discussed in the next section.

Our code here uses USB0_STAT to determine which endpoint the token was decoded for, finds the appropriate function pointer, and calls it with the value of USB0_STAT.

Part 4\: Token processing & descriptors
=======================================


This is one part of the driver that isn't something that must be done a certain way, but however it is done, it must accomplish the task correctly. My super-simple driver processes this in two stages\: Processing the token type and processing the token itself.

As mentioned in the previous section, I had a handler for each endpoint that would be called after a token was decoded. The handler for endpoint 0 is as follows\:

.. code-block:: c



   #define PID_OUT   0x1
   #define PID_IN    0x9
   #define PID_SOF   0x5
   #define PID_SETUP 0xd

   typedef struct {
       union {
           struct {
               uint8_t bmRequestType;
               uint8_t bRequest;
           };
           uint16_t wRequestAndType;
       };
       uint16_t wValue;
       uint16_t wIndex;
       uint16_t wLength;
   } setup_t;

   /**
    * Endpoint 0 handler
    */
   static void usb_endp0_handler(uint8_t stat)
   {
       static setup_t last_setup;

       //determine which bdt we are looking at here
       bdt_t* bdt = &table[BDT_INDEX(0, (stat & USB_STAT_TX_MASK) >> USB_STAT_TX_SHIFT, (stat & USB_STAT_ODD_MASK) >> USB_STAT_ODD_SHIFT)];

       switch (BDT_PID(bdt->desc))
       {
       case PID_SETUP:
           //extract the setup token
           last_setup = *((setup_t*)(bdt->addr));

           //we are now done with the buffer
           bdt->desc = BDT_DESC(ENDP0_SIZE, 1);

           //clear any pending IN stuff
           table[BDT_INDEX(0, TX, EVEN)].desc = 0;
           table[BDT_INDEX(0, TX, ODD)].desc = 0;
           endp0_data = 1;

           //run the setup
           usb_endp0_handle_setup(&last_setup);

           //unfreeze this endpoint
           USB0_CTL = USB_CTL_USBENSOFEN_MASK;
           break;
       case PID_IN:
           if (last_setup.wRequestAndType == 0x0500)
           {
               USB0_ADDR = last_setup.wValue;
           }
           break;
       case PID_OUT:
           //nothing to do here..just give the buffer back
           bdt->desc = BDT_DESC(ENDP0_SIZE, 1);
           break;
       case PID_SOF:
           break;
       }

       USB0_CTL = USB_CTL_USBENSOFEN_MASK;
   }


The very first step in handling a token is determining the buffer which contains the data for the token transmitted. This is done by the first statement which finds the appropriate address for the buffer in the table using the BDT_INDEX macro which simply implements the addressing form found in Figure 41-3 in the family manual.

After determining where the data received is located, we need to determine which token exactly was decoded. We only do things with four of the tokens. Right now, if a token comes through that we don't understand, we don't really do anything. My thought is that I should be initiating an endpoint stall, but I haven't seen anywhere that specifies what exactly I should do for an unrecognized token.

The main token that we care about with endpoint 0 is the SETUP token. The data attached to this token will be in the format described by setup_t, so the first step is that we dereference and cast the buffer into which the data was loaded into a setup_t. This token will be stored statically since we need to look at it again for tokens that follow, especially in the case of the IN token following the request to be assigned an address.

One part of processing a setup token that tripped me up for a while was what the next DATA state should be. The USB standard specifies that the data in a frame is either marked DATA0 or DATA1 and it alternates by frame. This information is stored in a flag that the USB module will read from the first 4 bytes of the BDT (the "desc" field). Immediately following a SETUP token, the next DATA transmitted must be a DATA1.

After this, the setup function is run (more on that next) and as a final step, the USB module is "unfrozen". Whenever a token is being processed, the USB module "freezes" so that processing can occur. While I haven't yet read enough documentation on the subject, it seems to me that this is to give the user program some time to actually handle a token before the USB module decodes another one. I'm not sure what happens if the user program takes to long, but I imagine some error flag will go off.

The guts of handling a SETUP request are as follows\:

.. code-block:: c



   typedef struct {
       uint8_t bLength;
       uint8_t bDescriptorType;
       uint16_t bcdUSB;
       uint8_t bDeviceClass;
       uint8_t bDeviceSubClass;
       uint8_t bDeviceProtocol;
       uint8_t bMaxPacketSize0;
       uint16_t idVendor;
       uint16_t idProduct;
       uint16_t bcdDevice;
       uint8_t iManufacturer;
       uint8_t iProduct;
       uint8_t iSerialNumber;
       uint8_t bNumConfigurations;
   } dev_descriptor_t;

   typedef struct {
       uint8_t bLength;
       uint8_t bDescriptorType;
       uint8_t bInterfaceNumber;
       uint8_t bAlternateSetting;
       uint8_t bNumEndpoints;
       uint8_t bInterfaceClass;
       uint8_t bInterfaceSubClass;
       uint8_t bInterfaceProtocol;
       uint8_t iInterface;
   } int_descriptor_t;

   typedef struct {
       uint8_t bLength;
       uint8_t bDescriptorType;
       uint16_t wTotalLength;
       uint8_t bNumInterfaces;
       uint8_t bConfigurationValue;
       uint8_t iConfiguration;
       uint8_t bmAttributes;
       uint8_t bMaxPower;
       int_descriptor_t interfaces[];
   } cfg_descriptor_t;

   typedef struct {
       uint16_t wValue;
       uint16_t wIndex;
       const void* addr;
       uint8_t length;
   } descriptor_entry_t;

   /**
    * Device descriptor
    * NOTE: This cannot be const because without additional attributes, it will
    * not be placed in a part of memory that the usb subsystem can access. I
    * have a suspicion that this location is somewhere in flash, but not copied
    * to RAM.
    */
   static dev_descriptor_t dev_descriptor = {
       .bLength = 18,
       .bDescriptorType = 1,
       .bcdUSB = 0x0200,
       .bDeviceClass = 0xff,
       .bDeviceSubClass = 0x0,
       .bDeviceProtocol = 0x0,
       .bMaxPacketSize0 = ENDP0_SIZE,
       .idVendor = 0x16c0, //VOTI VID/PID for use with libusb
       .idProduct = 0x05dc,
       .bcdDevice = 0x0001,
       .iManufacturer = 0,
       .iProduct = 0,
       .iSerialNumber = 0,
       .bNumConfigurations = 1
   };

   /**
    * Configuration descriptor
    * NOTE: Same thing about const applies here
    */
   static cfg_descriptor_t cfg_descriptor = {
       .bLength = 9,
       .bDescriptorType = 2,
       .wTotalLength = 18,
       .bNumInterfaces = 1,
       .bConfigurationValue = 1,
       .iConfiguration = 0,
       .bmAttributes = 0x80,
       .bMaxPower = 250,
       .interfaces = {
           {
               .bLength = 9,
               .bDescriptorType = 4,
               .bInterfaceNumber = 0,
               .bAlternateSetting = 0,
               .bNumEndpoints = 0,
               .bInterfaceClass = 0xff,
               .bInterfaceSubClass = 0x0,
               .bInterfaceProtocol = 0x0,
               .iInterface = 0
           }
       }
   };

   static const descriptor_entry_t descriptors[] = {
       { 0x0100, 0x0000, &dev_descriptor, sizeof(dev_descriptor) },
       { 0x0200, 0x0000, &cfg_descriptor, 18 },
       { 0x0000, 0x0000, NULL, 0 }
   };

   static void usb_endp0_transmit(const void* data, uint8_t length)
   {
       table[BDT_INDEX(0, TX, endp0_odd)].addr = (void *)data;
       table[BDT_INDEX(0, TX, endp0_odd)].desc = BDT_DESC(length, endp0_data);
       //toggle the odd and data bits
       endp0_odd ^= 1;
       endp0_data ^= 1;
   }

   /**
    * Endpoint 0 setup handler
    */
   static void usb_endp0_handle_setup(setup_t* packet)
   {
       const descriptor_entry_t* entry;
       const uint8_t* data = NULL;
       uint8_t data_length = 0;


       switch(packet->wRequestAndType)
       {
       case 0x0500: //set address (wait for IN packet)
           break;
       case 0x0900: //set configuration
           //we only have one configuration at this time
           break;
       case 0x0680: //get descriptor
       case 0x0681:
           for (entry = descriptors; 1; entry++)
           {
               if (entry->addr == NULL)
                   break;

               if (packet->wValue == entry->wValue && packet->wIndex == entry->wIndex)
               {
                   //this is the descriptor to send
                   data = entry->addr;
                   data_length = entry->length;
                   goto send;
               }
           }
           goto stall;
           break;
       default:
           goto stall;
       }

       //if we are sent here, we need to send some data
       send:
           if (data_length > packet->wLength)
               data_length = packet->wLength;
           usb_endp0_transmit(data, data_length);
           return;

       //if we make it here, we are not able to send data and have stalled
       stall:
           USB0_ENDPT0 = USB_ENDPT_EPSTALL_MASK | USB_ENDPT_EPRXEN_MASK | USB_ENDPT_EPTXEN_MASK | USB_ENDPT_EPHSHK_MASK;
   }


This is the part that took me the longest once I managed to get the module talking. Handling of SETUP tokens on endpoint 0 must be done in a rather exact fashion and the slightest mistake gives some `very cryptic errors <http://stackoverflow.com/questions/27287610/linux-device-descriptor-read-64-error-18>`__.

This is a very very very minimalistic setup token handler and *is not by any means complete*. It does only what is necessary to get the computer to see the device successfully read its descriptors. There is no functionality for actually doing things with the USB device. Most of the space is devoted to actually returning the various descriptors. In this example, the descriptor is for a device with a single configuration and a single interface which uses no additional endpoints. In a real device, this would almost certainly not be the case (unless one uses V-USB...this is how V-USB sets up their device if no other endpoints are compiled in).

The SETUP packet comes with a "request" and a "type". We process these as one word for simplicity. The above shows only the necessary commands to actually get this thing to connect to a Linux machine running the standard USB drivers that come with the kernel. I have not tested it on Windows and it may require some modification to work since it doesn't implement all of the necessary functionality. A description of the functionality follows\:


* Set address (0x0500)\: This is a very simple command. All it does is wait for the next IN token. Upon receipt of this token, the address is considered "committed" and the USB module is told of its new address (see the endpoint 0 handler function above (not the setup handler)).


* Set configuration (0x0900)\: This command can be complex, but I have stripped it down for the purposes of this example. Normally, during this command the USB module would be set up with all the requisite BDT entries for the endpoints described by the selected configuration. Since we only have one possible configuration and it doesn't use any additional endpoints, we basically do nothing. Once I start added other endpoints to this, all of the setup for those endpoints will go in here. This is the equivalent of the RESET handler for non-zero endpoints in terms of the operations that occur. If the Set Interface command was implemented, it would have similar functionality. More about this command can be read in the referenced USB basics website.


* Get descriptor (0x0680, 0x0681)\: In reality, this is two commands\: Get descriptor and get interface. However, due to the structure we have chosen in storing the descriptors, these two commands can be merged. This is the most complex part of this particular driver and is influenced heavily by the way things are done with the Teensyduino driver since I thought they had a very efficient pattern. Basically, it uses the wIndex and wValue to find a pointer to some data to return, whether that be the device descriptor, the configuration descriptor, a string, or something else. In our case, we have only the device descriptor and the configuration descriptor. Adding a string would be trivial, however, and the exact wIndex and wValue combination for that is described in the USB basics. The wIndex for strings matches with any of the several i\* (iManufacturer, iProduct, etc) which may be specified.


* default\: When an unrecognized command is received, we enter a stall. This is basically the USB way of saying "uhh...I don't know what to do here" and requires the host to un-stall the endpoint before it can continue. From what I gather, there isn't really much the user code has to do other than declare that a stall has occurred. The USB module seems to take care of the rest of that.



After handling a command and determining that it isn't a stall, the transmission is set up. At the moment, I only have transmission set up for a maximum of 64 bytes. In reality, this is limited by the wLength transmitted with the setup packet (note the if statement before the call to usb_endp0_transmit), but as far as I have seen this is generally the same as the length of the endpoint (I could be very wrong here...so watch out for that one). However, it would be fairly straightfoward to allow it to transmit more bytes\: Upon receipt of an IN token, just check if we have reached the end of what we are supposed to transmit. If not, point the next TX buffer to the correct starting point and subtract the endpoint size from the remaining length until we have transmitted all of the bytes. Although the endpoint size is 64 bytes, it is easy to transmit much more than that; it just takes multiple IN requests. The data length is given by the descriptors, so the host can determine when to stop sending IN requests.

During transmission, both the even and data flags are toggled. This ensures that we are always using the correct TX buffer (even/odd) and the DATA flag transmitted is valid.

The descriptors are the one part that can't really be screwed up here. Screwing up the descriptors causes interesting errors when the host tries to communicate. I did not like how the "reference" usb drivers I looked at generally defined descriptors\: They used a char array. This works very well for the case where there are a variable number of entries in the descriptor, but for my purposes I decided to use named structs so that I could match the values I had specified on my device to values I read from the host machine without resorting to counting bytes in the array. It's simply for easier reading and doesn't really give much more than that. It may even be more error prone because I am relying on the compiler packing the struct into memory in the correct order for transmission and in later versions I may end up using the char array method.

I won't delve into a long and drawn out description of what the USB descriptor has in it, but I will give a few points\:


* In Linux, the device descriptor is requested first and then the configuration descriptor after that. They are two separate commands, hence the two separate descriptor entries in my descriptor table.


* The device descriptor must NOT be "const". For my compiler at least, this causes it to be placed into flash which, while a perfectly valid memory address that in general can be read, is inaccessible to the USB module. I spent a long time banging my head on this one saying "but it should work! why doesn't it work???" Moral of the story\: Anything that is pointed to by a BDT entry (transmit buffers, receive buffers) must be located in main RAM, not in the flash. It must not be const.


* A device must have at least one configuration. Linux, at least, didn't seem to like it very much when there were zero configurations and would put lots of errors into my log.


* The configuration needs to have at least one interface. Specifying no interfaces caused the same problems as not specifying any configurations.


* The configuration indices (bConfigurationValue) are 1-based and the interface indices (bInterfaceNumber) are zero based. I haven't fooled around with these enough to test the veracity of this claim fully, but it was the only configuration that I managed to get things working in.


* The length values are very important. If these are not correct, the host will have some serious troubles reading the descriptors. I spend a while troubleshooting these. The main one to make sure of is the wTotalLength value in the configuration descriptor. Most of the others are pretty much always going to be the same.




Where to go from here
=====================


The driver I have implemented leaves much to be desired. This isn't meant to be a fully featured driver. Instead, its meant to be something of an introduction to getting the USB module to work on the bare metal without the support of some external dependency. A few things that would definitely need to be implemented are\:


* The full set of commands for the endpoint 0 SETUP token processing


* A more expansive configuration that allows for having some bulk endpoints for sending data. The 64-byte limitation of packet size for endpoint 0 can cause some issues when attempting to actually utilize the full 12Mbit/s bandwidth. The USB protocol does actually add overhead and the less times that a token has to be invoked, the better.


* Strings in the configuration. Right now, the configuration is essentially "blank" because it uses a shared VID/PID and doesn't specify a manufacturer, product, or serial number. It would be rather hard to identify this device using libusb on a system with multiple devices using that VID/PID combination.


* Real error handling. Right now, the interrupt basically ignores the errors. In a real application, these would need to be handled.


* A better structure. I am not a real fan of how I have structured this, but my idea was to make it "expandable" without needing to recompile usb.c every time a change was made. It doesn't achieve that yet, but in future iterations I hope to have a relatively portable usb driver module that I can port to other projects without modification, placing the other device-specific things into another, mimimalistic, file.




Conclusion
==========


I can only hope that this discussion has been helpful. I spent a long time reading documentation, writing code, smashing my keyboard, and figuring things out and I would like to see that someone else could benefit from this. I hope as I learn more about using the modules on my Teensy that I will become more competent in understanding how many of the systems I rely on on a daily basis function.

The code I have included above isn't always complete, so I would definitely recommend actually reading the code in the repository referenced at the beginning of this article.

If there are any mistakes in the above, please let me know in the comments or shoot me an email.