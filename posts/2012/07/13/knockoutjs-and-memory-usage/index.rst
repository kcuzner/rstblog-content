.. rstblog-settings::
   :title: KnockoutJS and Memory Usage
   :date: 2012/07/13
   :url: /2012/07/13/knockoutjs-and-memory-usage

Recently at work I have been using `KnockoutJS <http://www.knockoutjs.com>`__ for structuring my Javascript. To be honest, it is probably the best thing since jQuery in my opinion in terms of cutting down quantity of code that one must write for an interface. The only problem is, however, that it is really really easy to make a page use a ridiculous amount of memory. After thinking and thinking and trying different things I have realized the proper way to do things with more complex pages.

The KnockoutJS documentation is really great, but it is more geared towards the simple stuff/basics so that you can get started quickly and doesn't talk much about more complex stuff which leads to comments like the answer `here <http://stackoverflow.com/questions/5112899/knockout-js-vs-backbone-js-vs>`__ saying that it isn't so good for complex user interfaces. When things get more complex, like interfacing it with existing applications with different frameworks or handling very very large quantities of data, it doesn't really say much and kind of leaves one to figure it out on their own. I have one particular project that I was working on which had the capability to display several thousand items in a graph/tree format while calculating multiple inheritance and parentage on several values stored in each item object. In chrome I witnessed this page use 800Mb easily. Firefox it was about the same. Internet explorer got to 1.5Gb before I shut if off. Why was it using so much memory? Here is an example that wouldn't use a ton of memory, but it would illustrate the error I made\:

Example
-------


Javascript (note that this assumes usage of jQuery for things like AJAX)\:

.. code-block:: 

   function ItemModel(id, name) {
       var self = this;
       this.id = id;
       this.name = ko.observable(name);
       this.editing = ko.observable(false);
       this.save = function () {
           //logic that creates a new item if the id is null or just saves the item otherwise
           //through a call to $.ajax
       }
   }

   function ItemContainerModel(id, name, items) {
       var self = this;
       this.id = id;
       this.name = ko.observable(name);
       this.editing(true);
       this.items = ko.observableArray(items);
       this.save = function () {
           //logic that creates a new item container if the id is null or just saves the item container otherwise
           //through a call to $.ajax
       }
       this.add = function() {
           var aNewItem = new ItemModel(null, null);
           aNewItem.editing(true);
           self.items.push(aNewItem);
       }
       this.remove = function (item) {
           //$.ajax call to the server to remove the item
           self.items.remove(item);
       }
   }

   function ViewModel() {
       var self = this;
       this.containers = ko.observableArray();
       var blankContainer = new ItemContainerModel(null, null, []);
       this.selected = ko.observable(blankContainer);
       this.add = function () {
           var aNewContainer = new ItemContainerModel(null, null, []);
           aNewContainer.editing(true);
           self.containers.push(aNewContainer);
       }
       this.remove = function(container) {
           //$.ajax call to the server to remove the container
           self.containers.remove(container);
       }
       this.select = function(container) {
           self.selected(container);
       }
   }

   $(document).ready( function() {
       var vm = new ViewModel();
       ko.applyBindings(vm);
   });

Now for a really simple view (sorry for lack of styling or the edit capability, but hopefully the point will be clear)\:

.. code-block:: 

   <a data-bind="click: add" href="#">Add container</a>
   <ul data-bind="foreach: containers">
       <li><span data-bind="text: name"></span> <a data-bind="click: save" href="#">Save</a> <a data-bind="click: $parent.remove" href="#">Remove</a></li>
   </ul>
   <div data-bind="with: selected">
       <a data-bind="click: add" href="#">Add item</a>
       <div data-bind="foreach: items">
           <div data-bind="text: name"></div>
           <a data-bind="click: save" href="#"></a>
           <a data-bind="click: $parent.remove" href="#">Remove</a>
       </div>
   </div>


The Problem
-----------


So, what is the problem here with this model? It works just fine... you can add, remove, save, and display items in a collection of containers. However, if this view was to contain, say, 1000 containers with 1000 items each, what would happen? Well, we would have a lot of memory usage. Now, you could say that would happen no matter what you did and you wouldn't be wrong. The question here is, how much memory is it going to use? The example above is not nearly the most efficient way of structuring a model and will consume much more memory than is necessary. Here is why\:

Note how the saving, adding, and removing functions are implemented. They are declared attached to the *this* variable inside each object. Now, in languages like C++, C#, or Java, adding functions to an object (that is what attaching the function to the *this* variable does in Javascript if you aren't as familiar with objects in Javascript) will not cause increased memory usage generally, but would rather just make the program size larger since the classes would all share the same compiled code. However, Javascript is different.

Javascript uses what are called `closures <http://www.javascriptkit.com/javatutors/closures.shtml>`__. A closure is a very very powerful tool that allows for intuitive accessing and scoping of variables seen by functions. I won't go into great detail on the awesome things you can do with these since many others have explained it better than I ever could. Another thing that Javascript does is that it treats functions as "1st class citizens" which essentially means that Javascript sees no difference between a function and a variable. All are alike. This allows you to assign a variable to point to a function (var variable = function () { alert("hi"); };) so that you could call variable() and it would execute the function as if "variable" was the name of the function.

