.. rstblog-settings::
   :title: Bootloader for ARM Cortex-M0: No VTOR
   :date: 2018/11/13
   :url: /2018/11/13/bootloader-for-arm-cortex-m0-no-vtor
   :tags: arm-programming, arm-cortex, bootloader, hardware, nvic, programming, stm32, vtor

In my most recent project I selected an ARM Cortex-M0 microcontroller (the STM32F042). I soon realized that there is a key architectural piece missing from the Cortex-M0 which the M0+ does not have\: The vector table offset register (VTOR).

I want to talk about how I overcame the lack of a VTOR to write a USB bootloader which supports a semi-safe fallback mode.
**The source for this post can be found here (look in the "bootloader" folder)\:** 


`https\://github.com/kcuzner/midi-fader/tree/master/firmware <https://github.com/kcuzner/midi-fader/tree/master/firmware>`__



.. rstblog-break::


**Table of contents\:** 


* `What is the VTOR? <what-is-vtor>`__


* `Bootloaders and the VTOR <bootloader-vtor>`__


* `Dealing with an absent VTOR <no-vtor>`__ (TL;DR\: look here)


  * `Debugging the user program <debugging>`__





* `Conclusion <conclusion>`__




.. _what-is-vtor:

What is the VTOR?
=================


Near the heart of the ARM Cortex is the NVIC, or Nested Vector Interrupt Controller. This is used for prioritizing peripheral interrupts (I2C byte received, USB transaction complete, etc) and core signals (hard fault, system timer tick, etc) while managing the code which is executed in response. The NVIC works by using a lookup table at a specific location to determine what code to execute. As an example, the interrupt table for the STM32F042 looks something like this\:

.. list-table
   :widths: auto
   :header-rows: 1
   * - Address

     - Description
   * - 0x00000000

     - Address of initial stack offset in RAM

   * - 0x00000004

     - Reset handler address

   * - 0x00000008

     - NMI handler address

   * - 0x0000000C

     - HardFault handler address

   * - 0x00000010-0x00000028

     - Reserved (other Cortex-M processors have more items here)

   * - 0x0000002C

     - SVCall handler address

   * - 0x00000030-0x00000034

     - Reserved (same as other reserved fields)

   * - 0x00000038

     - PendSV handler address

   * - 0x0000003C

     - System tick handler address

   * - 0x00000040

     - STM32 WWDG handler address

   * - 0x00000044

     - STM32 PVD_VDDIO2 handler address

   * - 0x00000048

     - STM32 RTC handler address

   * - 0x0000004C

     - STM32 FLASH handler address

   * - ...etc...




When an interrupt occurs, the NVIC will examine this table, read the handler address from it, push some special information onto the stack (the exception frame), and then execute the handler. This exact sequence is fairly complex, but here are some resources if you're interested in learning more\:


* `http\://users.ece.utexas.edu/~valvano/Volume1/E-Book/C12_Interrupts.htm <http://users.ece.utexas.edu/~valvano/Volume1/E-Book/C12_Interrupts.htm>`__


* `http\://www.eng.auburn.edu/~nelson/courses/elec5260_6260/slides/ARM%20STM32F407%20Interrupts.pdf <http://www.eng.auburn.edu/~nelson/courses/elec5260_6260/slides/ARM%20STM32F407%20Interrupts.pdf>`__ (slide 5)


* `http\://infocenter.arm.com/help/topic/com.arm.doc.dui0553a/Babefdjc.html <http://infocenter.arm.com/help/topic/com.arm.doc.dui0553a/Babefdjc.html>`__ (ARM Cortex-M4 documentation on the exception frame)



For any program meant to run on an ARM Cortex processor there'll be some assembly (or maybe C) that looks like this (this one was provided by ST's CMSIS implementation for the STM32F042)\:

.. code-block:: asm
   :height-limit:

      .section .isr_vector,"a",%progbits
     .type g_pfnVectors, %object
     .size g_pfnVectors, .-g_pfnVectors


   g_pfnVectors:
     .word  _estack
     .word  Reset_Handler
     .word  NMI_Handler
     .word  HardFault_Handler
     .word  0
     .word  0
     .word  0
     .word  0
     .word  0
     .word  0
     .word  0
     .word  SVC_Handler
     .word  0
     .word  0
     .word  PendSV_Handler
     .word  SysTick_Handler
     .word  WWDG_IRQHandler                   /* Window WatchDog              */
     .word  PVD_VDDIO2_IRQHandler             /* PVD and VDDIO2 through EXTI Line detect */
     .word  RTC_IRQHandler                    /* RTC through the EXTI line    */
     .word  FLASH_IRQHandler                  /* FLASH                        */
     .word  RCC_CRS_IRQHandler                /* RCC and CRS                  */
     .word  EXTI0_1_IRQHandler                /* EXTI Line 0 and 1            */
   ...

