For the greater part of this week I have been trapped in a car driving across the United States for my sister's wedding. Of course, I had my trusty netbook with me and so I decided to do some programming. After discovering that I had unwittingly installed tons of documentation in my /usr/share/doc folder (don't you love those computer explorations that actually reveal something?), I started building yet another rendition of Tetris in Python. I did several things differently this time and the code is actually readable and I feel like some structure things I learned/discovered/re-discovered should be shared here.

Game State Management
---------------------

One problem that has constantly plagued my weak attempts at games has been an inability to do menus and manage whether the game is paused or not in a reasonably simple manner. Of course, I could always hack something together, but I could also write the whole thing in assembly language or maybe write it all as one big function in C. The issue is that if I program myself into a hole, I usually end up giving up a bit unless I am getting paid (then I generally bother thinking before programming so that I don't waste people's time). After finishing the game logic and actually getting things to work with the game itself, I remembered a funny tutorial I was once doing for OGRE which introduced a very simple game engine. The concept was one of a "stack" of game states. Using this stack, your main program basically injects input into and then asks a rendering from the state on the top of the stack. The states manipulate the stack, pushing a new state or popping themselves. When the stack is empty, the program exits.

My game state stack works by using an initial state that loads the resources (the render section gives back a loading screen). After it finishes loading the resources, it asks the manager to pop itself from the stack and then push on the main menu state. The menu state is quite simple\: It displays several options where each option either does something immediate (like popping the menu from the stack to end the program in the case of the Quit option) or something more complex (like pushing a sub-menu state on to create a new game with some settings). After that there are states for playing the game, viewing the high scores, etc.

The main awesome thing about this structure is that switching states is so easy. Want to pause the game? Just push on a state that doesn't do anything until it receives a key input or something, after which it pops itself. Feel like doing a complex menu system? The stack keeps track of the "breadcrumbs" so to speak. Never before have I been able to actually create an easily extensible/modification-friendly game menu/management system that doesn't leave me with a headache later trying to understand it or unravel my spaghetti code.

The second awesome thing is that this helps encourage an inversion of control. Rather than the state itself dictating when it gets input or when it renders something, the program on top of it can choose whether it wants to render that state or whether it wants to give input to that state. I ended up using the render function like a game loop function as well and so if I wanted a state to sort of "pause" execution, I could simply stop telling it to render (usually by just pushing a state on top of it). My main program (in Python) was about 25 lines long and took care of setting up the window, starting the game states, and then just injecting input into the game state and asking the state to render a window. The states themselves could choose how they wanted to render the window or even if they wanted to (that gets into the event bubbling section which is next). It is so much easier to operate that way as the components are loosely tied to one another and there is a clear relationship between them. The program owns the states and the states know nothing about about the program driving them...only that their input comes from somewhere and the renderings they are occasionally asked to do go somewhere.

Event bubbling
--------------

When making my Tetris game, I wanted an easy to way to know when to update or redraw the screen rather than always redrawing it. My idea was to create an event system that would "notice" when the game changed somehow\: whether a block had moved or maybe the score changed. I remembered of two event systems that I really really liked\: C#'s event keyword plus delegate thing and Javascript's event bubbling system. Some people probably hate both of those, but I have learned to love them. Mainly, its just because I'm new to this sort of thing and am still being dazzled by their plethora of uses. Using some knowledge I gleaned from my database abstraction project about the fun data model special function names in Python, I created the following\:

code-block::

    class EventDispatcher(object):
        """
        Event object which operates like C# events

        "event += handler" adds a handler to this event
        "event -= handler" removes a handler from this event
        "event(obj)" calls all of the handlers, passing the passed object

        Events may be temporarily suppressed by using them in a with
        statement. The context returned will be this event object.
        """
        def __init__(self):
            """
            Initializes a new event
            """
            self.__handlers = []
            self.__supress_count = 0
        def __call__(self, e):
            if self.__supress_count > 0:
                return
            for h in self.__handlers:
                h(e)
        def __iadd__(self, other):
            if other not in self.__handlers:
                self.__handlers.append(other)
            return self
        def __isub__(self, other):
            self.__handlers.remove(other)
            return self
        def __enter__(self):
            self.__supress_count += 1
            return self
        def __exit__(self, exc_type, exc_value, traceback):
            self.__supress_count -= 1

My first thought when making this was to do it like C# events\: super flexible, but no defined "way" to do them. The event dispatcher uses the same syntax as the C# events (+=, -= or __iadd__, __isub__) to add/remove handlers and also to call each handler (() or __call__). It also has the added functionality of optionally suppressing events by using them inside a "with" statement (which may actually be breaking the pattern, but I needed it to avoid some interesting redrawing issues). I would add EventDispatcher objects to represent each type of event that I wanted to catch and then pass an Event object into the event to send it off to the listening functions. However, I ran into an issue with this\: Although I was able to cut down the number of events being sent and how far they propagated, I would occasionally lose events. The issue this caused is that my renderer was listening to find out where it should "erase" blocks and where it should "add" blocks and it would sometimes seem to forget to erase some of the blocks. I later discovered that I had simply forgotten to call the event during a certain function which was called periodically to move the Tetris blocks down, but even so, it got my started on the next thing which I feel is better.

