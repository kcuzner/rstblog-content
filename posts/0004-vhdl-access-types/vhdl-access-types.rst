.. rstblog-settings::
   :title: Using "access" types and "new" in VHDL
   :url: vhdl-access-types
   :date: 9 March 2025
   :tags: vhdl, fpga

This is a topic where the information available on the internet is either
nonexistent, inadequate, or incomplete. Perhaps that's because if you need to
use these, you probably already know how to do so. Or perhaps you're
referencing the LRM or another resource which clearly explains how to use them.

Anyway, for the uninitiated, in the VHDL hardware description language there is
a way to perform dynamic memory management, an ability typically used during
simulations. This can be used to implement lower level structures such as
dynamically sized arrays or higher level constructs such as queues.

Here is an example of declaring a self-referential record, an access type to
reference an instance of that record, and an array type of references to those
records. To make things easier to relate to other languages which the reader
might be more familar with, I've put the standard C++ term for a few constructs
in parenthesis.

.. code-block:: vhdl

    type Record_t; -- Incomplete type ("forward") declaration
    type RecordAcc_t is access Record_t; -- Access ("pointer") type which references Record_t
    type Record_t is record -- Actual declaration of Record_t
        Data : string;
        NextRecord : RecordAcc_t; -- Pointer to another Record_t
    end record;
    type RecordAccArray_t is array (integer range <>) of RecordAcc_t; -- Array of pointers
    type RecordAccArrayAcc_t is access RecordAccArray_t; -- Access to an array of pointers

############################################################
Allocation and Deallocation
############################################################

Allocating storage to be pointed to by a reference type is straightforward: Just use ``new``!

.. code-block:: vhdl

    variable VarRecordAccDefault : RecordAcc_t := new;
    variable VarRecordAcc : RecordAcc_t := new Record_t'(Data => "hi", NextRecord => null);
    variable VarRecordAryAcc : RecordAccArrayAcc_t := new RecordAccArray_t(0 to 15);

There a few ways to use ``new``:

* ``new;``: This is only valid for non-array access types. The default value will be used;

* ``new TypeName_t'(...);``: This allows specifying the initial value of the
  allocated type. If the type is an array, this can also be used to initialize
  the value of that array (i.e. ``new string'("HI");``), constraining it to the
  range of the initial value.

* ``new TypeArrayName_t(<range>);``: When allocating an array type the range
  must be specified if an initial value isn't supplied. I *think* null-length
  arrays are allowed, but in any case, you can't get away with not specifying
  range at this point and must supply it.

When calling ``new``, this dynamically allocates storage and so like other
languages it's typically necessary to ``deallocate`` the storage when it's no
longer needed. Be sure that no other access variable is pointing at that
storage when it's deallocated, as it'll be pointing to a region of memory that
may be reallocated (so it'll be garbage).


.. note::
   :class: alert alert-info

   In VHDL-2017, a garbage collector is specified and so calling deallocate is
   not necessary to avoid memory leaks *if your simulator implements that part
   of the spec*.
   
   This should simplify cases where the pointer may have been copied to another
   variable (i.e. two variables of an access type point to the same memory.

############################################################
Using referenced storage
############################################################

There are three ways to access the storage: By naming a sub-element, an array
access (``(..)``), or using ``.all``.

.. code-block:: vhdl

    report "The value of Record_t.Data is " & VarRecordAcc.Data;
    report "The length of the array is " & integer'image(VarRecordAryAcc.all'length);
    VarRecordAcc := VarRecordAryAcc(0);

Note that when using ``.all``, predefined attributes such as ``'length`` can be
used as shown.
