Wow it has been a while. Between school, work, and another project that I've been working on since last October (which, if ultimately successful, I will post here) I haven't had a lot of time to write about anything cool.

I wanted to share today something cool I wrote for my AVRs. Many of my recent AVR projects have become rather complex in that they usually are split into multiple parts in the software which interact with each other. One project in particular had the following components\:


* A state machine managing several PWM channels. It implemented behavior like pulsing, flashing, etc. It also provided methods for the other components to interact with it.


* A state machine managing an NRF24L01+ radio module, again providing methods for components to interact with it.


* A state machine managing several inputs, interpreting them and sending commands to the other two components



So, why did I use state machines rather than just implementing this whole thing in a giant loop with some interrupts mixed in? The answer is twofold\:


#. Spaghetti. Doing things in state machines avoided spaghetti code that would have otherwise made the system very difficult to modify. Each machine was isolated from the others both structurally and in software (static variables/methods, etc). The only way to interact with the state machines was to use my provided methods which lends itself to a clean interface between the different components of the program. Switching out the logic in one part of the program did not have any effect on the other components (unless method signatures were changed, of course).


#. Speed. All of these state machines had a requirement of being able to respond quickly to events, whether they were input events from the user or an interrupt from a timer and whatnot. Interrupts make responding to things in a timely fashion easy, but they stop all other interrupts while running (unless doing nested interrupts, which is ...unwieldy... in an AVR) and so doing a lot of computation during an interrupt can slow down the other parts of the system. By organizing this into state machines, I could split up parts of computation into pieces that could execute fast and allow other parts to run in response to their interrupts quickly.



None of this, however, is particularly new. Everyone does state machines and they are comparatively easy to implement. In almost every project I have done there has been some form of state machine, whether it was just busy waiting for some flag somewhere and doing something after that flag was set, or doing something much more complex. What I wanted to show today was a different way of dealing with the issues of spaghetti and speed\: **Building a preempting task scheduler.** These are considered a key and central component of **Real-Time Operating Systems**, so what you see in this article is the beginnings of a real-time kernel for an AVR microcontroller.

