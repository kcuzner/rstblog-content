During my `LED Wristwatch project <http://kevincuzner.com/2017/04/18/the-led-wristwatch-a-more-or-less-completed-project/>`__, I decided early on that I wanted to do something different with the way my USB stuff was implemented. In the past, I have almost exclusively used libusb to talk to my devices in terms of raw bulk packets or raw setup requests. While this is ok, it isn't quite as easy to do once you cross out of the fruited plains of Linux-land into the barren desert of Windows. This project instead made the watch identify itself (enumerate) as a USB Human Interface Device (HID).

What I would like to do in this post is a step-by-step tutorial for modifying a USB device to enumerate as a human interface device. I'll start with an overview of HID, then move on to modifying the USB descriptors and setting up your device endpoints so that it sends reports, followed by a few notes on writing host software for Windows and Linux that communicates to devices using raw reports. With a little bit of work, you should be able to replace many things done exclusively with libusb with a cross-platform system that requires no drivers.
**Example code for this post can be found here\:**


`**https\://github.com/kcuzner/led-watch** <https://github.com/kcuzner/led-watch>`__


One thing to note is that since I'm using my LED Watch as an example, I'm going to be extending using my API, which I describe a little bit `here <http://kevincuzner.com/2018/01/29/bare-metal-stm32-writing-a-usb-driver/>`__. The main source code files for this can be found in common/src/usb.c and common/src/usb_hid.c.

Contents
========



.. rstblog-break::


`Overview of HID <overview>`__
`Reports <overview-reports>`__


`Report Descriptors <overview-report-descriptors>`__


`Step 1\: Extending Setup Requests <step-1>`__

`Step 2\: Descriptors <step-2>`__
`Modifying the configuration descriptor <step-2-configuration>`__


`Writing a report descriptor <step-2-report-descriptors>`__


`Step 3\: Sending IN Reports <step-3>`__

`Step 4\: Sending OUT Reports <step-4>`__

`Host software <host>`__
`Cross-platform C/C++ <host-c>`__


`Python (Linux) <host-python>`__


`C# (Windows) <host-c-sharp>`__


`Conclusion <conclusion>`__

.. _overview:

Overview of HID
===============


Before doing anything HID, you need two pieces of documentation\:


* The USB HID Specification\: `http\://www.usb.org/developers/hidpage/HID1_11.pdf <http://www.usb.org/developers/hidpage/HID1_11.pdf>`__


* The USB HID Usage Tables documentation\: `http\://www.usb.org/developers/hidpage/Hut1_12v2.pdf <http://www.usb.org/developers/hidpage/Hut1_12v2.pdf>`__



This is one of the few times I have read an industry specification and it hasn't required an almost lawyer-style analysis to comprehend. It is surprisingly readable and I highly recommend at least scrolling through it somewhat since it makes a halfway decent reference.

.. _overview-reports:

Reports
-------


HID communicates by way of "Reports". The basic idea is that a "Report" tells the host something going on with the human interface device, be it a mouse moment, a keystroke, or whatever. There are not only reports going to the host, but also those that go from the host to the device. These reports can do things like turn on the caps lock LED and so forth. The reports are named as follows\:


* IN Reports\: These are reports IN to the host from the device.


* OUT Reports\: These are reports OUT from the host to the device.



All the report naming is quite host-centric as you can see. Now, when a device declares itself as a human interface device, it has to implement the following endpoints\:


* The control endpoint (endpoint 0). Every device needs this anyway, so its hardly worth mentioning.


* An IN endpoint. This endpoint must be an INTERRUPT endpoint. Interrupt endpoints are polled every so often by the host at the rate specified in the endpoint descriptor. These endpoints have guaranteed bandwidth, but the sacrifice is that the guaranteed bandwidth is quite small. Contrast this to bulk endpoints which don't have guaranteed bandwidth, but can transmit as much data as they would like. The polling rate can be set such that the host is able to query the device for reports (remember that all USB communication is initiated by the host) fast enough so that lag can be avoided.


* Optionally, an OUT endpoint. This endpoint must also be an INTERRUPT endpoint. The OUT Interrupt endpoint is a strange beast. While you have to specify a polling rate, this does not mean that the host is going to initiate a transfer to the endpoint at that rate. Instead, it just reserves the bandwidth with the host so that it knows that there is an endpoint that it can send data to in a timely fashion. Hosts will only initiate an OUT Report transfer on an as-needed basis, but the specification guarantees there will be bandwidth to do it since it is an interrupt endpoint.



So in total, a HID has either one or two extra endpoints beyond the basic control endpoint. These endpoints are used to either send IN Reports of events happening to the device to the host or receive OUT Reports from the host commanding the device to do things.

.. _overview-report-descriptors:

Report Descriptors
------------------


