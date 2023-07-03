I've been using kicad for just about all of my designs for a little over 5 years now. It took a little bit of a learning curve, but I've really come to love it, especially with the improvements by CERN that came out in version 4. One of the greatest features, in my opinion, is the Python Scripting Console in the PCB editor (pcbnew). It gives (more or less) complete access to the design hierarchy so that things like footprints can be manipulated in a scripted fashion.

In my most recent design, the LED Watch, I used this to script myself a tool for arranging footprints in a circle. What I want to show today was how I did it and how to use it so that you can make your own scripting tools (or just arrange stuff in a circle).

***The python console can be found in pcbnew under Tools->Scripting Console.***

**Step 1\: Write the script**

When writing a script for pcbnew, it is usually helpful to have some documentation. Some can be found `here <http://ci.kicad-pcb.org/job/kicad-doxygen/ws/build/pcbnew/doxygen-python/html/namespacepcbnew.html>`_, though I mostly used "dir" a whole bunch and had it print me the structure of the various things once I found the points to hook in. The documentation is fairly spartan at this point, so that made things easier.

Here's my script\:

.. code-block:: {lang}



   #!/usr/bin/env python2

   # Random placement helpers because I'm tired of using spreadsheets for doing this
   #
   # Kevin Cuzner

   import math
   from pcbnew import *

   def place_circle(refdes, start_angle, center, radius, component_offset=0, hide_ref=True, lock=False):
       """
       Places components in a circle
       refdes: List of component references
       start_angle: Starting angle
       center: Tuple of (x, y) mils of circle center
       radius: Radius of the circle in mils
       component_offset: Offset in degrees for each component to add to angle
       hide_ref: Hides the reference if true, leaves it be if None
       lock: Locks the footprint if true
       """
       pcb = GetBoard()
       deg_per_idx = 360 / len(refdes)
       for idx, rd in enumerate(refdes):
           part = pcb.FindModuleByReference(rd)
           angle = (deg_per_idx * idx + start_angle) % 360;
           print "{0}: {1}".format(rd, angle)
           xmils = center[0] + math.cos(math.radians(angle)) * radius
           ymils = center[1] + math.sin(math.radians(angle)) * radius
           part.SetPosition(wxPoint(FromMils(xmils), FromMils(ymils)))
           part.SetOrientation(angle * -10)
           if hide_ref is not None:
               part.Reference().SetVisible(not hide_ref)
       print "Placement finished. Press F11 to refresh."




There are several arguments to this function\: a list of reference designators (["D1", "D2", "D3"] etc), the angle at which the first component should be placed, the position in mils for the center of the circle, and the radius of the circle in mils. Once the function is invoked, it will find all of the components indicated in the reference designator list and arrange them into the desired circle.

**Step 2\: Save the script**

In order to make life easier, it is best if the script is saved somewhere that the pcbnew python interpreter knows where to look. I found a good location at "/usr/share/kicad/scripting/plugins", but the list of all paths that will be searched can be easily found by opening the python console and executing "import sys" followed by "print(sys.path)". Pick a path that makes sense and save your script there. I saved mine as "placement_helpers.py" since I intend to add more functions to it as situations require.

**Step 3\: Open your PCB and run the script**

Before you can use the scripts on your footprints, they need to be imported. Make sure you execute the "Read Netlist" command before continuing.

The scripting console can be found under Tools->Scripting Console. Once it is opened you will see a standard python (2) command prompt. If you placed your script in a location where the Scripting Console will search, you should be able to do something like the following\:

.. code-block:: {lang}



   PyCrust 0.9.8 - KiCAD Python Shell
   Python 2.7.13 (default, Feb 11 2017, 12:22:40) 
   [GCC 6.3.1 20170109] on linux2
   Type "help", "copyright", "credits" or "license" for more information.
   >>> import placement_helpers
   >>> placement_helpers.place_circle(["D1", "D2"], 0, (500, 500), 1000)
   D1: 0
   D2: 180
   Placement finished. Press F11 to refresh.
   >>>


Now, pcbnew may not recognize that your PCB has changed and enable the save button. You should do something like lay a trace or some other board modification so that you can save any changes the script made. I'm sure there's a way to trigger this in Python, but I haven't got around to trying it yet.

**Conclusion**

Hopefully this brief tutorial will either help you to place components in circles in Kicad/pcbnew or will help you to write your own scripts for easing PCB layout. Kicad can be a very capable tool and with its new expanded scripting functionality, the sky seems to be the limit.

.. rstblog-settings::
   :title: Arranging components in a circle with Kicad
   :date: 2017/04/28
   :url: /2017/04/28/arranging-components-in-a-circle-with-kicad