Now, tying all that together here is what happens\: Closures "wrap up" everything in the scope of a function when it is declared so that it has access to all the variables that were able to be seen at that point. By treating functions almost like variables and assigning a function to a variable in the *this* object, you extend the *this* object to hold whatever that variable holds. Declaring the functions inline like we see in the add, remove, and save functions while in the scope of the object causes them to become specific to the particular instance of the object. Allow me to explain a bit\: Every time that you call 'new ItemModel(...)', in addition to creating a new item model, it creates a new function\: this.save. Every single ItemModel created has its very own instance of this.save. They don't share the same function. Now, when we create a new ItemContainerModel, 3 new functions are also created specific to each instance of the ItemContainerModel. That basically means that if we were to create two containers with 3 items each inside we would get 8 functions created (2 for the items, 6 for the containers). In some cases this is very useful since it lets you create custom methods for each oject. To use the example of the item save function, instead of having to access the 'id' variable as stored in the object, it could use one of the function parameters in 'function ItemModel(...)' inside the save function. This is due to the fact that the closure wrapped up the variables passed into the ItemModel function since they were in scope to the this.save function. By doing this, you could have the this.save function modify something different for each instance of the ItemModel. However, in our situation this is more of an issue than a benefit\: We just redundantly created 4 functions that do the exact same thing as 4 other functions that already exist. Each of those functions consumes memory and after a thousand of these objects are made, that usage gets to be quite large.

Solution
--------


How can this be fixed? What we need to do is to reduce the number of anonymous functions that are created. We need to remove the save, add, and remove functions from the ItemModel and ItemContainerModel. As it turns out, the structure of Knockout is geared towards doing something which can save us a lot of memory usage.

When an event binding like 'click' is called, the binding will pass an argument into the function which is the model that was being represented for the binding. This allows us to know who called the method. We already see this in use in the example with the remove functions\: the first argument was the model that was being referenced by the particular click when it was called. We can use this to fix our problem.

First, we must remove all functions from the models that will be duplicated often. This means that the add, remove, and save functions in the ItemContainer and the save function in the Item models have to go. Next, we create back references so that each contained object outside the viewmodel and its direct children knows who its daddy is. Here is an example\:

.. code-block:: 

   function ItemModel(id, name, container) {
       //note the addition of the container argument

       //...keep the same variables as before, but remove the this.save stuff

       this.container = container; //add this as our back reference
   }

   function ItemContainerModel(id, name) {
       //NOTE 1: this didn't need an argument for a back reference. This is because it is a direct child of the root model and
       //since the root model contains the functions dealing with adding and removing containers, it already knows the array to
       //manipulate

       //NOTE 2: the items argument has been removed. This is so that the container can be created before the items and the back
       //reference above can be completed. So, the process for creating a container with items is now: create container, create
       //items with a reference to the container, and then add the items to the container by doing container.items(arrayOfItems);

       //remove all the functions from this model as well
   }

   function ViewModel() {
       //all the stuff we already had here from the example above stays

       //we add the following:
       this.saveItem = function (item) {
           //instead of using self.id and self.name() when creating our ajax request, we use item.id and item.name()
       }
       this.saveContainer = function(container) {
           //instead of using self.id and self.name() when creating our ajax request, we use item.id and item.name()
       }
       this.addItem = function(container) {
           var aNewItem = new ItemModel(null, null, container);
           aNewItem.editing(true);
           container.items.push(aNewItem);
       }
       this.removeItem = function(item) {
           //create a $.ajax request to remove the item based on its id
           item.container.items.remove(item); //using our back reference, we can remove the item from its parent container
       }
   }

The view will now look like so (note that the bindings to functions now reference $root\: the main ViewModel)\:

.. code-block:: 

   <a data-bind="click: add" href="#">Add container</a>
   <ul data-bind="foreach: containers">
       <li><span data-bind="text: name"></span> <a data-bind="click: $root.saveContainer href="#">Save</a> <a data-bind="click: $root.remove" href="#">Remove</a></li>
   </ul>
   <div data-bind="with: selected">
       <a data-bind="click: $root.addItem" href="#">Add item</a>
       <div data-bind="foreach: items">
           <div data-bind="text: name"></div>
           <a data-bind="click: $root.saveItem" href="#"></a>
           <a data-bind="click: $root.removeItem" href="#">Remove</a>
       </div>
   </div>

Now, that wasn't so hard was it? What we just did was we made it so that we only use memory for the variables and don't have to create any closures for functions. By moving the individual model functions down to the ViewModel we kept the same functionality as before, did not increase our code size, and significantly reduced memory usage when the model starts to get really big. If we were to create 2 containers with 3 items each, we create no additional functions from the 4 inside the ViewModel. The only memory consumed by each model is the space needed for storing the actual values represented (id, name, etc).

Summary
-------


In summary, to reduce KnockoutJS memory usage consider the following\:


* Reduce the number of functions inside the scope of each model. Move functions to the lowst possible place in your model tree to avoid unnecessary duplication.


* Avoid closures inside heavily duplicated models like the plague. I know I didn't cover this above, but be careful with computed observables and their functions. It may be better to declare the bulk of a function for a computed observable outside the function and then use it like so\: 'this.aComputedObservable = ko.computed(function () { return aFunctionThatYouCreated(self); });' where self was earlier declared to be *this* in the scope of the model itself. That way the computed observable function still has access to the contents of the model while keeping the actual memory usage in the model itself small.


* Be very very slim when creating your model classes. Only put data there that will be needed.


* Consider pagination or something. If you don't need 1000 objects displayed at the same time, don't display 1000 objects at the same time. There is a server there to store the information for a reason.


