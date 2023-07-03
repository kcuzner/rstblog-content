As my final installment for the posts about my `LED Wristwatch project <http://kevincuzner.com/2017/04/18/the-led-wristwatch-a-more-or-less-completed-project/>`_ I wanted to write about the self-programming bootloader I made for an STM32L052 and describe how it works. So far it has shown itself to be fairly robust and I haven't had to get out my STLink to reprogram the watch for quite some time.

The main object of this bootloader is to facilitate reprogramming of the device without requiring a external programmer. There are two ways that a microcontroller can accomplish this generally\:
#. Include a binary image in every compiled program that is copied into RAM and runs a bootloader program that allows for self-reprogramming.


#. Reserve a section of flash for a bootloader that can reprogram the rest of flash.



Each of these ways has their pros and cons. Option 1 allows for the user program to use all available flash (aside from the blob size and bootstrapping code). It also might not require a relocatable interrupt vector table (something that some ARM Cortex microcontrollers lack). However, it also means that there is no recovery without using JTAG or SWD to reflash the microcontroller if you somehow mess up the switchover into the bootloader. Option 2 allows for a fairly fail-safe bootloader. The bootloader is always there, even if the user program is not working right. So long as the device provides a hardware method for entering bootloader mode, the device can always be recovered. However, Option 2 is difficult to update (you have to flash it with a special program that overwrites the bootloader), wastes unused space in the bootloader-reserved section, and also requires some features that not all microcontrollers have.

Because the STM32L052 has a large amount of flash (64K) and implements the vector-table-offset register (allowing the interrupt vector table to be relocated), I decided to go with Option 2.

**Example code for this post can be found here\:**


`**https\://github.com/kcuzner/led-watch** <https://github.com/kcuzner/led-watch>`_



Contents
========


.. rstblog-break::

* `Parts of a bootloader <parts>`_


* `Bootloader entry and exit <enter-exit>`_


* `Self-programming via USB <self-programming>`_


* `Considerations for linking the application <linking>`_


* `Host software <host>`_


* `Conclusion <conclusion>`_




.. _parts::

Parts of a bootloader
=====================

There's a few pieces to the bootloader that I'm going to describe here which are necessary for its function.
* Since the bootloader runs first\: The ability to detect whether or not the bootloader should run. Also a way for the application to enter bootloader mode.


* The ability to write to flash. And since this bootloader allows any program to be written\:


* Some way to transfer the program into the bootloader.




.. _enter-exit::

Bootloader Entry and Exit
=========================

When the watch first boots, the bootloader is going to be the first thing that runs. Not all bootloaders work like this, but this is one of the simplest ways to get things rolling.

First, there's a few #defines and global variables that it would be good to know about for some context\:

code-block::

    #define EEPROM_SECTION ".eeprom,\"aw\",%nobits//" //a bit of a hack to prevent .eeprom from being programmed
    #define _EEPROM __attribute__((section (EEPROM_SECTION)))

    /**
     * Mask for RCC_CSR defining which bits may trigger an entry into bootloader mode:
     * - Any watchdog reset
     * - Any soft reset
     * - A pin reset (aka manual reset)
     * - A firewall reset
     */
    #define BOOTLOADER_RCC_CSR_ENTRY_MASK (RCC_CSR_WWDGRSTF | RCC_CSR_IWDGRSTF | RCC_CSR_SFTRSTF | RCC_CSR_PINRSTF | RCC_CSR_FWRSTF)

    /**
     * Magic code value to make the bootloader ignore any of the entry bits set in
     * RCC_CSR and skip to the user program anyway, if a valid program start value
     * has been programmed.
     */
    #define BOOTLOADER_MAGIC_SKIP 0x3C65A95A

    static _EEPROM struct {
        uint32_t magic_code;
        union {
            uint32_t *user_vtor;
            uint32_t user_vtor_value;
        };
    } bootloader_persistent_state;



There are a few things that can be gathered from this\:
* We are going to be using the EEPROM. I made a convenient _EEPROM macro that makes a variable be placed into the EEPROM portion of memory.