One of the key features, and a major motivation behind writing HID devices, is that most operating systems require no drivers for these devices to work. For most other USB devices, the operating system requires a driver which interacts with the device on a low level and provides an interface either back into userspace or kernelspace which can be used by regular programs to interact with the device. However, for human interface devices the OS actually provides a driver which translates whatever reports a custom device may send back to the host into an API usable by programs. For example, if you plug a USB joystick or gamepad which enumerates as a HID into the computer, other programs can call OS methods that allow enumerating the analog joysticks and pushbuttons that the gamepad provides, without needing to use a manufacturer-specific driver to translate the reports into input actions.

This is possible by the use of "Report Descriptors". These serve as a way for the device to self-describe the format of the reports it is going to send back. A joystick from manufacturer A might send four analog values followed by 16 button values, but a joystick from manufacturer B may instead send 16 button values followed by only two analog values. The OS driver makes sense of the report formatting by reading the report descriptors returned by the device when it enumerates. Report descriptors are represented as a series of tokens which are parsed one after another to build up the description of the report. Tokens that may appear include\:


* **Begin/End Collection Tokens.** All items described by the report are placed inside collections. These collections can be nested.


* **Description tokens for the next report field.** These include the number of bits the field consumes, the meaning of the field (called a "Usage"), and how many copies of the field there are going to be. In addition, the report itself can be described here including an "ID" that can be used to distinguish multiple reports.


* **Tokens denoting the type and position of the field. **After a field is described, it is "emitted" by using an IN or OUT token. An IN token tells the OS the field will appear in an IN report and an OUT token tells the OS that the field will appear in an OUT report.



Building cross-platform report descriptors is one of the more challenging parts of creating a human interface device. Some operating systems, such as Linux, are extremely permissive and will still enumerate the device with a badly formatted report. Other operating systems, such as Windows, are extremely strict in terms of what they accept and will not enumerate your device if the report descriptor doesn't conform to its exacting standards (you'll get the dreaded "Device failed to start" error in Device Manager).

.. _step-1:

Step 1\:Extending Setup Requests
================================


The general USB specification defines a setup request command GET_DESCRIPTOR. The spec defines the high byte of wValue to be the "descriptor type". The HID specification defines the following class-specific descriptors\:


* 0x21\: HID


* 0x22\: Report


* 0x23\: Physical Descriptor



In general, hosts won't issue requests for descriptor type 0x21, but type 0x22 will be seen as part of the enumeration process. You'll need to extend your GET_DESCRIPTOR request so that it responds to 0x22 descriptor requests at index 0 and returns your HID descriptor (or even at multiple indexes if you have multiple HID descriptors).

In my LED watch with its API, I just have a read-only table of descriptors that has the expected wValue, wIndex, and a pointer to the data. My descriptor table looks like so\:

.. code-block:: {lang}



   const USBDescriptorEntry usb_descriptors[] = {
       { 0x0100, 0x0000, sizeof(dev_descriptor), dev_descriptor },
       { 0x0200, 0x0000, sizeof(cfg_descriptor), cfg_descriptor },
       { 0x0300, 0x0000, sizeof(lang_descriptor), lang_descriptor },
       { 0x0301, 0x0409, sizeof(manuf_descriptor), manuf_descriptor },
       { 0x0302, 0x0409, sizeof(product_descriptor), product_descriptor },
       { 0x2200, 0x0000, sizeof(hid_report_descriptor), hid_report_descriptor }, //new descriptor for HID
       { 0x0000, 0x0000, 0x00, NULL }
   };

Now, in addition to extending GET_DESCRIPTOR, the HID specification requires one new setup request be supported\: Class-specific request 0x01 (bRequest = 0x01, bmRequestType = 0x01), known as GET_REPORT. This provides a control-request way to get HID reports. Now, I've actually found that both Windows and Linux don't mind if this isn't implemented. However, it may be good to implement anyway. It has the following arguments\:


* wValue\: Report Type (IN, OUT, FEATURE) in the high byte, report ID in the low byte.


