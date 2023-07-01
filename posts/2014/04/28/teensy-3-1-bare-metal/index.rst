
Introduction
============

A couple of weeks ago I saw a link on `hackaday <http://hackaday.com>`_ to an `article <http://www.seanet.com/~karllunt/bareteensy31.html>`_ by Karl Lunt about using the Teensy 3.1 without the Arduino IDE and building for the bare metal. I was very intrigued as the Arduino IDE was my only major beef with developing stuff for the Teensy 3.1 and I wanted to be able to do things without having to use the IDE. I read through the article and although it was geared towards windows, I decided to try to adapt it to my development style. There were a few things I wanted to do\:
* No additional code dependencies other than the teensyduino installation which I already had


* Use local binaries for compilation, not the ones included with teensyduino (it just felt uncomfortable to use theirs)


* Separation of src, obj, and bin directories


* Mixture of c and cpp files in the src directory


* Not needing to explicitly list the files in the src directory to compile


* Selective inclusion of features from the teensyduino installation



I have very little experience writing more complex Makefiles. When I say "complex" I am referring to makefiles which have the src, obj, bin separation and pull in objects from multiple sources. While this may not seem complex to many people, its something I have very little experience actually doing by hand (I would normally use a generator of some sort).

I'm writing this in the hope that those without mad Makefile skills, such as myself, can liberate themselves from the Arduino IDE when developing for an awesome platform like the Teensy 3.1.

**All code for this example can be found here\: **`https\://github.com/kcuzner/teensy31-blinky-bare-metal <https://github.com/kcuzner/teensy31-blinky-bare-metal>`_

Prerequisites
=============

As my first order of business, I located the arm-none-eabi binaries for my linux distribution. These can also be found for Windows as noted in Karl Lunt's article. Random sidenote\: I found `this <http://kunen.org/uC/gnu_tool.html>`_ description of why arm-none-eabi is called arm-none-eabi. Very informative. Anyway, for those who run archlinux, the following packages are needed\:
* arm-none-eabi-gcc (contains the compilers)


* arm-none-eabi-binutils (contains the linker, objdump, and other things for manipulating the binaries into hex files)


* make (we are using a makefile...)



Hopefully this gives a bit of a hint on what packages may need to be installed on other systems. For Windows, the compiler is `here <https://launchpad.net/gcc-arm-embedded/+download>`_ and make can be found `here <http://gnuwin32.sourceforge.net/packages/make.htm>`_ or by googling around. I haven't tested any of this on Windows and would advocate using Linux for this, but it shouldn't be hard to modify the Makefile for Windows.

My Flow
=======

For C and C++ development I have a particular flow that I like to follow. This is heavily influenced by my usage of Code\:\:Blocks and Visual Studio. I like to have a src directory where I put all of my sources, an include directory where I put all of my headers, an obj directory for all the obj, d, & lst files, and a bin directory for my executable output. I've always had such a hard time with raw Makefiles because I could never quite get that directory structure working. I was never quite satisfied with my feeble Makefile attempts which ended up placing the object files in the root directory where the sources had to be. This Makefile represents my first time I was ever able to actually have a real bin, obj, src structure that works.

Compiling object files to obj & looking in src for source
---------------------------------------------------------

A working description of this can be found in the Makefile in my github repository I mentioned earlier.

Makefiles work by defining a series of "targets" which have "dependencies". Every dependency can also be the name of a target and a target may have multiple ways of being resolved (this I never realized before). So, here is the parts of the Makefile which enable searching in src for both c and cpp and doing specific actions for each, comping them into the obj directory\:

code-block::

    # Project C & C++ files which are to be compiled
    CPP_FILES = $(wildcard $(SRCDIR)/*.cpp)
    C_FILES = $(wildcard $(SRCDIR)/*.c)

    # Change project C & C++ files into object files
    OBJ_FILES := $(addprefix $(OBJDIR)/,$(notdir $(CPP_FILES:.cpp=.o))) $(addprefix $(OBJDIR)/,$(notdir $(C_FILES:.c=.o)))

    # Example build target
    build: $(OUTPUTDIR)/$(PROJECT).elf

    # Linker invocation
    $(OUTPUTDIR)/$(PROJECT).elf: $(OBJ_FILES)
        @mkdir -p $(dir $@)
        $(CC) $(OBJ_FILES) $(LDFLAGS) -o $(OUTPUTDIR)/$(PROJECT).elf

    # C file compilation for some object file
    $(OBJDIR)/%.o : $(SRCDIR)/%.c
        @echo Compiling $<, writing to $@...
        @mkdir -p $(dir $@)
        $(CC) $(GCFLAGS) -c $< -o $@ > $(basename $@).lst

    # C++ file compilation for some object file
    $(OBJDIR)/%.o : $(SRCDIR)/%.cpp
        @mkdir -p $(dir $@)
        @echo Compiling $<, writing to $@...
        $(CC) $(GCFLAGS) -c $< -o $@

Each section above has a specific purpose and the order can be rather important. The first part uses $(wildcard ...) to pick up all of the C++ and C files. The CPP_FILES variable, for example, will become "src/file1.cpp src/file2.cpp src/etc.cpp" if we had "file1.cpp", "file2.cpp" and "etc.cpp" in the src directory. Similarly, the C_FILES would pick up any files in src with a c file extension. Next, the filenames are transformed into object filenames living in the obj directory. This is done by first changing the file extension of the files to .o using the $(CPP_FILES\:.cpp=.o) or $(C_FILES\:.c=.o) syntax. However, these files still look like they are in the src directory (e.g. src/file1.o) so the directory is next stripped off each file using $(nodir...). Removing the directory doesn't allow for a nested src directory, but that wasn't one of our objectives here. At this point, the files are just names with no directories (e.g. file1.o) and so the last step is to change them to live in the obj directory using $(addprefix $(OBJDIR)/,..). This completes our transformation, populating OBJ_FILES to look like "obj/file1.o obj/file2.o" etc.

The next part is where we take that list of object files and use them as dependencies for a target. Targets are defined by <target name>\: <dependency list> followed by a list of commands to execute after resolving the dependencies. IMPORTANT\: The list of commands needs to be indented by a tab (t) character. Spaces will not work (it will say something like "missing separator" with a line number). A target is anything that we pass into make. The default target is 'all'. The "dependencies" are files which much be "up to date" before the target is run.

In our example, we use $(OBJ_FILES) as a dependency of "$(OUTPUTDIR)/$(PROJECT).elf" which is required as a dependency of "build". This tells make that when we run "make build", it needs to try to resolve the dependency of "bin/<project>.elf" which in turn needs to resolve "obj/file1.o", "obj/file2.o", and "obj/etc.o" (going from our example in the previous paragraph). This is where the next couple targets come in. A target will only be executed if it can find some rule to resolve all of the dependencies. We will use "obj/file1.o" as an example here. There are 2 targets with that name, actually\: "$(OBJDIR)/%.o\: $(SRCDIR)/%.c" and "$(OBJDIR)/%.o\: $(SRCDIR)/%.cpp". It would be good to note that the target names here the exact same even though the dependencies are different. Now, how does "$(OBJDIR)%.o" match "obj/file1.o"? A Makefile does something called "pattern matching" when the % sign is used. It says "match something that looks like $(OBJDIR)<some file>.o" which our "obj/file1.o" happens to match. The cool part is that once the target name is resolved using a %, the dependencies get to use % to substitute the exact same thing. Thus, our % here is "file1", so it follows that its dependency must be "$(SRCDIR)/file1.c". Now, our example used "file1.cpp", not "file1.c" and this is where defining multiple targets with the same names but different dependencies comes in. A target will only be executed if the dependencies can be resolved to either an actual file and/or another target. Our first target won't be a match since it says that the source file should be a C file. So, it goes to the next target that matches the name which has a dependency of "$(SRCDIR)/file1.cpp". This one matches, and so commands following that target are executed.

When executing a target ("$(OBJDIR)/%.o\: $(SRCDIR)/%.cpp" in our example), there are some special variables which are available for use. These are described `here <https://www.gnu.org/software/make/manual/html_node/Automatic-Variables.html>`_, but I will discuss two important ones that I used\: $@ and $<. $@ is the name of the target (so, "obj/file.o" in our case) and $< is the name of the first dependency ("src/file.cpp" in our case). This lets us pass these arguments into the commands that we execute. Our Makefile will first create the obj directory by calling "mkdir -p $(dir $@)" which is translated into "mkdir -p obj" since $(dir $@) will give us "obj". Next, we actually compile the $< (which is translated to "src/file.cpp"), outputting it to $< which is translated to "obj/file.o".

Outputting everything to bin
----------------------------

Compared to the pattern matching and multiple target definitions that we discussed above, this is comparatively simple. We simply get to prefix all of our "binary" output files with some directory which is set as $(OUTPUTDIR) in my Makefile. Here is an example\:

code-block::

    all:: $(OUTPUTDIR)/$(PROJECT).hex $(OUTPUTDIR)/$(PROJECT).bin stats dump

    $(OUTPUTDIR)/$(PROJECT).bin: $(OUTPUTDIR)/$(PROJECT).elf
        $(OBJCOPY) -O binary -j .text -j .data $(OUTPUTDIR)/$(PROJECT).elf $(OUTPUTDIR)/$(PROJECT).bin

    $(OUTPUTDIR)/$(PROJECT).hex: $(OUTPUTDIR)/$(PROJECT).elf
        $(OBJCOPY) -R .stack -O ihex $(OUTPUTDIR)/$(PROJECT).elf $(OUTPUTDIR)/$(PROJECT).hex

    #  Linker invocation
    $(OUTPUTDIR)/$(PROJECT).elf: $(OBJ_FILES)
        @mkdir -p $(dir $@)
        $(CC) $(OBJ_FILES) $(LDFLAGS) -o $(OUTPUTDIR)/$(PROJECT).elf

    stats:

    dump:

We see here that any output that we are creating as a result of the compilation (.elf, .hex, .bin) is going to end up in $(OUTPUTDIR). Futher, we see that our "all" target asks the Makefile to create both a bin file and a hex file along with two other targets called "stats" and "dump". These are just scripts that execute the "size" and "objdump" commands on our bin file.

Using Teensyduino without compiling everything
==============================================

This was by far the most frustrating part to get working. Everything about the makefiles was readily available online, with some serious googling. However, getting things to actually compile was a little different story.

The thing that makes this complex is the fact that it seems the Teensyduino libraries were not designed to be used independently of each other. I will cover, in order, what steps I had to take in order to get this to work.

The most important file we need is called "mk20dx128.c". This sets up a lot of things relating to interrupts along with the Phase Lock Loop (PLL) which controls the speed of the Teensy's processor. Without this configuration, we don't get interrupts and the processor runs at a pitiful 16Mhz. The only problem is that "mk20dx128" references a few functions that are either part of the standard library and not used often (making them difficult to search for) or are defined in other files, increasing our dependency count.

My first mistake was explicitly using the linker to link all of my object files (wait...aren't we supposed to use the linker? Read on.). Since arm-none-eabi is not dependent on a specific architecture, it doesn't know which standard library (libc) to use. This results in an undefined reference to "__libc_init_array()", a function used during the initialization phase of a program which is not often invoked in code outside the standard library itself. mk20dx128.c uses this function in its custom startup code which prepares the processor for running our program. To solve this, I wanted to tell the linker that I was using a cortex-m4 cpu so that it would know which libc to include and thereby resolve the reference. However, this proved difficult to do when directly invoking the linker. Instead, I took a hint from the Makefile that comes with Teensyduino and used the following command to link the objects\:

code-block::

    $(CC) $(OBJ_FILES) $(LDFLAGS) -o $(OUTPUTDIR)/$(PROJECT).elf

Which more or less translates to (using our example from earlier)\:

code-block::

    arm-none-eabi-gcc obj/file1.o obj/file2.o obj/etc.o obj/mk20dx128.o $(LDFLAGS) -o bin/$(PROJECT).elf

We would have thought that we should be using arm-none-eabi-ld instead of arm-none-eabi-gcc. However, by using arm-non-eabi-gcc I was able to pass the argument "-mcpu=cortex-m4" which then allowed GCC to instruct the linker which standard library to use. Wonderful, right? So all of our problems are solved? Not yet.

The next thing is that mk20dx128.c has a lot of external dependencies. It uses a function defined in pins_teensy.c which in turn requires functions defined in both analog.c and usb_dev.c which opens another can of worms. Ugh. I didn't want this many dependencies and I couldn't see a way to escape compiling nearly the entire Teensyduino library just to run my simple blinking program. Then, it dawned on me\: I could use the same technique that mk20dx128.c uses to define its ISRs to "define" the functions that pins_teensy.c was calling that I didn't really want. So, I made a file called "shim.c" which contained the following\:

code-block::

    void unused_void(void) { }

    void usb_init(void) __attribute__ ((weak, alias("unused_void")));

I decided that I would include "yield.c" and "analog.c" since those weren't too big. This left just the usb stuff. The only function that was actually called from pins_teensy.c was "usb_init". What the above statement says to the compiler is "I am defining usb_init(void) here (which points to unused_void(void)) unless you find another definition of usb_init(void) somewhere". The "weak" attribute makes this "strong" symbol of usb_init a "weak" symbol reference to which is basically the same as just making a declaration (in contrast to the definition a function, which is usually a strong reference). Sidenote\: A program can have any number of weak symbol references to a specific function/variable (declarations), but only one strong symbol reference (definition) of that function/variable. The "alias" attribute allows us to say "when I say usb_init I really mean unused_void". The end result of this is that if nobody defines usb_init(void) anywhere, as would be situation if I were to decide not to include usb_dev.c, any calls to usb_init(void) will actually call unused_void(void). However, if somebody did define usb_init(void), my definition of usb_init would be ignored in favor of using their definition. This lets me include usb support in the future if I wanted to. Isn't that cool? That fixed all of my reference issues and let me actually build the project.

Conclusion
==========

Armed with my new Makefile and a better understanding of how the Teensy 3.1 works from a software perspective, I managed to compile and upload my "blinky" program which just blinks the onboard LED (pin 13) on and off every 1/4 second. The overall program size was 3% of the total space, which is much more reasonable compared to the 10-20% it was taking when compiled using the Arduino IDE.

Again, all files from this escapade can be found here\: `https\://github.com/kcuzner/teensy31-blinky-bare-metal <https://github.com/kcuzner/teensy31-blinky-bare-metal>`_

.. rstblog-settings::
   :title: Teensy 3.1 Bare-Metal
   :date: 2014/04/28
   :url: 2014/04/28/teensy-3-1-bare-metal