* There are some reset conditions which will cause the bootloader to enter bootloader mode no matter what. These reset conditions are checked by masking the CSR register with this mask.


* We have some persistent state that consists of a "magic code" and the user program's VTOR register value. This is all stored to EEPROM.



The first thing that the bootloader does is ask the following question to determine if it should run the user application\:

code-block::

    void bootloader_init(void)
    {
        //if the prog_start field is set and there are no entry bits set in the CSR (or the magic code is programmed appropriate), start the user program
        if (bootloader_persistent_state.user_vtor &&
                (!(RCC->CSR & BOOTLOADER_RCC_CSR_ENTRY_MASK) || bootloader_persistent_state.magic_code == BOOTLOADER_MAGIC_SKIP))
        {
    ...

Reading here, we can see that if there is a user_vtor value and there was either no reset condition forcing an entry into bootloader mode or the magic number was programmed to our state, we're going to continue and load the user program rather than staying in bootloader mode.

The most important part here is the CSR check. This is what gives this bootloader some "recoverability" facilities. Basically if there's any reset except a power-on reset, it will assume that there's a problem with the application program and that it shouldn't execute it. It will stay in bootloader mode. This aids in writing application firmware since a hard fault followed by a WDT reset will result in the microcontroller safely entering bootloader mode. The downside to this is that it could make debugging difficult if you are trying to figure out why something like a hard fault occurred in the first place (though I could argue that you should be using the SWD dongle anyway to debug your program).

The next thing to explain here is probably the purpose of this magic_code value. The idea here is to have some number that is highly unlikely to appear randomly in the EEPROM which we will use to "override" the CSR check. This occurs when the program is finished being flashed for the first time. The bootloader itself will execute a soft-reset to start the newly flashed user program (which is something that the CSR check will abort execution of the user program for).

After the bootloader determines that it needs to run the user's program, it will execute the following\:

code-block::

            if (bootloader_persistent_state.magic_code)
                nvm_eeprom_write_w(&bootloader_persistent_state.magic_code, 0);
            __disable_irq();
            uint32_t sp = bootloader_persistent_state.user_vtor[0];
            uint32_t pc = bootloader_persistent_state.user_vtor[1];
            SCB->VTOR = bootloader_persistent_state.user_vtor_value;
            __asm__ __volatile__("mov sp,%0\n\t"
                    "bx %1\n\t"
                    : /* no output */
                    : "r" (sp), "r" (pc)
                    : "sp");
            while (1) { }


The first step here is to reset the magic_code value, since this is a one-time CSR-check override. Next, interrupts are disabled and some steps are taken to start executing the user program\:
#. The user_vtor value is dereferenced and we read values directly from the previously programmed user application. For Cortex-M binaries, the interrupt table's first two words are the initial stack pointer and the location of the reset interrupt. By dereferencing the VTOR value we read the user program like an array, extracting the first and second words to store as the future stack pointer and future program counter (since we want to start at the user program's reset entry point).


#. The actual VTOR register is written.


#. Some inline assembly sets the stack pointer and then branches to the user program's reset vector.



After these steps are performed, the user program will begin to run. Since this whole process occurs from the initial reset state of the processor and doesn't modify any clock enable values, the user program runs in the same environment that it would if it were the program being executed as reset.

In summary, the bootloader is entered immediately upon device reset. It then decides to either run the user program (exiting the bootloader) or continue on in bootloader mode based on the value of the CSR register.

.. _self-programming::

Self-programming via USB
========================

One main goal I had with this bootloader is that it should be driverless and cross-platform. To facilitate this, the bootloader enumerates as a USB Human Interface Device. Here is my report descriptor for the bootloader\:

code-block::

    static const USB_DATA_ALIGN uint8_t hid_report_descriptor[] = {
        HID_SHORT(0x04, 0x00, 0xFF), //USAGE_PAGE (Vendor Defined)
        HID_SHORT(0x08, 0x01), //USAGE (Vendor 1)
        HID_SHORT(0xa0, 0x01), //COLLECTION (Application)
        HID_SHORT(0x08, 0x01), //  USAGE (Vendor 1)
        HID_SHORT(0x14, 0x00), //  LOGICAL_MINIMUM (0)
        HID_SHORT(0x24, 0xFF, 0x00), //LOGICAL_MAXIMUM (0x00FF)
        HID_SHORT(0x74, 0x08), //  REPORT_SIZE (8)
        HID_SHORT(0x94, 0x40), //  REPORT_COUNT(64)
        HID_SHORT(0x80, 0x02), //  INPUT (Data, Var, Abs)
        HID_SHORT(0x08, 0x01), //  USAGE (Vendor 1)
        HID_SHORT(0x90, 0x02), //  OUTPUT (Data, Var, Abs)
        HID_SHORT(0xc0),       //END_COLLECTION
    };



Our reports are very simple\: We have a 64-byte IN report and a 64-byte OUT report. Although the report descriptor only describes these as simple arrays, the bootloader will actually type-pun them into something a little more structured as follows\:

code-block::

    static union {
        uint32_t buffer[16];
        struct {
            uint32_t last_command;
            uint32_t flags;
            uint32_t crc32_lower;
            uint32_t crc32_upper;
            uint8_t data[48];
        };
    } in_report;

    static union {
        uint32_t buffer[16];
        struct {
            uint32_t command;
            uint32_t *address;
            uint32_t crc32_lower;
            uint32_t crc32_upper;
        };
    } out_report;


To program the device, this bootloader implements a state machine that interprets sequences of OUT reports and issues IN reports as follows\:
* The status report\: At certain points, the bootloader will issue IN reports back to the host which contain the last command received, any error flags, and some CRC32 values which are used to ensure we don't swap upper and lower pages when transferring flash pages back to the host.


* The reset command\: The host issues an OUT report just containing 0x00000000 as its first four bytes. This resets the bootloader state machine and the bootloader will issue a single status report. In general, this command is to be executed three times in a row, since that will reset the bootloader state machine, even if it is in the middle of a programming cycle.


* The write command\: The host issues an OUT report with the command word set to 0x00000080. It also contains an address (the 6 lowest bits are ignored since flash writes always occur in groups ("pages") of 128 bytes) and two CRC32s. The host will then issue two OUT reports, each containing 64 bytes of data to be written to the flash. The CRC32 previously sent are then used to verify that the two OUT reports were received in the correct order. The reason for this stems from how most OS's implement USB HID devices\: There is no concept of exclusive access. Two separate host programs could be issuing reports (or reading reports) to the device. If this somehow occurs, the bootloader state machine could see interleaved OUT reports for unrelated commands. The CRC32 check aims to prevent this by asserting that the two reports following the initial OUT report are the ones intended to be interpreted as pages to be written to the flash. Once two valid OUT reports are received, the bootloader will erase the user_vtor value (basically invalidating the previously programmed user application) and begin the writing process. Once the flash write process is complete, the bootloader will issue an status IN report.


* The read command\: The host issues an OUT report with the command word set to 0x00000040. It also contains the address to read (again, the lowest 6 bits are ignored). The bootloader will then issue two IN reports containing the contents of the page. A status IN report will immediately follow.


* The exit command\: The host issues an OUT report with the command word set to 0x000000C3. The address field is set to the location of the interrupt table at the start of the program. This is programmed to the persistent structure in the EEPROM so that the bootloader knows where to start programming. If everything is successful, the magic word is programmed and the bootloader resets into the user program.


* The abort command\: The host issues an OUT report with the command word set to 0x0000003E. If the user_vtor value hasn't been erased (i.e. a write command hasn't been issued yet), this programs the magic word and resets into the user program.



A more detailed description of this protocol can be found at `https\://github.com/kcuzner/led-watch/blob/master/bootloader/README.md <https://github.com/kcuzner/led-watch/blob/master/bootloader/README.md>`_.

I'll cover briefly the process for writing the flash on the STM32. On my particular model, flash pages are 128 bytes and writes are always done in 64-byte groups. This is fairly standard for NOR flash that is seen in microcontrollers. When self-programming, one of the main issues I ran into was that the processor is not allowed to access the flash memory while a flash write is occurring. This is a problem since the flash write process requires the program to poll registers and wait for events to finish. Since this code by default resides in the flash memory, that will cause the write to fail. The solution to this is fairly straightforward\: We have to ensure that the code that actually performs flash writes lives in RAM. Since RAM is executable on the STM32, this is just as simple as requesting the linker to locate the functions in RAM. Here's my code that does flash erases and writes\:

code-block::

    /**
     * Certain functions, such as flash write, are easier to do if the code is
     * executed from the RAM. This decoration relocates the function there and
     * prevents any inlining that might otherwise move the function to flash.
     */
    #define _RAM __attribute__((section (".data#"), noinline))

    /**
     * RAM-located function which actually performs page erases.
     *
     * address: Page-aligned address to erase
     */
    static _RAM bool nvm_flash_do_page_erase(uint32_t *address)
    {
        //erase operation
        FLASH->PECR |= FLASH_PECR_ERASE | FLASH_PECR_PROG;
        *address = (uint32_t)0;
        //wait for completion
        while (FLASH->SR & FLASH_SR_BSY) { }
        if (FLASH->SR & FLASH_SR_EOP)
        {
            //completed without incident
            FLASH->SR = FLASH_SR_EOP;
            return true;
        }
        else
        {
            //there was an error
            FLASH->SR = FLASH_SR_FWWERR | FLASH_SR_PGAERR | FLASH_SR_WRPERR;
            return false;
        }
    }

    /**
     * RAM-located function which actually performs half-page writes on previously
     * erased pages.
     *
     * address: Half-page aligned address to write
     * data: Array to 16 32-bit words to write
     */
    static _RAM bool nvm_flash_do_write_half_page(uint32_t *address, uint32_t *data)
    {
        uint8_t i;

        //half-page program operation
        FLASH->PECR |= FLASH_PECR_PROG | FLASH_PECR_FPRG;
        for (i = 0; i < 16; i++)
        {
            *address = data[i]; //the actual address written is unimportant as these words will be queued
        }
        //wait for completion
        while (FLASH->SR & FLASH_SR_BSY) { }
        if (FLASH->SR & FLASH_SR_EOP)
        {
            //completed without incident
            FLASH->SR = FLASH_SR_EOP;
            return true;
        }
        else
        {
            //there was an error
            FLASH->SR = FLASH_SR_FWWERR | FLASH_SR_NOTZEROERR | FLASH_SR_PGAERR | FLASH_SR_WRPERR;
            return false;

        }
    }


The other thing to discuss about self-programming is the way the STM32 protects itself against erroneous writes. It does this by "locking" and "unlocking" using writes of magic values to certain registers in the FLASH module. The idea is that the flash should only be unlocked for just the amount of time needed to actually program the flash and then locked again. This prevents program corruption due to factors like incorrect code, ESD causing the microcontroller to wig out, power loss, and other things that really can't be predicted. I do the following to actually execute writes to the flash (note how the following code uses the _RAM-located functions I noted earlier)\:

code-block::

    /**
     * Unlocks the PECR and the flash
     */
    static void nvm_unlock_flash(void)
    {
        nvm_unlock_pecr();
        if (FLASH->PECR & FLASH_PECR_PRGLOCK)
        {
            FLASH->PRGKEYR = 0x8c9daebf;
            FLASH->PRGKEYR = 0x13141516;
        }
    }

    /**
     * Locks all unlocked NVM regions and registers
     */
    static void nvm_lock(void)
    {
        if (!(FLASH->PECR & FLASH_PECR_PELOCK))
        {
            FLASH->PECR |= FLASH_PECR_OPTLOCK | FLASH_PECR_PRGLOCK | FLASH_PECR_PELOCK;
        }
    }


    bool nvm_flash_erase_page(uint32_t *address)
    {
        bool result = false;

        if ((uint32_t)address & 0x7F)
            return false; //not page aligned

        nvm_unlock_flash();
        result = nvm_flash_do_page_erase(address);
        nvm_lock();
        return result;
    }

    bool nvm_flash_write_half_page(uint32_t *address, uint32_t *data)
    {
        bool result = false;

        if ((uint32_t)address & 0x3F)
            return false; //not half-page aligned

        nvm_unlock_flash();
        result = nvm_flash_do_write_half_page(address, data);
        nvm_lock();
        return result;
    }

More information about these magic numbers and the unlock-lock sequencing can be found in the documentation for the PRGKEYR register in the FLASH module on the STM32L052.

By combining the bootloader state machine with these methods for writing the flash, we can build a self-programming bootloader. Internally, it also checks to make sure we aren't trying to overwrite anything we shouldn't by ensuring that the write only applies to areas of user flash, not to the bootloader's reserved segment. In addition, it also verifies every page written against the original data to be programmed.

I do recommend reading through the code for the bootloader state machine (just bootloader.c in the bootloader directory). The state machine is table-based (see the "fsm" constant table variable and the "bootloader_tick" function) and I find that to be a very maintainable model for writing state machines in C.

.. _linking::

Considerations for linking the application
==========================================

One big thing we haven't yet covered is how exactly the user application needs to be changed in order to be compatible with the bootloader. Due to how the bootloader is structured (it just lives in the first bit of flash) and how it is entered (any reset other than power-on will enter bootloader mode), the only real change needed to make a user program compatible is to relocate where the linker script places the user program in flash (leaving the first section of it blank). In my linker script for the LED watch, I changed the MEMORY directive to read as follows\:

code-block::

    MEMORY
    {
        FLASH (RX) : ORIGIN = 0x08002000, LENGTH = 56K
        RAM (W!RX)  : ORIGIN = 0x20000000, LENGTH = 8K
        PMA (W)  : ORIGIN = 0x40006000, LENGTH = 512 /* 256 x 16bit */
    }

The flash segment has been shorted from 64K to 56K and the ORIGIN has been moved up to 0x08002000. The first 8KB of flash are now reserved for the bootloader. The bootloader is linked just like any other program, with the ORIGIN at 0x08000000, but its LENGTH is set to 8K instead.

When the user program wishes to enter bootloader mode, it just needs to issue a soft reset. The LED watch has a command for this that is issued over USB and just executes the following when it receives that command\:

code-block::

    //entering bootloader mode with a simple soft reset
    NVIC_SystemReset();


Very simple, very easy.

.. _host::

Host software
=============

The host software is written in python and uses pyhidapi to talk to the bootloader. It really is nothing complicated, since it just reads intel hex files and dumps them into the watch by operating the state machine. When it is finished, it tells the bootloader the location of the start of the program so that it can read the initial stack pointer and the address of the reset function by issuing the "exit" command. This also boots into the user program. Pretty much all the heavy lifting and "interesting" stuff for a bootloader happens in the bootloader itself, rather than in host software.

One small hack is that the host software does hardcode where it believes the program should start (address 0x08002000). One possible resolution for this hack is to take elf files instead of intel hex files, or just assume the lowest address in the hex file is the starting point.

.. _conclusion::

Conclusion
==========

This is my first bootloader that I've written for one of my projects. There were challenges getting it to work at first, but I hope that I've shown it isn't an incredibly complex thing to write. I actually got better performance flashing over USB than over SWD, so that is an additional win for writing this and if I didn't use the SWD for debugging so much I would probably always use a bootloader like this on my projects.

I hope this has been a useful read and I do encourage actually checking out the source code, since I've been pretty brief about some parts of the bootloader.

.. rstblog-settings::
   :title: Building a USB bootloader for an STM32
   :date: 2018/06/28
   :url: /2018/06/28/building-a-usb-bootloader-for-an-stm32