* wIndex\: Interface index. If you have multiple HID interfaces (i.e. you've made a composite device), then this will specify which interface the request is for.



In my LED Watch, the USB setup request handler will call hook_usb_handle_setup_request when it receives a request that the base driver can't handle. Here is my implementation\:

.. code-block:: {lang}



   /**
    * Implementation of hook_usb_handle_setup_request which implements HID class
    * requests
    */
   USBControlResult hook_usb_handle_setup_request(USBSetupPacket const *setup, USBTransferData *nextTransfer)
   {
       uint8_t *report_ptr;
       uint16_t report_len;
       switch (setup->wRequestAndType)
       {
           case USB_REQ(0x01, USB_REQ_DIR_IN | USB_REQ_TYPE_CLS | USB_REQ_RCP_IFACE):
               //Get report request
   ...determine which report is needed and get a pointer to it...
               nextTransfer->addr = report_ptr;
               nextTransfer->len = report_len;
               return USB_CTL_OK;
       }
       return USB_CTL_STALL;
   }


And with that, your device is now prepared to handle the host setup requests. The next step is going to be actually writing the descriptors.

.. _step-2:

Step 2\: Descriptors
====================



.. _step-2-configuration:

Modifying the configuration descriptor
--------------------------------------


Every USB device has a configuration descriptor. In reality, what I'm calling the "configuration descriptor" here is actually a concatenated list of everything that follows the configuration descriptor. Here are the parts of a configuration descriptor, as they appear in order\:


* The configuration descriptor itself (Descriptor with bDescriptorType = 2)


* Total length of everything to follow (wTotalLength)


* Number of interfaces (bNumInterfaces)


* Configuration value (bConfigurationValue)


* Configuration index (iConfiguration)


* Attributes and power


* First interface descriptor (bDescriptorType = 4)
* Zero or more endpoint descriptors (bDescriptorType = 5)

* Optionally more interface descriptors (bDescriptorType = 4)



This is usually just a byte array. When making a device into a HID, the descriptor needs to change. Two new descriptor types are introduced by the HID class specification that we will use\: 0x21 (HID descriptor) and 0x22 (Report Descriptor). The HID Descriptor declares the version of the HID spec that the device follows along with a country code. It also contains one or more report descriptors. The report descriptors contain only a length of a report (along with the bDescriptorType). These will be used later when the host makes a special HID setup request to load these descriptors.

The configuration descriptor of something that has an HID interface looks like so (changes in bold, see HID specification section 7.1, very first paragraph)\:


* The configuration descriptor itself (Descriptor with bDescriptorType = 2)


* Total length of everything to follow (**wTotalLength**)


* Number of interfaces (bNumInterfaces)


* Configuration value (bConfigurationValue)
* Configuration index (iConfiguration)

* Attributes and power


* First interface descriptor (bDescriptorType = 4, **bInterfaceClass = 0x3 (HID), bInterfaceSubclass = 0 (no boot), bInterfaceProtocol = 0**)
* **HID Descriptor (bDescriptorType = 0x21)**
  * **Report Descriptor (bDescriptorType = 0x22)**

  * \ :raw-html:`<del>`\ Zero or more endpoint descriptors (bDescriptorType = 5)\ :raw-html:`</del>`\ 


  * **Endpoint descriptor (bDescriptorType = 5, interrupt endpoint, IN)**
  * *Note that wMaxPacketSize will be restricted to 8 bytes on Low-speed devices, 64 bytes on Full-speed devices. This is due to it being an interrupt endpoint.*

  * **(Optional) Endpoint descriptor (bDescriptorType = 5, interrupt endpoint, OUT)**
  * *Same story as the IN endpoint with wMaxPacketSize.*

* Optionally more interface descriptors (bDescriptorType = 4)



In addition, the device descriptor must change so that **bDeviceClass = 0** to signal that the device's class is defined by its interfaces.

If you want to implement multiple separate HID devices in the same device (making a composite HID device), it is as simple as adding more interfaces. The only restriction is that the endpoint addresses need to be unique so that the host can talk to a specific HID implementation. This is one way to build things like mouse/keyboard combo devices.

Here is an example of a completed configuration descriptor that declares a single HID interface with both IN and OUT endpoints\:

.. code-block:: {lang}



   /**
    * Configuration descriptor
    */
   static const uint8_t cfg_descriptor[] = {
       9, //bLength
       2, //bDescriptorType
       9 + 9 + 9 + 7 + 7, 0x00, //wTotalLength
       1, //bNumInterfaces
       1, //bConfigurationValue
       0, //iConfiguration
       0x80, //bmAttributes
       250, //bMaxPower
       /* INTERFACE 0 BEGIN */
       9, //bLength
       4, //bDescriptorType
       0, //bInterfaceNumber
       0, //bAlternateSetting
       2, //bNumEndpoints
       0x03, //bInterfaceClass (HID)
       0x00, //bInterfaceSubClass (0: no boot)
       0x00, //bInterfaceProtocol (0: none)
       0, //iInterface
           /* HID Descriptor */
           9, //bLength
           0x21, //bDescriptorType (HID)
           0x11, 0x01, //bcdHID
           0x00, //bCountryCode
           1, //bNumDescriptors
           0x22, //bDescriptorType (Report)
           sizeof(hid_report_descriptor), 0x00,
           /* INTERFACE 0, ENDPOINT 1 BEGIN */
           7, //bLength
           5, //bDescriptorType
           0x81, //bEndpointAddress (endpoint 1 IN)
           0x03, //bmAttributes, interrupt endpoint
           USB_HID_ENDPOINT_SIZE, 0x00, //wMaxPacketSize,
           10, //bInterval (10 frames)
           /* INTERFACE 0, ENDPOINT 1 END */
           /* INTERFACE 0, ENDPOINT 2 BEGIN */
           7, //bLength
           5, //bDescriptorType
           0x02, //bEndpointAddress (endpoint 2 OUT)
           0x03, //bmAttributes, interrupt endpoint
           USB_HID_ENDPOINT_SIZE, 0x00, //wMaxPacketSize
           10, //bInterval (10 frames)
           /* INTERFACE 0, ENDPOINT 2 END */
       /* INTERFACE 0 END */
   };



One thing to note here\: The HID Descriptor declares how many Report Descriptors will appear in relation to the USB device (bNumDescriptors + (bDescriptorType + wDescriptorLength)\*<number of descriptors>). In general, HID devices don't usually need more than one report descriptor since you can describe multiple reports in a single descriptor. However, there's nothing stopping you from implementing multiple report descriptors.

.. _step-2-report-descriptors:

Writing a report descriptor
---------------------------


The HID class describes a new class-specific setup request which can be used to read Report Descriptors. When this setup request is sent by the host, the device should return the Report Descriptor requested. Report Descriptors are fairly unique compared to the other descriptors used in USB. One major difference is that they read more like an XML document than a key-value array. There is no set order and no set length. In fact, the only way the host knows how many bytes to read for this setup request is from the HID Descriptor found inside the Configuration Descriptor that says how many bytes to expect. With other descriptors, the host usually reads the descriptor twice\: Once only reading the first 9 bytes to get the wTotalLength and a second time reading the wTotalLength. With the Report Descriptor the host will read exactly as many bytes as were declared by the HID Descriptor. This of course means that if that length value is not set up correctly, then the host will get a truncated report descriptor and will have a hard time parsing it.

The most difficult part about writing report descriptors is that they are not easy to debug. On Windows, the device manager will simply say "Device failed to start". On Linux, a similar error appears in the system log. You'll get no help figure out what went wrong. Here are my tips to writing report descriptors\:


* **Start off small, then grow. **Write a minimal report descriptor and extend it from there, one token at a time. This way you can know which token has caused you to have problems.


* **Double check that you have declared a Usage Page.** On Windows, it will complain if no Usage Page has been set and will not parse your descriptor.


* **Double check that you declare a Usage before each field token.** On Windows (and possibly Linux, but I can't remember), it won't parse your descriptor.


* **Indent your descriptor as you write it.** It's really like an XML document with nesting and all. It is very easy to lose track of where you are in the nesting.


* **Write some helper macros to translate HID tokens into bytes.** There are several flags that have to be set for the start of every token and it is far easier if you make the compiler do this for you.


* **Remember that IN is *towards* the host and OUT is *away* from the host.** In USB, IN and OUT are host-centric. When you defined an INPUT field, it goes in your IN descriptor and represents a field your device sends to the host. When you define an OUTPUT field, it goes in your OUT descriptor and represents a field that the host can send back to the device.



The first thing I'm going to describe are my helper macros, actually\:

.. code-block:: {lang}



   /**
    * HID Descriptor Helpers
    */
   #define HID_SHORT_ZERO(TAGTYPE) (TAGTYPE | 0)
   #define HID_SHORT_MANY(TAGTYPE, ...) (TAGTYPE | (NUMARGS(__VA_ARGS__) & 0x3)), __VA_ARGS__
   #define GET_HID_SHORT(_1, _2, _3, _4, _5, NAME, ...) NAME
   #define HID_SHORT(...) GET_HID_SHORT(__VA_ARGS__, HID_SHORT_MANY, HID_SHORT_MANY, HID_SHORT_MANY, HID_SHORT_MANY, HID_SHORT_ZERO)(__VA_ARGS__)

All HID tokens have a common format. They are a sequence of bytes with the first byte describing how many of the bytes following are part of the token, up to five bytes total. The first byte has the following format\:


* Bits 7-2\: Tag Type


* Bytes 1-0\: Number of bytes to follow (0-3)



These helper macros are a little complex, and to be honest I based them of something I found on stackoverflow somewhere. I'm not even sure if they work with any compiler other than GCC. Here's how they work\:


* The HID_SHORT macro takes in a variable number of arguments (the ... in the argument list, also known as variadic arguments). This is accessed by __VA_ARGS__. It in turn calls the GET_HID_SHORT macro, pasting in the variadic arguments first. The arguments following are used to select which macro to call\: HID_SHORT_ZERO or HID_SHORT_MANY.


* The GET_HID_SHORT macro takes in 6 arguments before receiving variadic arguments. This is where some of the magic happens when this is combined with HID_SHORT\:
* If 1 argument was passed to HID_SHORT, then GET_HID_SHORT is called with 6 arguments\: "GET_HID_SHORT(<argument>, HID_SHORT_MANY, HID_SHORT_MANY, HID_SHORT_MANY, HID_SHORT_MANY, HID_SHORT_ZERO)". We don't use _1 through _5 and the NAME argument gets "HID_SHORT_ZERO".


  * If 2 arguments are passed to HID_SHORT, then GET_HID_SHORT is called with 7 arguments\: "GET_HID_SHORT(<argument 0>, <argument 1>, HID_SHORT_MANY, HID_SHORT_MANY, HID_SHORT_MANY, HID_SHORT_MANY, HID_SHORT_ZERO)". Again, _1 through _5 are discarded. However, this time the NAME argument gets "HID_SHORT_MANY" since the HID_SHORT_ZERO in argument position 7 is inside the variadic arguments for GET_HID_SHORT (and is therefore discarded).


  * So on and so forth for up to 5 arguments.

* HID_SHORT_ZERO takes in exactly one argument and ors it with 0. Basically it's just a No-Op.
* Note that HID_SHORT calls the result of GET_HID_SHORT with __VA_ARGS__. When exactly one argument is passed, GET_HID_SHORT evaluates to "HID_SHORT_ZERO" and that macro is in turn called with the single argument.

* HID_SHORT_MANY takes in one "tag" argument and many following arguments. When HID_SHORT_MANY is called, it will take the first argument and OR it with the number of arguments in __VA_ARGS__, masking it off to the correct number of bits for an HID token.
* In the case where more than 1 argument is passed to HID_SHORT, GET_HID_SHORT evaluates to "HID_SHORT_MANY" and that macro is in turn called with all of the arguments passed.


Here's some examples of what happens when this is evaluated\:


* HID_SHORT(0xC0)\: This evaluates to "(0x0c | 0)".


* HID_SHORT(0x04, 0x00, 0xFF)\: This evaluates to "(0x04 | 2), 0x00, 0xFF".



With this macro we can define our HID tokens without having to worry about making a mistake encoding the length in the first byte.

I'm not going to go through the token types exhaustively since those are in the spec, but here's a couple common ones\:


* 0x08\: USAGE. Every field in a report has a "Usage" associated with it. This token is followed by one or two more bytes and indicates to the host how the field is meant to be used. For example, there is a usage called "Wheel" and another called "D-pad up".


* 0x04\: USAGE_PAGE. This token is usually followed by one or two more bytes which encode the Usage Page that the next Usage token is using, LSB first. There are so many usages that they are categorized into pages. The full list is found in the `HID Usage Tables specification <http://www.usb.org/developers/hidpage/Hut1_12v2.pdf>`__.


* 0xA0\: COLLECTION. All fields are enclosed in a collection. In addition, collections can be nested in collections. This token followed by one byte which describes the type of collection.


* 0x80\: INPUT. This token is followed by one byte and creates a new field in an IN report. The byte contains flags describing what sort of field it is (constant, array, etc). Read the HID spec, section 6.2.2.4 for a description of these flags.


* 0x90\: OUTPUT\: This token is followed by one byte and creates a new field in an OUT report. Same story as INPUT with the byte following.



Since the easiest way to get started with these is with some examples, let's start off with a report descriptor that describes two reports\: an IN report that is 64 bytes long and an OUT report that is 64 bytes long. The 64 bytes in both of these reports have a "vendor defined" usage and thus can be used for general buffers. The OS won't try to hook them into any input system.

.. code-block:: {lang}



   static const uint8_t hid_report_descriptor[] = {
       HID_SHORT(0x04, 0x00, 0xFF), //USAGE_PAGE (Vendor Defined)
       HID_SHORT(0x08, 0x01), //USAGE (Vendor 1)
       HID_SHORT(0xa0, 0x01), //COLLECTION (Application)
       HID_SHORT(0x08, 0x01), //  USAGE (Vendor 1)
       HID_SHORT(0x14, 0x00), //  LOGICAL_MINIMUM (0)
       HID_SHORT(0x24, 0xFF, 0x00), //LOGICAL_MAXIMUM (0x00FF)
       HID_SHORT(0x74, 0x08), //  REPORT_SIZE (8)
       HID_SHORT(0x94, 64),   //  REPORT_COUNT(64)
       HID_SHORT(0x80, 0x02), //  INPUT (Data, Var, Abs)
       HID_SHORT(0x08, 0x01), //  USAGE (Vendor 1)
       HID_SHORT(0x90, 0x02), //  OUTPUT (Data, Var, Abs)
       HID_SHORT(0xc0),       //END_COLLECTION
   };

Let's dig into this report descriptor a little\:


* Right off the bat, we change the USAGE_PAGE to page 0xFF00, which is "Vendor Defined". All the usages on this page are "Vendor <number>".


* Before we start our Application collection, we set the USAGE to 0x01, or "Vendor 1". When the COLLECTION token follows, the HID descriptor parser will see that this collection of fields is meant to be used for "Vendor 1".
* Note that in general, Usage 0x00 means "Undefined" on most pages, meaning that the usage has not been defined (not that 0x00 is undefined as a usage). When doing something with vendor defined usages, start at 1.

* After starting the collection, we have another USAGE token. It turns out that the USAGE token is a "Local Item". Within HID descriptors, there's a concept of scopes. Items can be "Main", "Global", or "Local". Main items are things like the INPUT token, the OUTPUT token, and COLLECTION tokens. Local items' scope ends at the next Main item. Since the previous USAGE token was followed by a COLLECTION, we have to add another USAGE token.


* The LOGICAL_MINIMUM token is a "Global Item". This means that the value it sets will apply to all fields until we see another LOGICAL_MINIMUM. The meaning of this token is to set the minimum value that could be seen in the fields that follow. **Important\: The value of this token is signed!**


* The LOGICAL_MAXIMUM token is also a "Global Item" and sets the maximum value that could be seen in the fields that follow. Since we are sending raw bytes, the maximum value for this is 255. However, since **the value of this token is signed**, we have to represent it with 0x00FF rather than just 0xFF. If we left it at 0xFF, then it would actually be -127, which is less than the LOGICAL_MINIMUM (previously set to zero). Some OS's may choke on the report descriptor in this case.


* INPUT and OUTPUT tokens have a "Relative" or "Absolute" flag. Think of Absolute as sliding an audio fader and the field returning a value between 0% and 100%, depending on the position of the fader. Relative, on the other hand, is more like a rotary encoder. If it didn't move, the value is 0. If it turned one direction, the value could be 5 (or any value >0). If it turned the other direction, the value could be -10 (or any value <0).


* The REPORT_COUNT and REPORT_SIZE tokens are Global Items and define two things\:
* Count\: The number of fields that the next INPUT or OUTPUT token generates (that's right, you can define multiple fields with just one token).


  * Size\: The size in bits of each field. This can be any number, so you can have fields that have weird widths, like "3". **One caveat\: The total number of bits in a report *must* be divisible by eight.** Since reports are transferred by byte, this only makes sense. I know that at least with Windows, it will choke on your report descriptor if it has a number of bits not divisible by eight.

* Note that I have no real separation between the INPUT and OUTPUT tokens. This is something interesting about report descriptors\: You are actually defining two reports at the same time. When you have an INPUT token, you add a field to the input report that you're defining. When you have an OUTPUT token, the same thing happens except it goes to the output report. This means that you can interleave INPUT and OUTPUT tokens if you feel like it. Or you can define all the fields the IN report and then all the fields in the OUT report. Whatever makes the most sense with your application. They will both result in the same two reports. If at the end of the report descriptor no OUTPUT tokens appeared, then your OUT report is empty and won't be expected. Same deal if your report descriptor has no INPUT tokens.



Now let's move on to another kind of report descriptor\: Defining multiple reports in one descriptor. This requires some discussion of "Report IDs".

When a REPORT_ID token appears in a report descriptor, it changes how reports are sent and received by the host and device\:


* All reports are now exactly one byte longer. If you declare a report with eight 8-bit fields, you will transfer 9 bytes of data.


* The first byte of a report now contains a "report id" and the remainder of the bytes actually have the report content. The index of all your fields is shifted by 8 bits.



Here's an example descriptor that declares *three* reports\:

.. code-block:: {lang}



   static const USB_DATA_ALIGN uint8_t hid_report_descriptor[] = {
       HID_SHORT(0x04, 0x01), //USAGE_PAGE (Generic Desktop)
       HID_SHORT(0x08, 0x05), //USAGE (Game Pad)
       HID_SHORT(0xa0, 0x01), //COLLECTION (Application)
       HID_SHORT(0x84, 0x01), //  REPORT_ID (1)
       HID_SHORT(0x14, 0x00), //  LOGICAL_MINIMUM (0)
       HID_SHORT(0x24, 0x01), //  LOGICAL_MAXIMUM (1)
       HID_SHORT(0x74, 0x01), //  REPORT_SIZE (1)
       HID_SHORT(0x94, 4),    //  REPORT_COUNT(4)
       HID_SHORT(0x18, 0x90), //  USAGE_MINIMUM (D-pad up)
       HID_SHORT(0x28, 0x93), //  USAGE_MAXIMUM (D-pad left)
       HID_SHORT(0x80, 0x02), //  INPUT (Data, Var, Abs)
       HID_SHORT(0x80, 0x03), //  INPUT (Const, Var, Abs)
       HID_SHORT(0x04, 0x08), //  USAGE_PAGE (LED)
       HID_SHORT(0x08, 0x4B), //  USAGE (Generic Indicator)
       HID_SHORT(0x94, 8),    //  REPORT_COUNT(8)
       HID_SHORT(0x90, 0x02), //  OUTPUT (Data, Var, Abs)
       HID_SHORT(0x84, 0x02), //  REPORT_ID (2)
       HID_SHORT(0x14, 0xFF), //  LOGICAL_MINIMUM (-128)
       HID_SHORT(0x24, 0x7F), //  LOGICAL_MAXIMUM (127)
       HID_SHORT(0x74, 0x08), //  REPORT_SIZE (8)
       HID_SHORT(0x94, 2),    //  REPORT_COUNT (2)
       HID_SHORT(0x04, 0x01), //  USAGE_PAGE (Generic Desktop)
       HID_SHORT(0x08, 0x38), //  USAGE (Wheel)
       HID_SHORT(0x80, 0x06), //  INPUT (Data, Var, Rel)
       HID_SHORT(0xc0),       //END_COLLECTION
   };

The three reports defined here are\:


* IN report 1\: Contains 4 bits of D-pad information (up through left) and 4 bits of constant data (basically just filler bits).


* OUT report 1\: Contains 8 bits describing the on-off state of eight Generic Indicator LEDs.


* IN report 2\: Contains two 8-bit Wheel fields whose data is relative and ranges from -127 to 127.



Some more interesting things that this example brings up\:


* It just so happens that IN report 1 and OUT report 1 are the same size\: 1 byte (2 bytes transferred because of the report ID). However, they don't need to be.


* USAGE_MINIMUM and USAGE_MAXIMUM allow usages to be mapped to multiple fields when REPORT_COUNT is greater than 1. I don't know what happens if USAGE_MINIMUM and USAGE_MAXIMUM's span is smaller than REPORT_COUNT (I suspect that it will just repeat USAGE_MAXIMUM to the end of REPORT_COUNT after it finishes counting up). In this example, this allowed one INPUT token to declare a field for usages 0x90, 0x91, 0x92, and 0x93.


* I declared two INPUT tokens in a row. In this case this is permissible because the second INPUT is a constant. Constant values do not require a USAGE (though they may have one). These two tokens appear in a row because the constant input is also four copies of a 1-bit field (I could also have made it a single 4-bit field).



**Note that in the HID Usage Tables document, there are more examples in Appendix A!**


 

.. _step-3:

Step 3\: Sending IN Reports
===========================


Now that you've got your report descriptors all figured out, you need to actually send the data. This is not complicated.

In your configuration descriptor, you gave a polling rate for the endpoint. This polling rate does not imply that the host expects you to transfer a report at that rate. It only means that the host will attempt to start an IN transfer that often. When you have no report to send, make your endpoint NAK (don't STALL).

In my LED Watch project I wrote a USB API which takes care of packetizing for me. When I want to send data, I just point it towards an byte array and it sends it using as many or as few packets. For HID reports, I only sent them as-needed. The only complicated part is constructing the report itself. Follow these simple steps to send an IN report\:


#. Construct your report.
#. If you use the REPORT_ID token, then make sure the first byte of your report contains the report ID. All the other fields are concatenated later (so an 8-byte report is actually 9-bytes).


   #. One way of organizing this might be to make a C struct that matches the layout of your report. Or you can use a straight-up byte array. Whichever makes the most sense for your application.

#. Point your USB peripheral towards your report.
#. This will vary by microcontroller. On the Kinetis K20 (Teensy 3.x series), this is accomplished by pointing the appropriate Buffer Descriptor Table entry towards the memory address of your report. On the STM32 this is accomplished by copying the report data into the Packet Memory Area at the address pointed to by the Buffer Descriptor Table.

#. Tell your USB peripheral that the endpoint is Valid or Ready. When the host attempts to read the endpoint, the peripheral will send your report.
#. On both the K20 and STM32 there are just some bits to flip in the endpoint register.


You'll probably want to set up some system for notifying the program that the report was sent. Note that most microcontroller USB peripherals should set an endpoint to NAK once a report has sent, so the host will not see another report to read until you explicitly tell your peripheral to send again.

.. _step-4:

Step 4\: Sending OUT Reports
============================


This is the exact same story as IN reports, except this time you don't construct a report. Instead, you allocate space for it and wait for the host to send. Here's the steps for an OUT report\:


#. Allocate some memory and point your USB endpoint towards it.


#. Set your USB endpoint to be "Valid" or "Ready". The host can now write to it.
* Even though it is an interrupt endpoint, the host won't try to write unless it has some new data to send.

#. Wait for the interrupt from your peripheral that signals that the report has been received.


#. Process the report and when ready to accept another OUT report, set the endpoint to be "Valid" or "Ready" again.



Remember again that if you used the REPORT_ID token, the first byte will be the report ID and all bytes that follow will be the report.

.. _host:

Host Software
=============


Writing host software for HID devices is not complicated, but there are some gotchas to keep in mind. In general, the operating system will expose USB devices as a file of some kind. On Linux you can use the parsed hid driver or the unparsed hidraw driver (I've only used hidraw). hidraw will let you send raw reports. A similar system exists for Windows. HID devices are exposed as files which can be manipulated either with raw reports (using read and write on the file) or with the hid report parser (via calls to hid.dll).

When choosing how to write your host software you can choose to either use the OS's input system which will parse HID reports for you (abstracting away the reports themselves) or you can talk to the device in terms of reports ("raw"). I can't give much guidance for using the host's report parser, but for talking raw in terms of reports I do have some suggestions\:

.. _host-c:

C/C++ Cross-Platform
--------------------


If you're application is going to be written in C or C++, then there is a fairly convenient cross-platform option available\: `https\://github.com/signal11/hidapi <https://github.com/signal11/hidapi>`__

This library will take care of all the stuff that is required to enumerate the HID devices attached the computer. It will also handle reading and writing to the device using raw reports.

.. _host-python:

Python under Linux
------------------


For python, I highly recommend using the "hid" module\: `https\://pypi.python.org/pypi/hid <https://pypi.python.org/pypi/hid>`__

An example of using this can be found in the "host" directory in my LED watch repository.

.. _host-c-sharp:

C# under Windows
----------------


The enumeration of human interface devices and communication with them happens using some methods in hid.dll and kernel32.dll. Using P/Invoke you can talk to these using C#. There are several libraries for this, but the lightest weight one I can find is here\: `https\://github.com/MightyDevices/MightyHID <https://github.com/MightyDevices/MightyHID>`__

I don't actually recommend using the library itself. Rather, I would recommend reading through it and seeing how it does things and implementing that in your application directly. Sadly, although I have written an application in C# that talked pretty well to HID devices I do not have the source code available. Instead, I can give some tips\:


* **Don't be afraid of using P/Invoke.** At a bare minimum, you're going to have to to enumerate the HID devices in the system this way.


* **Don't forget to enable Overlapped I/O.** Although USB is a half-duplex communication medium for HID, the OS will expose it as full duplex. You can read and write concurrently to the file. When I did this I had a Read always pending to wait for the next IN report and occasionally sent Writes to update the device.


* **Although HID devices can be used with FileStream **(since you can get a SafeFileHandle out of CreateFile, which is used for opening the HID)**, don't do it. Use ReadFile and WriteFile instead through P/Invoke.** The temptation will be there since FileStream has a constructor that takes a SafeFileHandle, but you really shouldn't. The reason is that the FileStream is *not full-duplex*! Deep down inside, if a read is pending on the FileStream, all writes will block. Vice-versa if a write is pending. This means that if you start an asynchronous read on a FileStream to wait for the next HID IN Report, but you want to send an OUT report, that OUT report won't actually be sent until after the next IN report is received! The worst part is that the asynchronous write will actually complete, even though the operation is blocked and won't actually occur until later!! This makes for what looks like "lag" when writing to the device. The reason for this is explained in the comments in Microsoft's source code, but suffice to say that they could not find a good solution that spanned all possible use cases and so asynchronous reads/writes are made to be sequential rather than concurrent. I think the network stream overcomes this because it is more specific than a file stream.


* **Don't forget to pin your buffers when doing overlapped async I/O.** You need to make sure the garbage collector doesn't come by and decide to move your buffer to another address while the ReadFile or WriteFile is doing its thing. When you use those functions in overlapped I/O mode, they will return immediately rather than blocking and therefore the garbage collector could have an opportunity to strike.


* **I recommend using Marshal.AllocHGlobal and Marshal.FreeHGlobal instead of GCHandle.Alloc(object, GCHandleType.Pinned) for pinning your buffers.** I found that for the small buffer sizes involved in HID communication, its easier to use Marshall.AllocHGlobal to allocate one buffer in unmanaged memory (which the GC won't touch) and then copy to and from a buffer in managed memory (just a byte[]). The other option is to allocate your byte[] in managed memory and then use a GCHandle to pin it. I found that to be more difficult to manage since there are a LOT of corner cases that need to be handled. For the AllocHGlobal, the only corner case is that you forget to free it and that's easily fixed by wrapping the AllocHGlobal/FreeHGlobal calls inside the constructor and finalizer of an object, using the object to keep track of the allocated section of unmanaged memory. You can even implement IDisposable if you want deterministic control of the lifetime of the pointer.




.. _conclusion:

Conclusion
==========


At this point, I hope that I've armed you with enough information that you can implement a human interface device with any microcontroller that you have a working USB implementation for. We've gone through modifying the configuration descriptor, writing a report descriptor, sending and receiving reports, and briefly touched on writing host software to talk to the HID devices.

As always, if you have any suggestions, ideas, or questions feel free to comment below.

.. rstblog-settings::
   :title: Cross-platform driverless USB: The Human Interface Device
   :date: 2018/02/02
   :url: /2018/02/02/cross-platform-driverless-usb-the-human-interface-device