Javascript events work by specifying types of events, a "target" or object in the focus of the event, and arguments that get passed along with the event. The events then "bubble" upward through the DOM, firing first for a child and then for the parent of that child until it reaches the top element. The advantage of this is that if one wants to know, for example, if the screen has been clicked, a listener doesn't have to listen at the lowest leaf element of each branch of the DOM; it can simply listen at the top element and wait for the "click" event to "bubble" upwards through the tree. After my aforementioned issue I initially thought that I was missing events because my structure was flawed, so I ended up re-using the above class to implement event bubbling by doing the following\:

code-block::

    class Event(object):
        """
        Instance of an event to be dispatched
        """
        def __init__(self, target, name, *args, **kwargs):
            self.target = target
            self.name = name
            self.args = args
            self.kwargs = kwargs

    class EventedObject(object):
        def __init__(self, parent=None):
            self.__parent = parent
            self.event = EventDispatcher()
            self.event += self.__on_event
        def __on_event(self, e):
            if hasattr(self.__parent, 'event'):
                self.__parent.event(e)
        @property
        def parent(self):
            return self.__parent
        @parent.setter
        def parent(self, value):
            l = self.parent
            self.__parent = value
            self.event(Event(self, "parent-changed", current=self.parent, last=l))

The example here is the object from which all of my moving game objects (blocks, polyominoes, the game grid, etc) derive from. It defines a single EventDispatcher, through which Event objects are passed. It listens to its own event and when it hears something, it activates its parent's event, passing through the same object that it received. The advantage here is that by listening to just one "top" object, all of the events that occurred for the child objects are passed to whatever handler is attached to the top object's dispatcher. In my specific implementation I had each block send an Event up the pipeline when the were moved, each polyomino send an Event when it was moved or rotated, and the game send an Event when the score, level, or line count was changed. By having my renderer listen to just the game object's EventDispatcher I was able to intercept all of these events at one location.

The disadvantage with this particular method is that each movement has a potentially high computational cost. All of my events are synchronous since Python doesn't do true multithreading and I didn't need a high performance implementation. It's just method calls, but there is a potential for a stack overflow if either a chain of parents has a loop somewhere or if I simply have too tall of an object tree. If I attach too many listeners to a single EventDispatcher, it will also slow things down.

Another problem I have here has to do with memory leaks which I believe I have (I haven't tested it and this is entirely in my head, thinking about the issues). Since I am asking the EventDispatcher to add a handler which is a bound method to the object which owns it, there is a loop there. In the event that I forget all references to the EventedObject, the reference count will never decrease to 0 since the EventDispatcher inside the EventedObject still holds a reference to that same EventedObject inside the bound method. I would think that this could cause garbage collection to never happen. Of course, they could make the garbage collector really smart and notice that the dependency tree here is a nice orphan tree detached from the rest and can all be collected. However, if it is a dumb garbage collector, it will probably keep it around. This isn't a new issue for me\: I ran into it with doing something like this on one of my C# projects. However, the way I solved it there was to implement the IDisposable interface and upon disposal, unsubscribe from all events that created a circular dependency. The problem there was worse because there wasn't a direct exclusive link between the two objects like there is with this one (here one is a property of the other (strong link) and the other only references a bound method to its partner (weak...kinda...link)).

Overall, even though there are those disadvantages, I feel that the advantage gained by having all the events in one place is worth it. In the future I will create "filters" that can be attached to handlers as they are subscribed to avoid calling the handlers for events that don't match their filter. This is similar to Javascript in that handlers can be used to catch one specific type of event. However, mine differs in that in the spirit of Python duck typing, I decided to make no distinction between types of events outside of a string name that identifies what it is. Since I only had one EventDispatcher per object, it makes sense to only have one type of event that will be fed to its listeners. The individual events can then just be differentiated by a property value. While this feels flaky to me since I usually feel most comfortable with strong typing systems, it seems to be closer to what Python is trying to do.

Conclusion
----------

I eventually will put up this Tetris implementation as a gist or repository on github (probably just a gist unless it gets huge...which it could). So far I have learned a great deal about game design and structure, so this should get interesting as I explore other things like networking and such.

.. rstblog-settings::
   :title: Lessons in game design...in a car!
   :date: 2013/05/03
   :url: /2013/05/03/lessons-in-game-design-in-a-car