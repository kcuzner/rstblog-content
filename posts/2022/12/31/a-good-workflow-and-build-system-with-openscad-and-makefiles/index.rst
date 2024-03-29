.. rstblog-settings::
   :title: A good workflow and build system with OpenSCAD and Makefiles
   :date: 2022/12/31
   :url: /2022/12/31/a-good-workflow-and-build-system-with-openscad-and-makefiles
   :tags: hardware, programming

This is just a quick post, the blog isn't dead, I've just been busy. I've put together a reasonable OpenSCAD workflow that works for me and might work for others.

OpenSCAD is a 3D solid modeling program that performs computational geometry and is frequently used for describing models for 3D printing. It is a description language (and the program for compiling it) for solid shapes, procedurally generating them from primitive shapes like cubes, spheres, etc and mathematical operations such as unions and differences. Being fully text-based, it begs to live in version control and is usable through a CLI, leading to being able to be fully scripted. I started using OpenSCAD with the LED watch project and have since developed a fairly simple build system. It consists of two pieces\:


#. Special comments in a top-level OpenSCAD file designating which modules to build into STL files.


#. A makefile



I'll start with the Makefile. It's really straightforward and identical for each of my projects\:

.. code-block:: text

   SCAD=openscad
   BASEFILE=<path to top-level>.scad

   TARGETS=$(shell sed '/^module [a-z0-9_-]*\(\).*make..\?me.*$$/!d;s/module //;s/().*/.stl/' $(BASEFILE))

   all: ${TARGETS}

   .SECONDARY: $(shell echo "${TARGETS}" | sed 's/\.stl/.scad/g')

   include $(wildcard *.deps)

   %.scad: Makefile
   	printf 'use <$(BASEFILE)>\n$*();' > $@

   %.stl: %.scad
   	openscad -m make -o $@ -d $@.deps $<


In my top-level scad file, I then mark my top-level modules with a special comment\:

.. code-block:: text

   module Lid() { // `make` me
     ...
   }

The way this works is pretty straightforward. Just run "make" with no arguments\:


#. The makefile scans the top-level and creates a list of the names of the modules to be built into stl files. The suffix ".scad" is appended to each module, forming a list the top-level "all" targets


#. For each of these targets, it generates an scad file that includes the top-level file and instantiates the target module


#. When invoking openscad to build the stl from the target's scad file, a makefile deps file is generated by openscad. This file is included in the makefile so that later, when a dependency of the particular module changes, the stl will be updated according to the Makefile logic.



Armed with an STL, we can now go ahead and print. Typically, I put a fully assembled version of the top-levels in the top-level instantiation (since that isn't instantiated when including the file in the target's scad file) and point OpenSCAD directly to the top-level when editing.

The only non-automated part of this which is hard to check into version control is slicing the model. However, that's typically dictated per-print (and varies with wear and tear on the printer, the filament or resin used, etc), so I'm less motivated to figure out a good way to track it.

I have several examples of this workflow on github\:


* `https\://github.com/kcuzner/led-watch <https://github.com/kcuzner/led-watch>`__


* `https\://github.com/kcuzner/machi-koro-coins <https://github.com/kcuzner/machi-koro-coins>`__


* `https\://github.com/kcuzner/business-card-mandala <https://github.com/kcuzner/business-card-mandala>`__