Then in my linker script I have the "SECTIONS" portion start out like this\:

.. code-block:: c
   :height-limit:

   SECTIONS
   {
       /* General code */
       .text :
       {
           _flash_start = .;
           . = ALIGN(4);
           /* At beginning of flash is:
            *
            * Required:
            * 0x0000 Initial stack pointer
            * 0x0004 Reset Handler
            *
            * Optional:
            * 0x0008 and beyond: NVIC ISR Table
            */
           KEEP(*(.isr_vector))
           . = ALIGN(4);
           *(.text)
           *(.text*)
           *(.glue_7)
           *(.glue_7t)

           /* C startup support */
           /* TODO: Convert to -nostartfiles for maximum DIY */
           *(.eh_frame)
           KEEP(*(.init))
           KEEP(*(.fini))
       } > FLASH
   ...

The assembly snippet creates the table for the NVIC (g_pfnVectors in this example) and assigns it to the ".isr_vector" section. The linker script then locates this section right at the beginning of the flash (the "KEEP(\*(.isr_vector))" right at the beginning after some variable declarations). When the program is compiled what I end up with it something that looks like this (this is an assembly dump of the beginning of one of my binaries)\:

.. code-block:: asm
   :height-limit:

   Disassembly of section .text:

   08000000 <_flash_start>:
    8000000:	20001800 	andcs	r1, r0, r0, lsl #16
    8000004:	08001701 	stmdaeq	r0, {r0, r8, r9, sl, ip}
    8000008:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    800000c:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000010:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000014:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000018:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    800001c:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000020:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000024:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000028:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    800002c:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000030:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000034:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000038:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    800003c:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000040:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000044:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000048:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    800004c:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000050:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000054:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000058:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    800005c:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000060:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000064:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000068:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    800006c:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000070:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000074:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000078:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    800007c:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000080:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000084:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000088:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    800008c:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000090:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000094:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    8000098:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    800009c:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    80000a0:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    80000a4:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    80000a8:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    80000ac:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    80000b0:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    80000b4:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    80000b8:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}
    80000bc:	080005af 	stmdaeq	r0, {r0, r1, r2, r3, r5, r7, r8, sl}

   080000c0 <bootloader_tick>:
    80000c0:	4a0d      	ldr	r2, [pc, #52]	; (80000f8 <bootloader_tick+0x38>)
    80000c2:	2300      	movs	r3, #0
    80000c4:	0011      	movs	r1, r2
    80000c6:	b570      	push	{r4, r5, r6, lr}
    80000c8:	4c0c      	ldr	r4, [pc, #48]	; (80000fc <bootloader_tick+0x3c>)
   ...

For the first several 32-bit words I have created a bunch of function pointers which make up the table that the NVIC will read. After that table, the actual code starts.

So, what is the VTOR? In some ARM Cortex architectures (I know at least the ARM Cortex-M0+, ARM Cortex-M3, and ARM Cortex-M4 support this) there is a register located at address `0xE000ED08 <http://infocenter.arm.com/help/topic/com.arm.doc.dui0552a/Ciheijba.html>`__ called the "Vector Table Offset Register". This is a 7-bit aligned address (so its 7 LSBs must be zero) which points to the location of this interrupt vector table. On boot this register contains 0x00000000 and so when power comes up, the handler whose address lives at 0x00000004 is executed to handle the reset. Later on, the program might modify the VTOR so that it points at some other location in memory. For an example, let's say 0x08008000. After that point, the NVIC will look up the addresses for each handler relative to that address. So if an SVCall exception occurred the NVIC would read 0x0800802C to determine the address of the handler to call.

One thing you may have noticed at this point is that my assembly dump earlier had everything living relative to address 0x08000000. However, I said that that the VTOR's reset value was 0x00000000. So, how does the STM32's ARM core know where to find the table? All STM32's I've seen so far implement a "boot remapping" feature which uses the physical "BOOT0" pin to map the flash (which starts at 0x08000000) onto the memory space starting at 0x00000000 like so (may vary slightly by STM32)\:

.. list-table
   :widths: auto
   :header-rows: 1
   * - BOOT0 pin

     - Result
   * - 0

     - 0x08000000 (Main Flash Memory) mapped onto 0x00000000

   * - 1

     - System Memory (which is a ROM usually containing some bootloader supplied by ST) is mapped onto 0x00000000




Some STM32s have support for extra modes like mapping the SRAM (address 0x20000000) onto 0x00000000. So although the VTOR's default value is 0x00000000, since the STM32 is remapping 0x08000000 into that space the ARM Cortex core sees the contents of the flash when it loads information from locations relative to 0x00000000 if the BOOT0 pin is tied low.

.. _bootloader-vtor:

Bootloaders and the VTOR
========================


At this point we can talk about how bootloaders would use the VTOR. In my `last post on the subject <http://kevincuzner.com/2018/06/28/building-a-usb-bootloader-for-an-stm32/>`__, I didn't really talk extensively about interrupts beyond mentioning that the VTOR is overwritten as part of the process of jumping to the user program. The reason this is done is so that after the bootloader has decided to transfer execution to the user program that interrupts executed in the program are directed to the handlers dictated by the user program. Ideally, the user program doesn't even need to worry about the fact that its running in a boot-loaded manner.

On a microcontroller with a separate bootloader and user program the flash is partitioned into two segments\: The bootloader which *always* lives right at the beginning of flash so that the STM32 boots into the bootloader and the user program which lives much further down in the flash. I usually put my user programs at around the 8KB mark since the (inefficient and clumsy) hobbyist bootloaders i write tend to use just a little over 4K of the flash. When the bootloader runs it performs the following sequence\:


#. Determine if a user program exists. If the user program does not exist, start running the main bootloader program and abort this sequence.


#. Disable interrupts (important!)


#. Set the VTOR register to the start of the user program (which just so happens to be the location of the user program's vector table, since the table lives right at the beginning of the flash image of the program).


#. Read the address of the stack pointer from the first word of the user program.


#. Read the reset handler address from the second word of the user program.


#. Set the stack pointer and jump to the reset handler.



So long as the user program doesn't go and mess with the VTOR, any interrupts that occur after the user program re-enables interrupts will cause the NVIC to use the user program's table to determine where the handlers are. Isn't that awesome?

There is one step that the user program has to do, however. It needs to properly offset all of its addresses in the flash. As I mentioned in my previous post about bootloaders this is pretty easy to do in the linker script by just tricking it into thinking that the flash starts at the beginning of the user program partition (example on a 32K microcontroller)\:

.. code-block:: c

   _flash_origin = 0x08002000;
   _flash_length = 24K;

   MEMORY
   {
       FLASH (RX) : ORIGIN = _flash_origin, LENGTH = _flash_length
       RAM (W!RX)  : ORIGIN = 0x20000000, LENGTH = 6K
   }


The user program is now tricked into thinking that flash starts at 0x08002000 and is only 24K. We can see that this was successful if we take a look at the beginning of the disassembly of a compiled program\:

.. code-block:: asm
   :height-limit:

   Disassembly of section .text:

   08002000 <_flash_start>:
    8002000:	20001800 	andcs	r1, r0, r0, lsl #16
    8002004:	08004141 	stmdaeq	r0, {r0, r6, r8, lr}
    8002008:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    800200c:	08003c29 	stmdaeq	r0, {r0, r3, r5, sl, fp, ip, sp}
   	...
    800202c:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
   	...
    8002038:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    800203c:	08002f05 	stmdaeq	r0, {r0, r2, r8, r9, sl, fp, sp}
    8002040:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    8002044:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    8002048:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    800204c:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    8002050:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    8002054:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    8002058:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    800205c:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    8002060:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    8002064:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    8002068:	08002e07 	stmdaeq	r0, {r0, r1, r2, r9, sl, fp, sp}
    800206c:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    8002070:	08002c51 	stmdaeq	r0, {r0, r4, r6, sl, fp, sp}
    8002074:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    8002078:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    800207c:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    8002080:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
   	...
    800208c:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    8002090:	00000000 	andeq	r0, r0, r0
    8002094:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    8002098:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    800209c:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    80020a0:	00000000 	andeq	r0, r0, r0
    80020a4:	08002e05 	stmdaeq	r0, {r0, r2, r9, sl, fp, sp}
    80020a8:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    80020ac:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    80020b0:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    80020b4:	00000000 	andeq	r0, r0, r0
    80020b8:	080041c1 	stmdaeq	r0, {r0, r6, r7, r8, lr}
    80020bc:	08003919 	stmdaeq	r0, {r0, r3, r4, r8, fp, ip, sp}

   080020c0 <configuration_begin_request>:
    80020c0:	b513      	push	{r0, r1, r4, lr}
    80020c2:	4668      	mov	r0, sp
    80020c4:	0002      	movs	r2, r0
   ...

All the addresses are offset by 0x08002000. Now all the bootloader has to do is set the VTOR to 0x08002000 and this user program will execute normally, interrupts and all.

.. _no-vtor:

Dealing with an absent VTOR
===========================


After I purchased the microcontroller for my project (an STM32F042) I discovered that it was a Cortex-M0 and did not have a VTOR. This was a rather unpleasant surprise and now I know that the M0 sucks compared to the M0+. Nonetheless, I was able to overcome this with a fairly simple software shim and that's what I want to share.

There are two main issues that the VTOR addresses\:


* Determining the address of an interrupt when it isn't relative to 0x00000000.


* Forwarding execution of the interrupt routine to that custom address.



Since I don't have a VTOR all of my interrupts will be executed from the bootloader by default. This is obviously unacceptable since things like a USB interrupt occurring would cause the user program to suddenly revert back to being the bootloader program (and probably into some undefined state since the SRAM would be all different).

To address the first problem, I had to make some changes to my bootloader and to the user program\:


#. I designated a certain area of SRAM in the bootloader program as holding data that will be valid while the processor is running.


#. The user program's linker script had its SRAM startpoint moved beyond this reserved section.



I implemented this with these linker script memory modifications\:



**Bootloader linker script\:** 

.. code-block:: c

   _flash_origin = 0x08000000;
   _flash_length = 32K;

   MEMORY
   {
       FLASH (RX) : ORIGIN = _flash_origin, LENGTH = 8K
       RAM_RSVD (W!RX) : ORIGIN = 0x20000000, LENGTH = 256
       RAM (W!RX)  : ORIGIN = 0x20000100, LENGTH = 6K - 256
   }







**Device linker script\:** 

.. code-block:: c

   _flash_origin = 0x08002000;
   _flash_length = 24K;

   MEMORY
   {
       FLASH (RX) : ORIGIN = _flash_origin, LENGTH = _flash_length
       RAM (W!RX)  : ORIGIN = 0x20000100, LENGTH = 6K - 256
   }









And this section addition in the bootloader linker script\:

.. code-block:: c

   ...
       .boot_data :
       {
           *(.rsvd.data)
           *(.rsvd.data*)
       } > RAM_RSVD
   ...

Now I have some reserved memory that the user program won't touch. I use this area to store a psuedo-VTOR\:

.. code-block:: c

   /**
    * Places a symbol into the reserved RAM section. This RAM is not
    * initialized and must be manually initialized before use.
    */
   #define RSVD_SECTION ".rsvd.data,\"aw\",%nobits//"
   #define _RSVD __attribute__((used, section(RSVD_SECTION)))

   static volatile _RSVD uint32_t bootloader_vtor;

   extern uint32_t *g_pfnVectors;

   void bootloader_init(void)
   {
       bootloader_vtor = (uint32_t)(&g_pfnVectors);
   ...

When the bootloader starts it will set this "bootloader_vtor" variable to the location of the bootloader's vector table (the "extern uint32_t \*g_pfnVectors" is linked to that table defined in assembly earlier).

Then, if the bootloader determines that the user program exists it overwrites bootloader_vtor with the following\:

.. code-block:: text

   void bootloader_init(void)
   {
   ...
       uint32_t user_vtor_value = 0;
   ...load the user value...
       //if the prog_start field is set and there are no entry bits set in the CSR (or the magic code is programmed appropriate), start the user program
       if (user_vtor_value &&
               (!reset_entry || (magic == BOOTLOADER_MAGIC_SKIP)))
       {
   ...housekeeping before we jump to the user program...
           __disable_irq();

           uint32_t *user_vtor = (uint32_t *)user_vtor_value;
           uint32_t sp = user_vtor[0];
           uint32_t pc = user_vtor[1];
           bootloader_vtor = user_vtor_value;
           __asm__ __volatile__("mov sp,%0\n\t"
                   "bx %1\n\t"
                   : /* no output */
                   : "r" (sp), "r" (pc)
                   : "sp");
           while (1) { }
       }
   }


Ok, so that solves the issue of "where do the user's interrupts live". The next issue is actually jumping to those. Turns out, that's not a hard problem to solve now. A quick change to the interrupt handlers makes short work of that\:

.. code-block:: c

   /**
    * Entry point for all exceptions which passes off execution to the appropriate
    * handler. This adds some non-trivial overhead, but it does tail-call the
    * handler and I think it's about as minimal as you can get for emulating the
    * VTOR.
    */
   void __attribute__((naked)) Bootloader_IRQHandler(void)
   {
       __asm__ volatile (
               " ldr r0,=bootloader_vtor\n" // Read the fake VTOR into r0
               " ldr r0,[r0]\n"
               " ldr r1,=0xE000ED04\n" // Prepare to read the ICSR
               " ldr r1,[r1]\n" // Load the ICSR
               " mov r2,#63\n"  // Prepare to mask SCB_ICSC_VECTACTIVE (6 bits, Cortex-M0)
               " and r1, r2\n"  // Mask the ICSR, r1 now contains the vector number
               " lsl r1, #2\n"  // Multiply vector number by sizeof(function pointer)
               " add r0, r1\n"  // Apply the offset to the table base
               " ldr r0,[r0]\n" // Read the function pointer value
               " bx r0\n" // Aaaannd branch!
               );
   }

What this does is determine which interrupt number is executing, multiply that number by 4, adds it to bootloader_vtor, and jumps to that location. This does naively what the VTOR does from the perspective of a program. This routine does stomp all over r0, r1, and r2, but since those registers are part of the ARM Exception Context, the original values have already been pushed onto the stack. Since we haven't modified the stack at all (no pushes or pops here), the actual interrupt handler should be none the wiser that something happened before it (and it shouldn't care what's in r0, r1, and r2 as well).

The bootloader also gets a rather non-trivial change to its interrupt vector table\:

.. code-block:: asm
   :height-limit:

   /******************************************************************************
   *
   * The minimal vector table for a Cortex M0.  Note that the proper constructs
   * must be placed on this to ensure that it ends up at physical address
   * 0x0000.0000.
   *
   ******************************************************************************/
      .section .isr_vector,"a",%progbits
     .word  _estack
     .word  Reset_Handler
     .word  Bootloader_IRQHandler
     .word  Bootloader_IRQHandler
     .word  Bootloader_IRQHandler
     .word  Bootloader_IRQHandler
     .word  Bootloader_IRQHandler
     .word  Bootloader_IRQHandler
     .word  Bootloader_IRQHandler
     .word  Bootloader_IRQHandler
     .word  Bootloader_IRQHandler
     .word  Bootloader_IRQHandler
     .word  Bootloader_IRQHandler
     .word  Bootloader_IRQHandler
     .word  Bootloader_IRQHandler
     .word  Bootloader_IRQHandler
     .word  Bootloader_IRQHandler                   /* Window WatchDog              */
     .word  Bootloader_IRQHandler             /* PVD and VDDIO2 through EXTI Line detect */
     .word  Bootloader_IRQHandler                    /* RTC through the EXTI line    */
     .word  Bootloader_IRQHandler                  /* FLASH                        */
     .word  Bootloader_IRQHandler                /* RCC and CRS                  */
     .word  Bootloader_IRQHandler                /* EXTI Line 0 and 1            */
     .word  Bootloader_IRQHandler                /* EXTI Line 2 and 3            */
     .word  Bootloader_IRQHandler               /* EXTI Line 4 to 15            */
     .word  Bootloader_IRQHandler                    /* TSC                          */
     .word  Bootloader_IRQHandler          /* DMA1 Channel 1               */
     .word  Bootloader_IRQHandler        /* DMA1 Channel 2 and Channel 3 */
     .word  Bootloader_IRQHandler        /* DMA1 Channel 4 and Channel 5 */
     .word  Bootloader_IRQHandler                   /* ADC1                         */
     .word  Bootloader_IRQHandler    /* TIM1 Break, Update, Trigger and Commutation */
     .word  Bootloader_IRQHandler                /* TIM1 Capture Compare         */
     .word  Bootloader_IRQHandler                   /* TIM2                         */
     .word  Bootloader_IRQHandler                   /* TIM3                         */
     .word  Bootloader_IRQHandler                                 /* Reserved                     */
     .word  Bootloader_IRQHandler                                 /* Reserved                     */
     .word  Bootloader_IRQHandler                  /* TIM14                        */
     .word  Bootloader_IRQHandler                                 /* Reserved                     */
     .word  Bootloader_IRQHandler                  /* TIM16                        */
     .word  Bootloader_IRQHandler                  /* TIM17                        */
     .word  Bootloader_IRQHandler                   /* I2C1                         */
     .word  Bootloader_IRQHandler                                 /* Reserved                     */
     .word  Bootloader_IRQHandler                   /* SPI1                         */
     .word  Bootloader_IRQHandler                   /* SPI2                         */
     .word  Bootloader_IRQHandler                 /* USART1                       */
     .word  Bootloader_IRQHandler                 /* USART2                       */
     .word  Bootloader_IRQHandler                                 /* Reserved                     */
     .word  Bootloader_IRQHandler                /* CEC and CAN                  */
     .word  Bootloader_IRQHandler                    /* USB                          */


All the interrupts point to this new Bootloader_IRQHandler except Reset. We now have another problem\: What about the interrupts for when we actually need to execute the bootloader program instead of the user program. Well, that's fairly simple now. We just move the g_pfnVectors table so that it is just like any other table\:

.. code-block:: asm

   /**
    * Default vector table local to the bootloader. This is used by the
    * emulated VTOR functionality to actually dispatch interrupts. It must
    * be word-aligned since "ldr" is used to access it.
    */
      .section .text.LocalVectors,"a",%progbits
     .type g_pfnVectors, %object
     .size g_pfnVectors, .-g_pfnVectors
     .align 4

   g_pfnVectors:
     .word  _estack
     .word  Reset_Handler
     .word  NMI_Handler
     .word  HardFault_Handler
     .word  0
     .word  0
     .word  0
     .word  0
     .word  0
     .word  0
     .word  0
     .word  SVC_Handler
     .word  0
     .word  0
     .word  PendSV_Handler
     .word  SysTick_Handler
     .word  WWDG_IRQHandler                   /* Window WatchDog              */
     .word  PVD_VDDIO2_IRQHandler             /* PVD and VDDIO2 through EXTI Line detect */
     .word  RTC_IRQHandler                    /* RTC through the EXTI line    */
     .word  FLASH_IRQHandler                  /* FLASH                        */
     .word  RCC_CRS_IRQHandler                /* RCC and CRS                  */
     .word  EXTI0_1_IRQHandler                /* EXTI Line 0 and 1            */
     .word  EXTI2_3_IRQHandler                /* EXTI Line 2 and 3            */
   ...

I placed it in its own section for fun, but you'll see that it now lives in ".text". This means that it ends up in flash just like any other read only variable would and I don't really care where it ends up. I suppose I could also have put it into the "rodata" section and that would probably be more correct, but it hasn't caused a problem yet. Anyway, as we saw during bootloader_init the address of the bootloader's g_pfnVectors is loaded into bootloader_vtor and if there's no user program it will remain there.

With those two pieces together, we have effectively emulated the VTOR functionality. There are a few corner cases that this doesn't handle very well (such as exceptions before the bootloader_vtor value is initialized) which likely result in Hard Faults, but I haven't encountered an issue there yet.

.. _debugging:

Debugging the user program
--------------------------


With my other bootloader which relied on the VTOR, the presence of the bootloader was not only transparent to the user program, it was also transparent to the debugger. If I needed to run a stack trace during an interrupt or exception, it knew the names of all the symbols it would find in the trace. But now that we've mixed together the bootloader and user program, that makes things less straightfoward since the elf file from the user program won't have any knowledge of the code executed by the bootloader.

While I didn't overcome this issue completely and stack traces can be a little awkward if they are interrupted at just the right time, I did manage to massage gdb enough to make it somewhat usable\:

.. code-block:: sh

   gdb -ex "target remote localhost:3333" -ex "add-symbol-file ./path/to/my/bootloader.elf 0x08000000" ./path/to/my/user/program.elf


The "add-symbol-file" directive points gdb towards my bootloader's elf file and informs it about any symbols it might find if we just so happen to break while inside the bootloader's program space. It also knows about the names of symbols inside the bootloader's reserved SRAM space.

.. _conclusion:

Conclusion
==========


Here we've seen how the VTOR works, why it's useful to bootloaders, and one way to overcome the issue of not having a VTOR in certain architectures like the Cortex-M0. If you have any questions or comments, feel free to leave a comment on this post. This isn't the most robust way of fixing the problem, but for my hacking around it works just fine. I only hope that this post is useful and maybe sparks some idea with someone who is trying to overcome a similar problem.