I should mention here that there is a certain level of ability assumed with AVRs in this post. I assume that the reader has a good knowledge of how programs work with the stack, the purpose and functioning of the general purpose registers, how function calls actually happen on the microcontroller, how interrupts work, the ability to read AVR assembly (don't worry most of this is in C...but there is some critical code written in assembly), and a general knowledge of the avr-gcc toolchain.

Table of Contents
=================




* `Preemption? <preemption>`__


* `Pros and Cons <prosandcons>`__


* `Implementation <implementation>`__
* `kos_init and kos_new_task <initnewtask>`__


  * `kos_run and kos_schedule <runschedule>`__


  * `kos_enter_isr and kos_exit_isr <isr>`__


  * `kos_dispatch <dispatch>`__


  * `Results by code size <codesize>`__

* `Example\: A semaphore <semaphore>`__


* `Conclusion <conclusion>`__




.. _preemption:

Preemption?
===========


The definition of preemption in computing is being able to interrupt a task, without its cooperation, with the intention of executing it later, in order to run some other task.

Firstly we need to define a task\: **A task is a unit of execution; something that the program structure defines as a self-contained part of the program which accomplishes some purpose**. In our case, a task is basically going to just be a method which never returns. The next thing to define is a **scheduler**. A scheduler is a software component which can decide from a list of tasks which task needs to run on the processor. The scheduler uses a **dispatcher** to actually change the code that is executing from the current task to another one. This is called saving and restoring the **context** of the task.

The cool thing about preemptive scheduling is that any task can be interrupted at any time and another task can start executing. Now, it could be asked, "Well, isn't that what interrupts do? What's the difference?". The difference is that an interrupt in a system using a preemptive scheduler can actually resume in a different place from when it started. Without a scheduler, when an interrupt ends the processor will send the code right back to where it was executing when the interrupt occurred. In contrast, the scheduler actually allows the program to have a little more control and move from one task to another in response to an interrupt or some other stimuli (yes, it doesn't even need to be an interrupt...it could be another task!).

In the state machine example above, I used state machines as a way to break up computations so that the other machines could run at predetermined points. I noticed that in most of these cases, this point was when waiting for some user input or an interrupt. Although I used interrupts extensively in the application, there were a lot of flags to be polled and this happened inside state machine tick functions. When an interrupt occurred and set a flag, it would need to wait for the "main" code to get around to executing the tick function for the particular state machine that listens to the flag before anything could happen. This introduces a lot of latency and jitter (differences in the amount of time it takes the system to respond to an interrupt from one moment to the next). Not good.

Using tasks removes a lot of these latency problems since the interrupt can halt the current task (**block**) and begin executing another which was waiting on the interrupt to occur (**unblock** or **resume**). Once the higher priority task is blocked again (through a call to some function asking it to wait for some event), the scheduler will change back to the original task and things go on as usual. Using tasks also has the effect of making the code easier to read. While state machines are easy to write, they are not always easy to follow. A function is invoked over and over again and that requires more thought than simply reading a linear function. Tasks can be very linear since the state machine is embodied in calls which could possibly block the task.

A positive side effect of doing things this way (with a scheduler) is that we can now implement the familiar things such as `semaphores <https://en.wikipedia.org/wiki/Semaphore_(programming)>`__ and `queues <https://en.wikipedia.org/wiki/Message_queue>`__ to communicate between our tasks in a fine grained manner. At their core these are simply methods that can manipulate the list of tasks and call the scheduler to decide which task to execute next.

**Summary\:** Using a preemptive scheduler can allow for lower latency and jitter between an interrupt occurring and some non-ISR code responding to it when compared to using several state machines. This means it will respond more consistently to interrupts occurring, though not necessarily in a more timely fashion. It also allows for fine-grained priority control with these responses.

.. _prosandcons:

Pros and Cons
=============


Before continuing, I would like to point out some pros and cons that I see of writing a task scheduler lest we fall into the "golden hammer" antipattern. There are certainly more, but here is my list (feel free to comment with comments on this).

Some Pros
---------




* Can reduce the jitter (and possibly the latency) in responding to interrupts. This is of paramount importance in some embedded systems which will have problems if the system cannot respond in a predictable manner to external stimuli.


* Can greatly simplify application code by using familiar constructs such as semaphores and queues. Compared to state machines, this code can be easier to read as it can be written very linearly (no switches, if's etc). This can reduce the initial bugs found in programs.


* Can entirely remove the need for busy waits (loops polling a flag). A properly designed state machine shouldn't have these either, but it can take a large amount of effort to design these kinds of machines. They also can take up a lot of program space when space is at a premium (not always true).


* Can reduce application code size. This is weak, but since the code can be made more linear with calls to the scheduler rather than returning all the time, there is no need for switch statements and ifs which can compile to some beastly assembly code.




Some Cons
---------




* Can add unnecessary complexity to the program in general. A task scheduler is no small thing and brings with it all of the issues seen in concurrent programming in general. However, these issues usually already exist when using interrupts and such.


* Can be very hard to debug. I needed an emulator to get this code working correctly. Anything where we mess with the stack pointer or program counter is going to be a very precise exercise.


* Can make the application itself hard to debug. Is it a problem with the scheduler? Or is it a problem with the program itself? It is an additional component to consider when debugging.


* Adds additional program weight. My base implementation uses ~450 bytes of program memory. While quite tiny compared to many programs, this would be unacceptably high on a smaller AVR such as the ATTiny13A which only has 1K of program memory.



So...lots of those are contradictory. What is a pro can also be a con. Anyway, I'm just presenting this as something cool to do, not as the end all be all of ways to structure an embedded program. If you have a microcontroller that is performing a lot of tasks that need to be able to react reliably to an interrupt, this might be the way to go for you. However, if your microcontroller is just toggling some gpios and reacting to some timers, this might be overkill. It all depends on the application.

.. _implementation:

Implementation
==============


Mmmkay here's the fun part. At this point you may be asking, "How in the world can we make something that can interrupt during one function and resume into another?" I recently completed a course on Real-Time Operating Systems (RTOS) at my university which opened my eyes into how this can be done (we wrote one for the 8086...so awesome!), so I promptly wrote one for the AVR. For those who come by here who have taken the same course at BYU, they will notice some distinct similarities since I went with what I knew. I've named it KOS, for "Kevin's Operating System", but this was just so I had an easy prefix for my types and function names. If you're going to implement your own based on this article, don't worry about naming it like mine (though a mention of this article somewhere would be cool).

**Disclaimer\: I have only started to scratch the surface of this stuff myself and I may have made some errors.** I appreciate any insight anyone can give me into either suggestions for this or problems with my implementation. Just leave it in the comments \:)

**All of the code can be found here\: `https\://github.com/kcuzner/kos-avr <https://github.com/kcuzner/kos-avr>`__**

The focus of a scheduler/dispatcher system for tasks is manipulating the stack pointer and the stack itself. "Traditionally," programs written for microcontrollers have a single stack which grows from the bottom of memory up and all code is executed on that stack. The concept here is that we still start out with that stack, but we actually execute the tasks on their own separate stacks. When we want to switch to a task, we point the AVR's stack pointer to the desired task's stack and start executing (its the "start executing" part where things get fun).

First, let's take a look at the structure which represents a task\:

.. code-block:: {lang}



   typedef enum { TASK_READY, TASK_SEMAPHORE, TASK_QUEUE } KOS_TaskStatus;

   typedef struct KOS_Task {
       void *sp;
       KOS_TaskStatus status;
       struct KOS_Task *next;
       void *status_pointer;
   } KOS_Task;

The very first item in this struct is the pointer to the stack pointer (\*sp). It is a void\* because we don't normally access anything on it...we just make the SP register point to it when we want to execute the task.

The next item in the struct is a status enum. This is used by my primitive scheduler to determine if a task is "READY" to execute. If a task is ready to execute, then it is not waiting on anything (i.e. blocked) and it can be resumed at any time. In the case where the task is waiting on something like a semaphore, this status would be changed to SEMAPHORE. The semaphore posting code would then change the status back to READY once somebody posted to the semaphore. This is called "unblocking".

After the status comes the \*next pointer. The tasks are arranged in a linked list because they have a **priority** attached to them. This priority determines which tasks get executed first. At the top of the linked list is the highest priority task and at the end of the list is the lowest priority task.

Finally, we have the \*status_pointer. This is used by our functions which can unblock tasks to determine why tasks are blocked in the first place. We will see more about this when we make a primitive semaphore.

Ok, so for the basic task scheduling and dispatching functionality we are going to implement some functions (these are declared in a header)\:

.. code-block:: {lang}



   typedef void (*KOS_TaskFn)(void);

   extern KOS_Task *kos_current_task;

   /**
    * Initializes the KOS kernel
    */
   void kos_init(void);

   /**
    * Creates a new task
    * Note: Not safe
    */
   void kos_new_task(KOS_TaskFn task, void *sp);

   /**
    * Puts KOS in ISR mode
    * Note: Not safe, assumes non-nested isrs
    */
   void kos_isr_enter(void);

   /**
    * Leaves ISR mode, possibly executing the dispatcher
    * Note: Not safe, assumes non-nested isrs
    */
   void kos_isr_exit(void);

   /**
    * Runs the kernel
    */
   void kos_run(void);

   /**
    * Runs the scheduler
    */
   void kos_schedule(void);

   /**
    * Dispatches the passed task, saving the context of the current task
    */
   void kos_dispatch(KOS_Task *next);

As for source files, we will only have a single C file for the implementation, but there will be some inline assembly because we are going to have to fiddle with registers. Yay! I'll just go through the functions one by one and afterwards I'll go through my design decisions and how they affect things. This is not the only, nor the best, way to do this.

.. _initnewtask:

Implementation\: kos_init and kos_new_task
------------------------------------------


Firstly, we have the kos_init and kos_new_task functions, which come with some baggage\:

.. code-block:: {lang}



   static KOS_Task tasks[KOS_MAX_TASKS + 1];
   static uint8_t next_task = 0;
   static KOS_Task *task_head;
   KOS_Task *kos_current_task;

   static uint8_t kos_idle_task_stack[KOS_IDLE_TASK_STACK];
   static void kos_idle_task(void)
   {
       while (1) { }
   }

   void kos_init(void)
   {
       kos_new_task(&kos_idle_task, &kos_idle_task_stack[KOS_IDLE_TASK_STACK - 1]);
   }

   void kos_new_task(KOS_TaskFn task, void *sp)
   {
       int8_t i;
       uint8_t *stack = sp;
       KOS_Task *tcb;

       //make space for pc, sreg, and 32 registers
       stack[0] = (uint16_t)task & 0xFF;
       stack[-1] = (uint16_t)task >> 8;
       for (i = -2; i > -34; i--)
       {
           stack[i] = 0;
       }
       stack[-34] = 0x80; //sreg, interrupts enabled
    
       //create the task structure
       tcb = &tasks[next_task++];
       tcb->sp = stack - 35;
       tcb->status = TASK_READY;

       //insert into the task list as the new highest priority task
       if (task_head)
       {
           tcb->next = task_head;
           task_head = tcb;
       }
       else
       {
           task_head = tcb;
       }
   }

Here we have two concepts that are embodied. The first is the **context**. The context the data pushed onto the stack that the dispatcher is going to use in order to restore the task before executing it. This is similar (identical even) to the procedure used with interrupt service routines, except that we store every single one of the 32 registers instead of just the ones that we use. The next concept is that of the **idle task**. As an optimization, there is a task which has the lowest priority and is never blocked. It is always ready to execute, so when all other tasks are blocked, it will run. This means that we don't have to deal with the case in the scheduler when there is no tasks to execute since there will always be a task.

The kos_init function performs only one operation\: Add the idle task to the list of tasks to execute. Notice that there was some space allocated for the stack of the idle task. This stack must be at least as large as the entire context (35 bytes here) plus enough for any interrupts which may occur during program execute. I chose 48 bytes, but it could be as large as you want. Also take note of the pointer that we pass for the stack into kos_new_task\: It is a pointer to the end of our array. This is because stacks grow "up" in memory, meaning a push decrements the address and a pop increments it. If we passed the beginning of the array, the first push would make us point before the memory allocated to the stack since arrays are allocated "downwards" in memory.

The kos_new_task function is a little more complex. It performs two operations\: setting up the initial context for the function and adding the Task structure to the linked list of tasks. The context needs to be set up initially because from the scheduler's perspective, the new task is simply an unblocked task that was blocked before. Therefore, it expects that some context is stored on that task's stack. Our context is ordered such that the PC (program counter) is first, the 32 registers are next, and the status register is last. Since the stack is last-in first-out, the SREG is popped first, then the 32 registers, and then the PC. We can see at the beginning of the function that we take the function pointer (they are usually 16 bits on most AVRs...the ones with lots of flash do it differently, so consult your datasheets) and set it up to be the program counter. It is arranged LSB-first, so the LSByte is "pushed" before the MSByte. The order here is very important and the reason why will become very apparent when we see the code for the dispatcher. After that, we put 32 0's onto the stack. These are the initial values for the registers and 0 seemed like a sensible value. The very last byte "pushed" is the status register. We set it to 0x80 so that the interrupt flag is set. This is a design decision to prevent problems with forgetting to enable interrupts for every task and having one task where we forgot to enable it prevent all interrupts from executing. Finally, the top of the stack (note the subtraction of 35 bytes from the stack pointer) is stored on the Task struct along with the initial task state. We add it to the task list as the head of the list, so the last task added is the task with the highest priority.

.. _runschedule:

Implementation\: kos_run and kos_schedule
-----------------------------------------


Next we have the kos_run function\:

.. code-block:: {lang}



   void kos_run(void)
   {
       kos_schedule();
   }

Well that's simple\: it just calls the scheduler. So, let's look at kos_schedule\:

::



   void kos_schedule(void)
   {
       if (kos_isr_level)
           return;

       KOS_Task *task = task_head;
       while (task->status != TASK_READY)
           task = task->next;

       if (task != kos_current_task)
       {
           ATOMIC_BLOCK(ATOMIC_RESTORESTATE)
           {
               kos_dispatch(task);
           }
       }
   }


The very first thing to notice is the kos_isr_level reference. This solves a very specific problem that occurs with ISRs which I talk about in the next section. Other than that bit, however, this is also simple. Because our tasks in the linked list are ordered by priority, we can simply start at the top and move along the linked list until we locate the first task that is ready (unblocked). Once that task is found, we will call the dispatcher if the task we found is not the currently executing task.

The purpose of the ATOMIC_BLOCK is to ensure that interrupts are disabled when the dispatcher runs. Since the stack is going to be manipulated, the entire dispatcher is considered to be a critical section of code and must be run atomically. The ATOMIC_BLOCK will restore the interrupt status after kos_dispatch returns (which is after the task has been resumed).

.. _isr:

Implementation\: kos_enter_isr and kos_exit_isr
-----------------------------------------------


We are faced with a very particular problem when we want to call our scheduler inside of an interrupt. Let's imagine a scenario where we have two tasks, Task A and Task B (Task A has higher priority than Task B), in addition to the idle task. Task A uses waits on two semaphores (semaphores 1 and 2) that is signaled by an ISR. When task A is running, it signals another semaphore that Task B waits on (semaphore 3). Here is what happens\:


#. The idle task is running because both Task A and Task B are waiting on semaphores.


#. An interrupt occurs (note that it happens during the idle task) and the ISR begins executing immediately. An ISR can be thought of as a super high priority task since it will interrupt anything.


#. The ISR posts to semaphore 1 which Task A is waiting on. The very next statement is going to be to signal semaphore 2 as well. However, this happens next\:


#. After signaling semaphore 1, the dispatcher runs and Task A begins to execute. Task A signals semaphore 3 which will cause Task B to run. Since Task A has a higher priority than B, however, Task B isn't executed yet. Task A goes on to wait on semaphore 2. This then causes Task B to be dispatched.


#. Task B takes a really long time to run, but it finally ends. There are no more tasks on the ready list, so the idle task begins to run.


#. The idle task resumes inside the ISR and posts to semaphore 2.


#. Task A begins running again.



As straightforward as that may seem, that isn't the intended behavior. Imagine if a task with an even higher priority than A had the ISR occur while it was executing. The sequence above would be totally different because Task A wouldn't be dispatched after the 1st semaphore being posted (item #4). Let's see what happens\:


#. The idle task is running because both Task A and Task B are waiting on semaphores.


#. An interrupt occurs (note that it happens during the idle task) and the ISR begins executing immediately. An ISR can be thought of as a super high priority task since it will interrupt anything.


#. The ISR posts to semaphore 1 which task A is waiting on.


#. After signaling semaphore 1, the scheduler notices that the current task has a higher priority than Task A, so it does not dispatch.


#. The ISR posts to semaphore 2.


#. Same as #4. The ISR ends. Let's say that the high priority task blocks soon afterwards.


#. Once the high priority task has blocked, Task A is executed. It posts to semaphore 3 and then waits on semaphore 2. Since semaphore 2 has already been posted, it continues right on through without a task switch to Task B. **This is a major difference in the order of operations.**


#. After Task A finally blocks, Task B executes.



Because of the inconsistency and the fact that the ISR "priority" when viewed by the scheduler is determined by possibly random ISRs (making it non-deterministic), we need fix this. The solution I went with was to make two methods\: kos_enter_isr and kos_exit_isr. These should be called when an ISR begins and when an ISR ends to temporarily hold off calling the scheduler until the very end of the ISR. This has the effect of giving an ISR an apparently high priority since it will not switch to another task until it has completely finished. So, although the idle task may be running when the ISR occurs, while the ISR is running no context switches will occur until the very end. Here is some code\:

.. code-block:: {lang}



   static uint8_t kos_isr_level = 0;
   void kos_isr_enter(void)
   {
       kos_isr_level++;
   }

   void kos_isr_exit(void)
   {
       kos_isr_level--;
       kos_schedule();
   }

As seen in kos_schedule, we use the kos_isr_level variable to indicate to the scheduler whether we are in an ISR or not. When kos_isr_level finally returns to 0, the scheduler will actually perform scheduling when it is called at the end of kos_isr_exit. The second set of events described earlier will now happen every time, even if the idle task is interrupted.

These functions must be run with interrupts disabled since they don't use any sort of locking, but they should support nested interrupts so long as they are called at the point in the interrupt when interrupts have been disabled.

.. _dispatch:

Implementation\: kos_dispatch
-----------------------------


The dispatcher is written basically entirely in inline assembly because it does the actual stack manipulation\:

.. code-block:: {lang}



   void kos_dispatch(KOS_Task *task)
   {
       // the call to this function should push the return address into the stack.
       // we will now construct saving context. The entire context needs to be
       // saved because it is very possible that this could be called from within
       // an isr that doesn't use the call-used registers and therefore doesn't
       // save them.
       asm volatile (
               "push r31 \n\t"
               "push r30 \n\t"
               "push r29 \n\t"
               "push r28 \n\t"
               "push r27 \n\t"
               "push r26 \n\t"
               "push r25 \n\t"
               "push r24 \n\t"
               "push r23 \n\t"
               "push r22 \n\t"
               "push r21 \n\t"
               "push r20 \n\t"
               "push r19 \n\t"
               "push r18 \n\t"
               "push r17 \n\t"
               "push r16 \n\t"
               "push r15 \n\t"
               "push r14 \n\t"
               "push r13 \n\t"
               "push r12 \n\t"
               "push r11 \n\t"
               "push r10 \n\t"
               "push r9 \n\t"
               "push r8 \n\t"
               "push r7 \n\t"
               "push r6 \n\t"
               "push r5 \n\t"
               "push r4 \n\t"
               "push r3 \n\t"
               "push r2 \n\t"
               "push r1 \n\t"
               "push r0 \n\t"
               "in   r0, %[_SREG_] \n\t" //push sreg
               "push r0 \n\t"
               "lds  r26, kos_current_task \n\t"
               "lds  r27, kos_current_task+1 \n\t"
               "sbiw r26, 0 \n\t"
               "breq 1f \n\t" //null check, skip next section
               "in   r0, %[_SPL_] \n\t"
               "st   X+, r0 \n\t"
               "in   r0, %[_SPH_] \n\t"
               "st   X+, r0 \n\t"
               "1:" //begin dispatching
               "mov  r26, %A[_next_task_] \n\t"
               "mov  r27, %B[_next_task_] \n\t"
               "sts  kos_current_task, r26 \n\t" //set current task
               "sts  kos_current_task+1, r27 \n\t"
               "ld   r0, X+ \n\t" //load stack pointer
               "out  %[_SPL_], r0 \n\t"
               "ld   r0, X+ \n\t"
               "out  %[_SPH_], r0 \n\t"
               "pop  r31 \n\t" //status into r31: andi requires register above 15
               "bst  r31, %[_I_] \n\t" //we don't want to enable interrupts just yet, so store the interrupt status in T
               "bld  r31, %[_T_] \n\t" //T flag is on the call clobber list and tasks are only blocked as a result of a function call
               "andi r31, %[_nI_MASK_] \n\t" //I is now stored in T, so clear I
               "out  %[_SREG_], r31 \n\t"
               "pop  r0 \n\t"
               "pop  r1 \n\t"
               "pop  r2 \n\t"
               "pop  r3 \n\t"
               "pop  r4 \n\t"
               "pop  r5 \n\t"
               "pop  r6 \n\t"
               "pop  r7 \n\t"
               "pop  r8 \n\t"
               "pop  r9 \n\t"
               "pop  r10 \n\t"
               "pop  r11 \n\t"
               "pop  r12 \n\t"
               "pop  r13 \n\t"
               "pop  r14 \n\t"
               "pop  r15 \n\t"
               "pop  r16 \n\t"
               "pop  r17 \n\t"
               "pop  r18 \n\t"
               "pop  r19 \n\t"
               "pop  r20 \n\t"
               "pop  r21 \n\t"
               "pop  r22 \n\t"
               "pop  r23 \n\t"
               "pop  r24 \n\t"
               "pop  r25 \n\t"
               "pop  r26 \n\t"
               "pop  r27 \n\t"
               "pop  r28 \n\t"
               "pop  r29 \n\t"
               "pop  r30 \n\t"
               "pop  r31 \n\t"
               "brtc 2f \n\t" //if the T flag is clear, do the non-interrupt enable return
               "reti \n\t"
               "2: \n\t"
               "ret \n\t"
               "" ::
               [_SREG_] "i" _SFR_IO_ADDR(SREG),
               [_I_] "i" SREG_I,
               [_T_] "i" SREG_T,
               [_nI_MASK_] "i" (~(1 << SREG_I)),
               [_SPL_] "i" _SFR_IO_ADDR(SPL),
               [_SPH_] "i" _SFR_IO_ADDR(SPH),
               [_next_task_] "r" (task));
   }


So, a lot is happening here. There are 4 basic steps\: Save the current context, update the current task's stack pointer, change the stack pointer to the next task, and restore the next task's context.

Inline assembly has an interesting syntax in GCC. I don't believe it is fully portable into non-GCC compilers, so this makes the code depend more or less on GCC. Inline assembly works by way of placeholders (called Operands in the `manual <https://gcc.gnu.org/onlinedocs/gcc/Extended-Asm.html>`__). At the very end of the assembly statement, we see a series of comma-separated statements which define these placeholders/operands and how the assembly is going to use registers and such. First off, we pass in the SREG, SPL, and SPH registers as type "i", which is a constant number known at compile-time. These are simply the IO addresses for these registers (found in avr/io.h if you follow the #include chain deep enough). The next couple parameters are also "i" and are simply bit numbers and masks. The last parameter is the next task pointer passed in as an argument. This is the part where we see the reason why it is more convenient to do this in inline assembly rather than writing it up in an assembly file. While it is possible to look up how avr-gcc passes arguments to functions and discover that the arguments are stored in a certain order in certain registers, it is far simpler and less breakable to allow gcc to fill in the blanks for us. By stating that the _next_task_ placeholder is of type "r" (register), we force GCC to place that variable into some registers of its choosing. Now, if we were using some global variable or a static local, gcc would generate some code before our asm block placing those values into some registers. For this application, that could be quite bad since we depend on no (possibly stack-manipulating) code appearing between the function label and our asm block (more on this in the next paragraph). However, since arguments are passed by way of register, gcc will simply give us the registers by which they are passed in to the function. Since pointers are usually 16 bits on an 8-bit AVR (larger ones will have 3 bytes maybe...but I'm really not sure about this), it fits into two registers. We reference these in the inline assembly by way of "%A[_next_task_]" and "%B[_next_task_]" (note the A and B...these denote the LSB and MSB registers).

Storing the context is pretty straightforward\: push all of the registers and push the status register. At this point you may ask, "What about the program counter? Didn't we have to push that earlier during kos_new_task?" When the function was called (using the CALL instruction), the return address was pushed onto the stack as a side-effect of that instruction. So, we don't need to push the program counter because it is already on there. This is also why it would be very bad if some code appeared before our asm block. It is likely that gcc will clear out some space on the stack and so we would end up with some junk between the return address on the stack and our first "push" instruction. This would mess up the task context frame and we will see later in the code that this will prevent this function from dispatching the task correctly when it became time for the task to be resumed.

Updating the stack pointer is slightly more tricky. Interrupts are disabled first because it would really suck if we got interrupt during this part (anytime the stack pointer is manipulated is a critical section). We then get to dereference the kos_current_task variable which contains our current task. If we remember from above, the very first thing in the KOS_Task structure is the stack pointer, so if we dereference kos_current_task, we are left with the address at which to store the stack pointer. From there, its as simple as loading the stack pointer into some registers and saving it into Indirect Register X (set by registers 26 and 27).

I should note here something about clearing the interrupt flag. Normally, we would want to check to see if interrupts were enabled beforehand so that we can know if we need to restore them. This code lacks an explicit check because of the fact that the status register (with interrupts possibly enabled) has already been stored. Later, when the current task is restored, the SREG will be restored and thus interrupts will be turned back on if they need to be. Similarly, if the next task has interrupts enabled, they will turned on in the same fashion.

After updating kos_current_task's stack pointer, we get to move the stack to the next task and set kos_current_task to point to the next task. This is essentially the reverse of the previous operation. Instead of writing to Indirect Register X (which points to the stack pointer of the task), we get to read from it. We also slip in a couple instructions to update the kos_current_task pointer so that it points to the next task. After we have changed the SPL and SPH registers to point to our new stack, the task passed into kos_dispatch is ready to be resumed.

Resuming the next task's context is a little less straightforward than saving it. We need to prevent interrupts from occurring while we restore the context. The reason for this is to ensure that we don't end up storing more than one context on that task's stack (and thereby increase the minimum required stack size to prevent a stack overflow). The problem here is that when we restore the status register, interrupts could be enabled at that point, rather that at the end when the context is done being restored. So, we need to restore in three steps\: Restore the status register without the interrupt flag, restore all other registers, and then restore the interrupt flag. This is done by transferring the interrupt flag in the status register into the T (transfer) bit in the status register (that's the "bst" and "bld" instructions), clearing the interrupt flag, and then later executing either the ret or reti instruction based on this flag. The side effect is that we trash the T bit. **I am not sure I can actually do this.** This is one part that is tricky\: The avr-gcc manual `states <https://gcc.gnu.org/wiki/avr-gcc#Call-Used_Register>`__ that the T flag is a scratchpad, just like r0, and doesn't need to be restored by called functions. My logic here is that since the only way for a task to become blocked is either it being executed initially or from a call to kos_dispatch, gcc sees the dispatch call as a normal function call and will not assume that the T flag will remain unchanged.

After dancing around with bits and restoring the modified SREG, we proceed to pop off the rest of the registers in the reverse order that they were stored at the beginning of the function. At the very end, we use a T flag branch instruction to determine which return instruction to use. "ret" will return normally without setting the interrupt flag and "reti" will set the interrupt flag.

.. _codesize:

Implementation\: Results by code size
-------------------------------------


So, at this point we have implemented a task scheduler and dispatcher. Here is how it weighs in with avr-size when compiled for an ATMega48A running just the idle task\:

::



   avr-size -C --mcu=atmega48a bin/kos.elf
   AVR Memory Usage
   ----------------
   Device: atmega48a

   Program:     474 bytes (11.6% Full)
   (.text + .data + .bootloader)

   Data:        105 bytes (20.5% Full)
   (.data + .bss + .noinit)


Not the best, but its reasonable. The data usage could be taken down by reducing the number of maximum tasks. There are other RTOS available for AVR which can compile smaller. We could do several optimizations which I will discuss in the conclusion

.. _semaphore:

Example\: A semaphore
=====================


So, we now have a task scheduler. The thing is, although capable of running multiple tasks, it is not possible for multiple tasks to actually run. Why? Because kos_dispatch is never called! We need something that causes the task to become blocked.

As a demonstration, I'm going to implement a simple semaphore. I won't go into huge detail since that isn't the point of this article (and it has been long enough), but here is the code\:

Header contents\:

.. code-block:: {lang}



   typedef struct {
       int8_t value;
   } KOS_Semaphore;

   /**
    * Initializes a new semaphore
    */
   KOS_Semaphore *kos_semaphore_init(int8_t value);

   /**
    * Posts to a semaphore
    */
   void kos_semaphore_post(KOS_Semaphore *sem);

   /**
    * Pends from a semaphore
    */
   void kos_semaphore_pend(KOS_Semaphore *sem);

Source contents\:

.. code-block:: {lang}



   static KOS_Semaphore semaphores[KOS_MAX_SEMAPHORES + 1];
   static uint8_t next_semaphore = 0;

   KOS_Semaphore *kos_semaphore_init(int8_t value)
   {
       KOS_Semaphore *s = &semaphores[next_semaphore++];
       s->value = value;
       return s;
   }

   void kos_semaphore_post(KOS_Semaphore *semaphore)
   {
       ATOMIC_BLOCK(ATOMIC_RESTORESTATE)
       {
           KOS_Task *task;
           semaphore->value++;

           //allow one task to be resumed which is waiting on this semaphore
           task = task_head;
           while (task)
           {
               if (task->status == TASK_SEMAPHORE && task->status_pointer == semaphore)
                   break; //this is the task to be restored
               task = task->next;
           }

           task->status = TASK_READY;
           kos_schedule();
       }
   }

   void kos_semaphore_pend(KOS_Semaphore *semaphore)
   {
       ATOMIC_BLOCK(ATOMIC_RESTORESTATE)
       {
           int8_t val = semaphore->value--; //val is value before decrement

           if (val <= 0)
           {
               //we need to wait on the semaphore
               kos_current_task->status_pointer = semaphore;
               kos_current_task->status = TASK_SEMAPHORE;

               kos_schedule();
           }
       }
   }

So, our semaphore will cause a task to become blocked when kos_semaphore_pend is called (and the semaphore value was <= 0) and when kos_semaphore_post is called, the highest priority task that is blocked on the particular semaphore will be made ready.

Just so this makes sense, let's go through an example sequence of events\:


#. Task A is created. There are now two tasks on the task list\: Task A and the idle task.


#. Semaphore is initialized to 1 with kos_semaphore_init(1);


#. Task A calls kos_semaphore_pend on the semaphore. The value is decremented, but it was >0 before the decrement, so the pend immediately returns.


#. Task A calls kos_semaphore_pend again. This time, the kos_current_task (which points to Task A) state is set to blocked and the blocking data points to the semaphore. The scheduler is called and since Task A is now blocked, the idle task will be dispatched by kos_dispatch.


#. The idle task runs and runs


#. Eventually, some interrupt could occur (like a timer or something). During the course of the ISR, kos_semaphore_post is called on the semaphore. Every call to kos_semaphore_post allows exactly one task to be resumed, so it goes through the list looking for the highest priority task which is blocked on the semaphore. Task A is resumed at the point immediately after the call to kos_dispatch in kos_schedule. kos_schedule returns after a couple instructions restoring the interrupt flag state and now Task A will run until it is blocked.



Here's a program that does just this\:

.. code-block:: {lang}



   /**
    * Main file for OS demo
    */

   #include "kos.h"

   #include <avr/io.h>
   #include <avr/interrupt.h>

   #include "avr_mcu_section.h" //these two lines are for simavr
   AVR_MCU(F_CPU, "atmega48");

   static KOS_Semaphore *sem;

   static uint8_t val;

   static uint8_t st[128];
   void the_task(void)
   {
       TCCR0B |= (1 << CS00);
       TIMSK0 |= (1 << TOIE0);
       while (1)
       {
           kos_semaphore_pend(sem);
           TCCR0B = 0;

           val++;
       }
   }

   int main(void)
   {
       kos_init();

       sem = kos_semaphore_init(0);

       kos_new_task(&the_task, &st[127]);

       kos_run();

       return 0;
   }

   ISR(TIMER0_OVF_vect)
   {
       kos_isr_enter();
       kos_semaphore_post(sem);
       kos_isr_exit();
   }


Running this with avr-gdb and simavr we can see this in action. I placed breakpoints at the val++ line and the kos_semaphore_post line. Here's the output with me pressing Ctrl-C at the end once it got into and stayed in the infinite loop in the idle task\:

::



   (gdb) break main.c:27
   Breakpoint 1 at 0x35a: file src/main.c, line 27.
   (gdb) break main.c:47
   Breakpoint 2 at 0x38a: file src/main.c, line 47.
   (gdb) continue
   Continuing.
   Note: automatically using hardware breakpoints for read-only addresses.

   Breakpoint 2, __vector_16 () at src/main.c:47
   47	    kos_semaphore_post(sem);
   (gdb) continue
   Continuing.

   Breakpoint 2, __vector_16 () at src/main.c:47
   47	    kos_semaphore_post(sem);
   (gdb) continue
   Continuing.

   Breakpoint 2, __vector_16 () at src/main.c:47
   47	    kos_semaphore_post(sem);
   (gdb) continue
   Continuing.

   Breakpoint 1, the_task () at src/main.c:27
   27	        val++;
   (gdb) continue
   Continuing.

   Breakpoint 1, the_task () at src/main.c:27
   27	        val++;
   (gdb) continue
   Continuing.

   Breakpoint 1, the_task () at src/main.c:27
   27	        val++;
   (gdb) continue
   Continuing.
   ^C
   Program received signal SIGTRAP, Trace/breakpoint trap.
   kos_idle_task () at src/kos.c:27
   27	{


You may have noticed that the interrupt was called three times before we even got to val++. The reason for this is that timer0 is an 8-bit timer and I used no prescaler for its clock, so the interrupt will happen every 255 cycles. Given that the dispatcher is nearly 100 instructions and the scheduler isn't exactly short either, the interrupt could easily be called three times before it manages to resume the task after it blocks (including the time it takes to block it).

A word on debugging
===================


Before I finish up I want to mention a few things about debugging with avr-gdb. This project was the first time I had ever needed to use an simulator and debugger to even get the program to run. It would have been impossible to write this using an actual device since very little is revealed when operating the device. Here are a few things I learned\:


* avr-gdb is not perfect. For example, it is confused by the huge number of push statements at the beginning of kos_dispatch and will crash if stepped into that function (if it receives a break inside kos_dispatch that seems to work sometimes). This is due to avr-gdb attempting to decode the stack and finding that the frame size of the function is too big. It's weird and I didn't quite understand why that limitation was there, so I didn't really muck around with it. This made debugging the dispatcher super difficult.


* Stack bugs are hard to find. *I would recommend placing a watch on the top of your stack (the place where the variable actually points) and then setting that value to something unlikely like 0xAA.* If you see this value modified, you know that there is a problem since you are about to exceed your stack size. I spent hours staring at a problem with that semaphore example above before I realized that the idle task stack had encroached on the semaphore variables. Even then, I was looking at something totally different and just noticed that the stack pointer was too small. As it turns out, my original stack size of 48 was too small. The dispatcher will always require at least 35 free bytes on the stack and any ISR that calls a function will require at least 17 bytes due to the way that functions are called in avr-gcc. 35+17 = 52 which is greater than 48...so yeah. Not good.


* Simavr is pretty good. It supports compiling a program that embeds simavr which can be used to emulate the hardware around the microcontroller rather than just the microcontroller itself. I didn't use this functionality for this project, but that is a seriously cool thing.




.. _conclusion:

Conclusion
==========


This has been a long post, but it is a complicated topic. Writing something like this is actually considered writing an operating system (albeit just the kernel portion and a small one at that) and the debug along for just this post took me a while. One must have a good knowledge of how exactly the processor works. I found my knowledge lacking, actually, and I learned a lot about how the AVR works. The other thing is that things like concurrency and interrupts must be considered from the very beginning. They can't be an afterthought.

The scheduler and dispatcher I have described here are not perfect nor are they the most optimal efficient design. For one thing, my design uses a huge amount of RAM compared to other RTOS options. My scheduler and dispatcher are also inefficient, with the scheduler having an O(N) complexity depending on the number of tasks. My structure does, however, allow for O(1) time when suspending a task (although I question the utility of this...it worked better with the 8086 scheduler I made for class than with the AVR). Another problem is that kos_dispatch will not work with avr-gdb if the program is stopped during this function (it has a hard time decoding the function prologue because of the large number of push instructions). I haven't found a solution to this problem and it certainly made debugging a little more difficult.

So, now that I've told you some of what's wrong with the above, here are two RTOS which can be used with the AVR and are well tested\:


* `FemtoOS <http://www.femtoos.org/>`__. This is an extremely tiny and highly configurable RTOS. The bare implementation needs only 270 bytes of flash and 10 bytes of RAM. Ridiculous! My only serious issue with it is that it is GPLv3 licensed and due to how the application is compiled, licensing can be troublesome unless you want to also be GPLv3.


* `FreeRTOS <http://www.freertos.org/>`__. Very popular RTOS that has all sorts of support for many processors (ARM, PPC, AVR...you name it). I've never used it myself, but it also seems to have networking support and stuff like that. The site says that it's "market leading."



Anyway, I hope that this article is useful and as usual, any suggestions and such can be left in the comments. As mentioned before, the code for this article can be found on github here\: `https\://github.com/kcuzner/kos-avr <https://github.com/kcuzner/kos-avr>`__

.. rstblog-settings::
   :title: Writing a preemptive task scheduler for AVR
   :date: 2015/12/31
   :url: /2015/12/31/writing-a-preemptive-task-scheduler-for-avr