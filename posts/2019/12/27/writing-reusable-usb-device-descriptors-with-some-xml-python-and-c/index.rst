
A recent project required me to reuse (once again) my USB HID device driver. This is my third or fourth project using this and I had started to find it annoying to need to hand-modify a heavily-commented, self-referencing array of uint8_t's. I figured there must be a better way, so I decided to try something different.


In this post I will present a script that turns this madness, which lives in a separate file\:



::



   /**
    * Device descriptor
    */
   static const USB_DATA_ALIGN uint8_t dev_descriptor[] = {
       18, //bLength
       1, //bDescriptorType
       0x00, 0x02, //bcdUSB
       0x00, //bDeviceClass (defined by interfaces)
       0x00, //bDeviceSubClass
       0x00, //bDeviceProtocl
       USB_CONTROL_ENDPOINT_SIZE, //bMaxPacketSize0
       0xc0, 0x16, //idVendor
       0xdc, 0x05, //idProduct
       0x11, 0x00, //bcdDevice
       1, //iManufacturer
       2, //iProduct
       0, //iSerialNumber,
       1, //bNumConfigurations
   };

   static const USB_DATA_ALIGN uint8_t hid_report_descriptor[] = {
       HID_SHORT(0x04, 0x00, 0xFF), //USAGE_PAGE (Vendor Defined)
       HID_SHORT(0x08, 0x01), //USAGE (Vendor 1)
       HID_SHORT(0xa0, 0x01), //COLLECTION (Application)
       HID_SHORT(0x08, 0x01), //  USAGE (Vendor 1)
       HID_SHORT(0x14, 0x00), //  LOGICAL_MINIMUM (0)
       HID_SHORT(0x24, 0xFF, 0x00), //LOGICAL_MAXIMUM (0x00FF)
       HID_SHORT(0x74, 0x08), //  REPORT_SIZE (8)
       HID_SHORT(0x94, 64), //  REPORT_COUNT(64)
       HID_SHORT(0x80, 0x02), //  INPUT (Data, Var, Abs)
       HID_SHORT(0x08, 0x01), //  USAGE (Vendor 1)
       HID_SHORT(0x90, 0x02), //  OUTPUT (Data, Var, Abs)
       HID_SHORT(0xc0),       //END_COLLECTION
   };

   /**
    * Configuration descriptor
    */
   static const USB_DATA_ALIGN uint8_t cfg_descriptor[] = {
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

   static const USB_DATA_ALIGN uint8_t lang_descriptor[] = {
       4, //bLength
       3, //bDescriptorType
       0x09, 0x04 //wLANGID[0]
   };

   static const USB_DATA_ALIGN uint8_t manuf_descriptor[] = {
       2 + 15 * 2, //bLength
       3, //bDescriptorType
       'k', 0x00, //wString
       'e', 0x00,
       'v', 0x00,
       'i', 0x00,
       'n', 0x00,
       'c', 0x00,
       'u', 0x00,
       'z', 0x00,
       'n', 0x00,
       'e', 0x00,
       'r', 0x00,
       '.', 0x00,
       'c', 0x00,
       'o', 0x00,
       'm', 0x00
   };

   static const USB_DATA_ALIGN uint8_t product_descriptor[] = {
       2 + 14 * 2, //bLength
       3, //bDescriptorType
       'L', 0x00,
       'E', 0x00,
       'D', 0x00,
       ' ', 0x00,
       'W', 0x00,
       'r', 0x00,
       'i', 0x00,
       's', 0x00,
       't', 0x00,
       'w', 0x00,
       'a', 0x00,
       't', 0x00,
       'c', 0x00,
       'h', 0x00
   };

   const USBDescriptorEntry usb_descriptors[] = {
       { 0x0100, 0x0000, sizeof(dev_descriptor), dev_descriptor },
       { 0x0200, 0x0000, sizeof(cfg_descriptor), cfg_descriptor },
       { 0x0300, 0x0000, sizeof(lang_descriptor), lang_descriptor },
       { 0x0301, 0x0409, sizeof(manuf_descriptor), manuf_descriptor },
       { 0x0302, 0x0409, sizeof(product_descriptor), product_descriptor },
       { 0x2200, 0x0000, sizeof(hid_report_descriptor), hid_report_descriptor },
       { 0x0000, 0x0000, 0x00, NULL }
   };

Into these comment blocks which can live anywhere in the source and are somewhat more readable\:



.. code-block:: c



   /**
    * <descriptor id="device" type="0x01">
    *  <length name="bLength" size="1" />
    *  <type name="bDescriptorType" size="1" />
    *  <word name="bcdUSB">0x0200</word>
    *  <byte name="bDeviceClass">0</byte>
    *  <byte name="bDeviceSubClass">0</byte>
    *  <byte name="bDeviceProtocol">0</byte>
    *  <byte name="bMaxPacketSize0">USB_CONTROL_ENDPOINT_SIZE</byte>
    *  <word name="idVendor">0x16c0</word>
    *  <word name="idProduct">0x05dc</word>
    *  <word name="bcdDevice">0x0010</word>
    *  <ref name="iManufacturer" type="0x03" refid="manufacturer" size="1" />
    *  <ref name="iProduct" type="0x03" refid="product" size="1" />
    *  <byte name="iSerialNumber">0</byte>
    *  <count name="bNumConfigurations" type="0x02" size="1" />
    * </descriptor>
    * <descriptor id="lang" type="0x03" first="first">
    *  <length name="bLength" size="1" />
    *  <type name="bDescriptorType" size="1" />
    *  <foreach type="0x03" unique="unique">
    *    <echo name="wLang" />
    *  </foreach>
    * </descriptor>
    * <descriptor id="manufacturer" type="0x03" wIndex="0x0409">
    *  <property name="wLang" size="2">0x0409</property>
    *  <length name="bLength" size="1" />
    *  <type name="bDescriptorType" size="1" />
    *  <string name="wString">kevincuzner.com</string>
    * </descriptor>
    * <descriptor id="product" type="0x03" wIndex="0x0409">
    *  <property name="wLang" size="2">0x0409</property>
    *  <length name="bLength" size="1" />
    *  <type name="bDescriptorType" size="1" />
    *  <string name="wString">LED Wristwatch</string>
    * </descriptor>
    * <descriptor id="configuration" type="0x02">
    *  <length name="bLength" size="1" />
    *  <type name="bDescriptorType" size="1" />
    *  <length name="wTotalLength" size="2" all="all" />
    *  <count name="bNumInterfaces" type="0x04" associated="associated" size="1" />
    *  <byte name="bConfigurationValue">1</byte>
    *  <byte name="iConfiguration">0</byte>
    *  <byte name="bmAttributes">0x80</byte>
    *  <byte name="bMaxPower">250</byte>
    *  <children type="0x04" />
    * </descriptor>
    */

   /**
    * <include>usb_hid.h</include>
    * <descriptor id="hid_interface" type="0x04" childof="configuration">
    *  <length name="bLength" size="1" />
    *  <type name="bDescriptorType" size="1" />
    *  <index name="bInterfaceNumber" size="1" />
    *  <byte name="bAlternateSetting">0</byte>
    *  <count name="bNumEndpoints" type="0x05" associated="associated" size="1" />
    *  <byte name="bInterfaceClass">0x03</byte>
    *  <byte name="bInterfaceSubClass">0x00</byte>
    *  <byte name="bInterfaceProtocol">0x00</byte>
    *  <byte name="iInterface">0</byte>
    *  <children type="0x21" />
    *  <children type="0x05" />
    * </descriptor>
    * <descriptor id="hid" type="0x21" childof="hid_interface">
    *  <length name="bLength" size="1" />
    *  <type name="bDescriptorType" size="1" />
    *  <word name="bcdHID">0x0111</word>
    *  <byte name="bCountryCode">0x00</byte>
    *  <count name="bNumDescriptors" type="0x22" size="1" associated="associated" />
    *  <foreach type="0x22" associated="associated">
    *    <echo name="bDescriptorType" />
    *    <echo name="wLength" />
    *  </foreach>
    * </descriptor>
    * <descriptor id="hid_in_endpoint" type="0x05" childof="hid_interface">
    *  <length name="bLength" size="1" />
    *  <type name="bDescriptorType" size="1" />
    *  <inendpoint name="bEndpointAddress" define="HID_IN_ENDPOINT" />
    *  <byte name="bmAttributes">0x03</byte>
    *  <word name="wMaxPacketSize">USB_HID_ENDPOINT_SIZE</word>
    *  <byte name="bInterval">10</byte>
    * </descriptor>
    * <descriptor id="hid_out_endpoint" type="0x05" childof="hid_interface">
    *  <length name="bLength" size="1" />
    *  <type name="bDescriptorType" size="1" />
    *  <outendpoint name="bEndpointAddress" define="HID_OUT_ENDPOINT" />
    *  <byte name="bmAttributes">0x03</byte>
    *  <word name="wMaxPacketSize">USB_HID_ENDPOINT_SIZE</word>
    *  <byte name="bInterval">10</byte>
    * </descriptor>
    * <descriptor id="hid_report" childof="hid" top="top" type="0x22" order="1" wIndexType="0x04">
    *  <hidden name="bDescriptorType" size="1">0x22</hidden>
    *  <hidden name="wLength" size="2">sizeof(hid_report)</hidden>
    *  <raw>
    *  HID_SHORT(0x04, 0x00, 0xFF), //USAGE_PAGE (Vendor Defined)
    *  HID_SHORT(0x08, 0x01), //USAGE (Vendor 1)
    *  HID_SHORT(0xa0, 0x01), //COLLECTION (Application)
    *  HID_SHORT(0x08, 0x01), //  USAGE (Vendor 1)
    *  HID_SHORT(0x14, 0x00), //  LOGICAL_MINIMUM (0)
    *  HID_SHORT(0x24, 0xFF, 0x00), //LOGICAL_MAXIMUM (0x00FF)
    *  HID_SHORT(0x74, 0x08), //  REPORT_SIZE (8)
    *  HID_SHORT(0x94, 64), //  REPORT_COUNT(64)
    *  HID_SHORT(0x80, 0x02), //  INPUT (Data, Var, Abs)
    *  HID_SHORT(0x08, 0x01), //  USAGE (Vendor 1)
    *  HID_SHORT(0x90, 0x02), //  OUTPUT (Data, Var, Abs)
    *  HID_SHORT(0xc0),       //END_COLLECTION
    *  </raw>
    * </descriptor>
    */


In most of my projects before this one I would have something like the first script shown above sitting in a file by itself, declaring a bunch of uint8_t arrays and a usb_descriptors[] table constant that would be consumed by my USB driver as it searched for USB descriptors. A header file that exposes the usb_descriptors[] table would also be found in the project. Any USB descriptor that had to be returned by the device would be found in this table. To make things more complex, descriptors like the configuration descriptor have to declare all of the device interfaces and so pieces and parts of each separate USB interface component would be interspersed inside of other descriptors.


I've been using this structure for some time after writing my first USB driver after reading through the Teensy driver. This is probably the only structural code that has made it all the way from the Teensy driver into all of my other code.


With this new script I've written there's no more need for manually computing how long a descriptor is or needing to modify the configuration descriptor every time a new interface has been added. All the parts of a descriptor are self-contained in the source file that defines a particular interface and can be easily moved around from project to project.


**All the code for this post lives here\:**


**`https\://github.com/kcuzner/midi-fader <https://github.com/kcuzner/midi-fader>`__**



.. rstblog-break::











Contents
--------




* `The Script <the-script>`__


* `Makefile Changes <makefile-changes>`__


* `USB Descriptor XML <usb-descriptors>`__


* `USB Application Object <usb-application>`__


* `Conclusion <conclusion>`__




.. _the-script:

The Script
----------


I have continued to write my descriptors using the "Teensy method" for a few reasons\:




* They are compile-time constants and therefore don't take up valuable RAM (which consumes both .data and .rodata segments). I've seen other implementations that initialize a writable array in RAM with the descriptor and that just doesn't work well with memory-constrained embedded systems. It just makes the USB driver stack footprint too large for my comfort.


* It is easy to figure out what is going on. There is very little "macro magic" here. Even the part where I look up descriptors in the table is really straightforward and beyond that, everything is just an opaque byte array that is copied out over USB. Real simple.



Writing descriptors like this has some problems, however\:




* It requires me to manually edit the binary contents of the descriptors, keep multiple fields in sync (i.e. length fields vs actual length), and handle endianness manually.


* Making a new project requires me to copy-paste pieces from another project's descriptor file into my configuration descriptor and hope that I updated the lengths correctly.


* Adding a new interface to my configuration again required editing this blob and hoping that I got it right.


* Without generous comments, it is impossible to interpret and read. Finding a bug in the descriptor is very much a "stare at it until something moves" sort of process.



So, I decided to improve this a bit with some scripting. Here were my goals\:




* Fully automatic computation of the wLength fields in descriptors.


* Ad-hoc descriptor definition (i.e. I can specify descriptors throughout the code in many places).


* Portable to all my machines without any dependencies other than Python. In general I use arch with python installed, so requesting that python be available isn't a big deal for me.


* Fully compatible with my existing USB driver structure (i.e. use the same usb_descriptors table format).


* Fairly agnostic of the actual USB driver used. The idea is that this can be used by other people who don't want to be stuck with my USB driver implementation.



The way my script works, block comments in any source file can contain XML which is interpreted by the script which in turn generates a C file that declares the usb_descriptors[] table and contains the generated byte arrays containing all descriptors declared in the program. In addition, I have a static "USBApplication" object which handles each USB interface in a modular manner. I can how have my HID interface completely self-contained in a single file, my audio device interface in another single file, and some other custom interface in its own file. If I want to move the HID interface to another project, all I have to do is copy-paste the single HID source file (and header) and everything (source, descriptors, USB interface declaration) comes along with it. Nice and easy!


For example, here is the "main.c" file of my `midi-fader device <https://github.com/kcuzner/midi-fader>`__\:



.. code-block:: c



   /**
    * USB Midi-Fader
    *
    * Kevin Cuzner
    *
    * Main Application
    */

   #include "usb.h"
   #include "usb_app.h"
   #include "usb_hid.h"
   #include "usb_midi.h"
   #include "osc.h"
   #include "error.h"
   #include "storage.h"
   #include "fader.h"
   #include "buttons.h"
   #include "systick.h"
   #include "mackie.h"

   #include "stm32f0xx.h"

   #include "_gen_usb_desc.h"

   /**
    * <descriptor id="device" type="0x01">
    *  <length name="bLength" size="1" />
    *  <type name="bDescriptorType" size="1" />
    *  <word name="bcdUSB">0x0200</word>
    *  <byte name="bDeviceClass">0</byte>
    *  <byte name="bDeviceSubClass">0</byte>
    *  <byte name="bDeviceProtocol">0</byte>
    *  <byte name="bMaxPacketSize0">USB_CONTROL_ENDPOINT_SIZE</byte>
    *  <word name="idVendor">0x16c0</word>
    *  <word name="idProduct">0x05dc</word>
    *  <word name="bcdDevice">0x0010</word>
    *  <ref name="iManufacturer" type="0x03" refid="manufacturer" size="1" />
    *  <ref name="iProduct" type="0x03" refid="product" size="1" />
    *  <byte name="iSerialNumber">0</byte>
    *  <count name="bNumConfigurations" type="0x02" size="1" />
    * </descriptor>
    * <descriptor id="lang" type="0x03" first="first">
    *  <length name="bLength" size="1" />
    *  <type name="bDescriptorType" size="1" />
    *  <foreach type="0x03" unique="unique">
    *    <echo name="wLang" />
    *  </foreach>
    * </descriptor>
    * <descriptor id="manufacturer" type="0x03" wIndex="0x0409">
    *  <property name="wLang" size="2">0x0409</property>
    *  <length name="bLength" size="1" />
    *  <type name="bDescriptorType" size="1" />
    *  <string name="wString">kevincuzner.com</string>
    * </descriptor>
    * <descriptor id="product" type="0x03" wIndex="0x0409">
    *  <property name="wLang" size="2">0x0409</property>
    *  <length name="bLength" size="1" />
    *  <type name="bDescriptorType" size="1" />
    *  <string name="wString">Midi-Fader</string>
    * </descriptor>
    * <descriptor id="configuration" type="0x02">
    *  <length name="bLength" size="1" />
    *  <type name="bDescriptorType" size="1" />
    *  <length name="wTotalLength" size="2" all="all" />
    *  <count name="bNumInterfaces" type="0x04" associated="associated" size="1" />
    *  <byte name="bConfigurationValue">1</byte>
    *  <byte name="iConfiguration">0</byte>
    *  <byte name="bmAttributes">0x80</byte>
    *  <byte name="bMaxPower">250</byte>
    *  <children type="0x04" />
    * </descriptor>
    */

   #include <stddef.h>

   static const USBInterfaceListNode midi_interface_node = {
       .interface = &midi_interface,
       .next = NULL,
   };

   static const USBInterfaceListNode hid_interface_node = {
       .interface = &hid_interface,
       .next = &midi_interface_node,
   };

   const USBApplicationSetup setup = {
       .interface_list = &hid_interface_node,
   };

   const USBApplicationSetup *usb_app_setup = &setup;

   uint8_t buf[16];
   int main()
   {
   ...
       return 0;
   }

It only needs to declare the main device descriptor with the manufacturer and model strings. I have two other interfaces (usb_hid and usb_midi) in this project, but there's no trace of them here except for the bits where I hook them into the overall application. I'll talk a little more about that at the end, but the main point of this post is to show my new method for handling USB descriptors.



.. _makefile-changes:

Makefile changes
----------------


The script consists of a 800-ish line python script (current version\: `https\://github.com/kcuzner/midi-fader/blob/master/firmware/scripts/descriptorgen.py <https://github.com/kcuzner/midi-fader/blob/master/firmware/scripts/descriptorgen.py>`__) which takes as its arguments every source file in the project that could have some block comments. It then does the following\:




#. Find all block comments (/\* ... \*/) in the source and extract them, stripping off leading "\*" characters from each line. The blocks are retained as individual continuous pieces and are each parsed separately.


#. If the block doesn't contain text matching the regex "<descriptor+.>", it is discarded. Otherwise, the contents of the block comment are wrapped in an arbitrary element and then parsed using `elementtree <https://docs.python.org/2/library/xml.etree.elementtree.html>`__.


#. Each parsed comment block is assumed to declare one or more "descriptors". The parsed XML is run through an interpreter which begins assembling objects which will generate the binary descriptor.


#. After every block has been parsed, the script will generate all the descriptors into a C file, automatically tracking endpoint numbers, addresses, and descriptor lengths.



The C file that this generates is placed in the obj folder during compilation and treated as a non-source-controlled component. It is regenerated every time the makefile is run. Here is a snippet of how my makefile invokes this script. I hope this makes some sense. My makefile style has changed somewhat for this project enable multiple targets, but hopefully this communicates the gist of how I made the Makefile execute the python script before compiling any other objects.



.. code-block:: sh



   # These are spread out among several files, but are concatenated here for easy
   # reading

   #
   # These are declared in a Makefile meant as a header:
   #

   # Project structure
   SRCDIRS = src
   GENSRCDIRS = src
   BINDIR = bin
   OBJDIR = obj
   GENDIR = obj/gen
   CSRCDIRS = $(SRCDIRS)
   SSRCDIRS = $(SRCDIRS)

   # Sources
   GENERATE =
   SRC = $(foreach DIR,$(CSRCDIRS),$(wildcard $(DIR)/*.c))
   GENSRC = $(foreach DIR,$(GENSRCDIRS),$(wildcard $(DIR)/*.c))
   STORAGESRC = $(foreach DIR,$(CSRCDIRS),$(wildcard $(DIR)/*.storage.xml))
   ASM = $(foreach DIR,$(SSRCDIRS),$(wildcard $(DIR)/*.s))

   #
   # These are declared in the per-project makefile that configures the build
   # process:
   #

   SRCDIRS = src
   GENSRCDIRS = src

   # This will cause the USB descriptor to be generated
   GENERATE = USB_DESCRIPTOR

   #
   # These are declared in a Makefile meant as a footer that declares all recipes:
   #

   GENERATE_USB_DESCRIPTOR=USB_DESCRIPTOR
   GENERATE_USB_DESCRIPTOR_SRC=_gen_usb_desc.c
   GENERATE_USB_DESCRIPTOR_HDR=_gen_usb_desc.h

   OBJ := $(addprefix $(OBJDIR)/,$(notdir $(SRC:.c=.o)))
   OBJ += $(addprefix $(OBJDIR)/,$(notdir $(ASM:.s=.o)))

   # If the USB descriptor generation is requested, add it to the list of targets
   # which will run during code generation
   ifneq ($(filter $(GENERATE), $(GENERATE_USB_DESCRIPTOR)),)
   	GEN_OBJ += $(GENDIR)/$(GENERATE_USB_DESCRIPTOR_SRC:.c=.o)
   	GEN_TARGETS += $(GENERATE_USB_DESCRIPTOR)
   endif

   ALL_OBJ := $(OBJ) $(GEN_OBJ)

   # Invoke the python script to generate the USB descriptor
   $(GENERATE_USB_DESCRIPTOR):
   	@mkdir -p $(GENDIR)
   	$(DESCRIPTORGEN) -os $(GENDIR)/$(GENERATE_USB_DESCRIPTOR_SRC) \
   		-oh $(GENDIR)/$(GENERATE_USB_DESCRIPTOR_HDR) \
   		$(GENSRC)

   # Ensure generated objects get run first
   $(OBJ): | $(GEN_TARGETS)

   #
   # Later, the $(ALL_OBJ) variable is used in the linking step to include the
   # generated C source files.
   #


It's not the most straightforward method, but it works well for my multi-target project structure that I've been using lately. Perhaps I'll write a post about that someday.


This works like so\:




#. The GENERATE variable is set to contain the phrase "USB_DESCRIPTOR" which will trigger evaluation of the variables that will cause the USB descriptor to be generated.


#. The ifneq statement adds $(GENERATE_USB_DESCRIPTOR) to the GEN_TARGETS variable if GENERATE contains the phrase "USB_DESCRIPTOR". The targets in this variable will have their recipes evaluated as a dependency for all the object files in $(OBJ) which doesn't include the generated object files.


#. During makefile evaluation, the $(OBJ) list is created from all the source and is depended on by targets like "all" (not shown). This triggers evaluation of $(GEN_TARGETS) which is just set to $(GENERATE_USB_DESCRIPTOR).


#. The $(GENERATE_USB_DESCRIPTOR) target's recipe is invoked. The python script is run with all source files as its argument. It creates the generated C files whose objects are captured in $(GEN_OBJ).


#. Compilation will continue, compiling the C files for $(OBJ) and the C files for $(GEN_OBJ). This isn't shown in the snippet.


#. Finally all the resulting objects (both source and generated files) are linked into the executable. Again, this isn't shown in the snippet.




.. _usb-descriptors:

USB Descriptor XML
------------------


As the python script is run, it searches the source files for XML which describes the USB descriptors. To demonstrate the XML format, here is the simplest USB descriptor. This will just declare a device, add product and model strings, and declare a simple configuration that requires maximum USB power\:



.. code-block:: xhtml



   <descriptor id="device" type="0x01">
     <length name="bLength" size="1" />
     <type name="bDescriptorType" size="1" />
     <word name="bcdUSB">0x0200</word>
     <byte name="bDeviceClass">0</byte>
     <byte name="bDeviceSubClass">0</byte>
     <byte name="bDeviceProtocol">0</byte>
     <byte name="bMaxPacketSize0">USB_CONTROL_ENDPOINT_SIZE</byte>
     <word name="idVendor">0x16c0</word>
     <word name="idProduct">0x05dc</word>
     <word name="bcdDevice">0x0010</word>
     <ref name="iManufacturer" type="0x03" refid="manufacturer" size="1" />
     <ref name="iProduct" type="0x03" refid="product" size="1" />
     <byte name="iSerialNumber">0</byte>
     <count name="bNumConfigurations" type="0x02" size="1" />
   </descriptor>
   <descriptor id="lang" type="0x03" first="first">
     <length name="bLength" size="1" />
     <type name="bDescriptorType" size="1" />
     <foreach type="0x03" unique="unique">
       <echo name="wLang" />
     </foreach>
   </descriptor>
   <descriptor id="manufacturer" type="0x03" wIndex="0x0409">
     <property name="wLang" size="2">0x0409</property>
     <length name="bLength" size="1" />
     <type name="bDescriptorType" size="1" />
     <string name="wString">kevincuzner.com</string>
   </descriptor>
   <descriptor id="product" type="0x03" wIndex="0x0409">
     <property name="wLang" size="2">0x0409</property>
     <length name="bLength" size="1" />
     <type name="bDescriptorType" size="1" />
     <string name="wString">Midi-Fader</string>
   </descriptor>
   <descriptor id="configuration" type="0x02">
     <length name="bLength" size="1" />
     <type name="bDescriptorType" size="1" />
     <length name="wTotalLength" size="2" all="all" />
     <count name="bNumInterfaces" type="0x04" associated="associated" size="1" />
     <byte name="bConfigurationValue">1</byte>
     <byte name="iConfiguration">0</byte>
     <byte name="bmAttributes">0x80</byte>
     <byte name="bMaxPower">250</byte>
     <children type="0x04" />
   </descriptor>


The syntax is as follows\:




* Every USB descriptor is declared using a **<descriptor>** element. This element has an "id" and a "type" attribute. The "id" is just a string which can be used to refer to the descriptor later inside of other descriptors. The "type" is a number which is exactly the same as the USB descriptor type as declared in the USB specification. For example, a device descriptor is type "1", a configuration descriptor is type "2", a string descriptor is type "3", and an interface descriptor is type "4".


  * I added the "type" as a **<descriptor>**-level attribute because elements like **<children>** require that we have indexed descriptors by type.


  * The **<descriptor>** can optionally declare the "childof" attribute. This attribute should be set to the "id" of another descriptor in which this discriptor will appear. If the "childof" attribute isn't specified, then the descriptor will appear in the global "usb_descriptors" table.





* The order of the children inside the **<descriptor>** element defines the structure of the USB descriptor. Each element may create 0 or more bytes in the resulting output byte array\:


  * Most child elements have a "name" attribute. This allows them to be referenced by other child elements in the same descriptor.


  * The **<length>** element will output the length of the descriptor in bytes. It has a "size" attribute which says how many bytes to take up. Note that in a configuration descriptor, this is used twice\: Once for the bDescriptorLength (which is always 9) and once for the wTotalLength (which varies depending on the number of interfaces). By default, bytes created by the <children> element are not counted in the bytes generated by the <length> tag unless the "all" attribute is present.


  * The **<type>** element just echoes the type of the parent **<descriptor>** in the number of bytes specified by "size". This allows us to single-source the descriptor type number only in the **<descriptor>** element.


  * The **<count>** element outputs the number of descriptors of some type specified by the "type" attribute. This is the same "type" as declared in **<descriptor>**.


    * There is the concept of "associated" descriptors. An associated descriptor is one that declares this descriptor as its parent. If we don't specify the "associated" attribute, then **<count>** will count all descriptors found of the specified "type". Otherwise, it will only count descriptors who have explicitly declared that they are children of this descriptor.





  * The **<string>** element generates the bytes for a USB wchar string based on the text contained in the element.


    * This was one of the things about manual descriptors that annoyed me the most. I've never had to use the upper byte of wchars and so reading or modifying the strings was always a pain with the extra null bytes between each character.





  * The **<byte>** element generates a single byte based on interpeting the text in this element as a number.


  * The **<word>** element generates two bytes based on interpreting the text in this element as a number.


  * The **<property>** element declares non-outputting binary content that is associated with this descriptor by interpreting the text in this element as a number. The content can be outputted in other ways, such as through the **<foreach>** element in another descriptor. Its "size" argument declares how many bytes this will produce.


  * The **<children>** element will echo the entire binary contents of descriptors which declare their "childof" attribute to have the id of this descriptor. It has a "type" attribute which specifies which type of descriptor to echo.


  * The **<foreach>** element will output binary content based on the content of other descriptors. It has a "type" argument which specifies the descriptor type to enumerate. It examines all descriptors declared.


    * This element can have one child\: **<echo>**. The **<echo>** element will take the binary content of the element whose name matches this element's "name" attribute in each descriptor matched by the **<foreach>** element.


    * The "unique" attribute of the **<foreach>** element will ensure that there are no duplicate **<echo>** values.


    * This is pretty much only used to output the "wLang" attribute of the string descriptors in the 0th string descriptor.









There's a couple other child tags that a descriptor can have, but they aren't part of this code snippet and are meant for facilitating HID report descriptors or more complex descriptors. See `usb_hid.c <https://github.com/kcuzner/midi-fader/blob/master/firmware/common/src/usb_hid.c>`__ and `usb_midi.c <https://github.com/kcuzner/midi-fader/blob/master/firmware/src/usb_midi.c>`__ for details. You can also read the source and while I consider it somewhat readable, I hacked it together in about 2 days and it definitely shows. There are inconsistencies in the "API" and badly named things (like "**<hidden>**" which I didn't mention above. I really should have spent more time on that one...I'm not even sure about all the ways it's different from "**<property>**" reading it now).


To summarize, this descriptor generating script allows me to do some pretty convenient things\:




* I can define a descriptor for an interface in the same file as the source file that handles it.


* The descriptor moves around with the source, so I can simply copy-paste to another project without needing to make any changes.


* Adding a descriptor to a project requires no modification of the makefile to get it included. So long as my makefile finds the source, the descriptor gets included.




.. _usb-application:

USB Application Object
----------------------


This section can be ignored if you're just here for generating descriptors. That is pretty generic and everyone needs to do it. This is more specific to hooking this into my USB driver and ensuring that I can simply copy-paste files around between my projects and they "just work" without needing to modify other source (within reason)


The next step to having something fully portable is to have an easy way to hook into the entire application. In general, my drivers have functions that start with **hook_** which are called at certain points. Here are a few examples of hooks that I typically define\:




* **hook_usb_handle_setup_request**\: Called whenever a setup request is received. Passes the setup request as its argument. It is only called when a setup request arrives that can't be processed by the default handler (which only processes SET_ADDRESS and GET_DESCRIPTOR requests).


* **hook_usb_reset**\: This is called whenever the USB peripheral receives a reset condition.


* **hook_usb_sof**\: This is called whenever the USB peripheral receives an SOF packet. Useful for periodic events.


* **hook_usb_endpoint_sent**\: This is called whenever a packet queued for sending on an interface is successfully sent. Passes the endpoint and transmit buffer as arguments.


* **hook_usb_endpoint_received**\: This is called whenever a packet is fully received from the peripheral. Passes the endpoing and receive buffer as arguments.



These are usually defined like this in the calling module\:



.. code-block:: c



   USBControlResult __attribute__ ((weak)) hook_usb_handle_setup_request(USBSetupPacket const *setup, USBTransferData *nextTransfer)
   {
       return USB_CTL_STALL; //default: Stall on an unhandled request
   }
   void __attribute__ ((weak)) hook_usb_control_complete(USBSetupPacket const *setup) { }
   void __attribute__ ((weak)) hook_usb_reset(void) { }
   void __attribute__ ((weak)) hook_usb_sof(void) { }
   void __attribute__ ((weak)) hook_usb_set_configuration(uint16_t configuration) { }
   void __attribute__ ((weak)) hook_usb_set_interface(uint16_t interface) { }
   void __attribute__ ((weak)) hook_usb_endpoint_setup(uint8_t endpoint, USBSetupPacket const *setup) { }
   void __attribute__ ((weak)) hook_usb_endpoint_received(uint8_t endpoint, void *buf, uint16_t len) { }
   void __attribute__ ((weak)) hook_usb_endpoint_sent(uint8_t endpoint, void *buf, uint16_t len) { }

Application code can then interface to these hooks like so (example from my HID driver)\:



.. code-block:: c



   void hook_usb_endpoint_sent(uint8_t endpoint, void *buf, uint16_t len)
   {
       USBTransferData report = { buf, len };
       if (endpoint == HID_IN_ENDPOINT)
       {
           hook_usb_hid_in_report_sent(&report);
       }
   }

   void hook_usb_endpoint_received(uint8_t endpoint, void *buf, uint16_t len)
   {
       USBTransferData report = { buf, len };
       if (endpoint == HID_OUT_ENDPOINT)
       {
           hook_usb_hid_out_report_received(&report);
       }
   }

The problem with this is that since the **hook_** function can only be defined in a single place, every time I add an interface that needs to know when an endpoint receives a packet I need to modify the function. For composite devices (such as the midi-fader I'm using as an example here), this is really problematic and annoying for porting things between projects.


To remedy this, I created a "usb_app" layer which implements these **hook_** functions and then dispatches them to handlers. I define these handlers by way of some structs (which are const, so they get stored in flash rather than RAM)\:



.. code-block:: c



   /**
    * Structure instantiated by each interface
    *
    * This is intended to usually be a static constant, but it could also
    * be created on the fly.
    */
   typedef struct {
       /**
        * Hook function called when a USB reset occurs
        */
       USBNoParameterHook hook_usb_reset;
       /**
        * Hook function called when a setup request is received
        */
       USBHandleControlSetupHook hook_usb_handle_setup_request;
       /**
        * Hook function called when the status stage of a setup request is
        * completed on endpoint zero.
        */
       USBHandleControlCompleteHook hook_usb_control_complete;
       /**
        * Hook function called when a SOF is received
        */
       USBNoParameterHook hook_usb_sof;
       /**
        * Hook function called when a SET_CONFIGURATION is received
        */
       USBSetConfigurationHook hook_usb_set_configuration;
       /**
        * Hook function called when a SET_INTERFACE is received
        */
       USBSetInterfaceHook hook_usb_set_interface;
       /**
        * Hook function called when data is received on a USB endpoint
        */
       USBEndpointReceivedHook hook_usb_endpoint_received;
       /**
        * Hook function called when data is sent on a USB endpoint
        */
       USBEndpointSentHook hook_usb_endpoint_sent;
   } USBInterface;

   /**
    * Node structure for interfaces attached to the USB device
    */
   typedef struct USBInterfaceListNode {
       const USBInterface *interface;
       const struct USBInterfaceListNode *next;
   } USBInterfaceListNode;

   typedef struct {
       /**
        * Hook function called when the USB peripheral is reset
        */
       USBNoParameterHook hook_usb_reset;
       /**
        * Hook function called when a SOF is received.
        */
       USBNoParameterHook hook_usb_sof;
       /**
        * Head of the interface list. This node will be visited first
        */
       const USBInterfaceListNode *interface_list;
   } USBApplicationSetup;

   /**
    * USB setup constant
    *
    * Define this elsewhere, such as main
    */
   extern const USBApplicationSetup *usb_app_setup;

Every module that has a USB descriptor and some interface can then declare an **extern const USBInterface** in its header. The application using the module can then just attach it to the **usb_app_setup** for the project. For example, my HID interface declares this in its header\:



.. code-block:: c



   /**
    * USB interface object for the app
    */
   extern const USBInterface hid_interface;

And then in my main.c, I link it (along with any other interfaces) into the rest of my application like so (using the usb_app framework)\:



.. code-block:: c



   static const USBInterfaceListNode midi_interface_node = {
       .interface = &midi_interface,
       .next = NULL,
   };

   static const USBInterfaceListNode hid_interface_node = {
       .interface = &hid_interface, //this comes from usb_hid.h
       .next = &midi_interface_node,
   };

   const USBApplicationSetup setup = {
       .interface_list = &hid_interface_node,
   };

   const USBApplicationSetup *usb_app_setup = &setup;

Meanwhile, in my usb_hid.c I have defined **hid_interface** to look like this (all the referenced functions are also pretty short, but I haven't included them for brevity). If a hook is unused, I just leave it null\:



.. code-block:: c



   const USBInterface hid_interface = {
       .hook_usb_handle_setup_request = &hid_usb_handle_setup_request,
       .hook_usb_set_configuration = &hid_usb_set_configuration,
       .hook_usb_endpoint_sent = &hid_usb_endpoint_sent,
       .hook_usb_endpoint_received = &hid_usb_endpoint_received,
   };

Aside from the runtime overhead of now needing to walk a linked list to handle hooks, I now have a pretty low-resource method for making my modules portable. I can now take my self-contained module C file and header, drop them into a project (simply dropping them in tends to make the descriptor be generated), and then hook them up in main.c to the **usb_app_setup** object. Nice and easy.



.. _conclusion:

Conclusion
----------


I've presented here a couple code structure methods for making more portable embedded applications that use USB device desriptors (and their associated interface). My objective when I originally wrote these was to make it easier on myself when I wanted to build a project atop progress I had made on another project (since my home projects tend to go unfinished after they've achieved their goals for what I wanted to learn).


I expect the most useful thing here for others is probably the USB device descriptor generation, but perhaps my usb_app architecture can inspire someone to make an even better method for writing maintainable embedded code that has low runtime overhead.




.. rstblog-settings::
   :title: Writing reusable USB device descriptors with some XML, Python, and C
   :date: 2019/12/27
   :url: /2019/12/27/writing-reusable-usb-device-descriptors-with-some-xml-python-and-c