.. rstblog-settings::
   :title: Extreme Attributed Metadata with Autofac
   :date: 2014/05/19
   :url: /2014/05/19/extreme-attributed-metadata-autofac


Introduction
============


If you are anything like me, you love reflection in any programming language. For the last two years or so I have been writing code for work almost exclusively in C# and have found its reflection system to be a pleasure to use. Its simple, *can* be fast, and can do so much.

I recently started using `Autofac <http://autofac.org/>`__ at work to help achieve `Inversion of Control <http://martinfowler.com/articles/injection.html>`__ within our projects. It has honestly been the most life changing C# library (sorry Autofac, jQuery and Knockout still take the cake for "life-changing in all languages") I have ever used and has changed the way I decompose problems when writing programs.

This article will cover some very interesting features of the Autofac Attributed Metadata module. It is a little lengthy, so I have here what will be covered\:


* What is autofac?


* Attributed Metadata\: The Basics


* The IMetadataProvider interface


* IMetadataProvider\: Making a set of objects


* IMetadataProvider\: Hierarchical Metadata




What is Autofac?
================


This post assumes that the reader is at least passingly familiar with Autofac. However, I will make a short introduction\: Autofac allows you to "compose" your program structure by "registering" components and then "resolving" them at runtime. The idea is that you define an interface for some object that does "something" and create one or more classes that implement that interface, each accomplishing the "something" in their own way. Your parent class, which needs to have one of those objects for doing that "something" will ask the Autofac container to "resolve" the interface. Autofac will give back either one of your implementations or an IEnumerable of all of your implementations (depending on how you ask it to resolve). The "killer feature" of Autofac, IMO, is being able to use constructor arguments to recursively resolve the "dependencies" of an object. If you want an implementation of an interface passed into your object when it is resolved, just put the interface in the constructor arguments and when your object is resolved by Autofac, Autofac will resolve that interface for you and pass it in to your constructor. Now, this article isn't meant to introduce Autofac, so I would definitely recommend reading up on the subject.

Attributed Metadata\: The Basics
================================


One of my most favorite features has been `Attributed Metadata <https://github.com/autofac/Autofac/wiki/Attribute-Metadata>`__. Autofac allows Metadata to be included with objects when they are resolved. Metadata allows one to specify some static parameters that are associated with a particular implementation of something registered with the container. This Metadata is normally created during registration of the particular class and, without this module, must be done "manually". The Attributed Metadata module allows one to use custom attributes to specify the Metadata for the class rather than needing to specify it when the class is registered. This is an absurdly powerful feature which allows for doing some pretty interesting things.

For my example I will use a "extendible" letter formatting program that adds some text to the content of a "letter". I define the following interface\:

.. code-block:: c#



   interface ILetterFormatter
   {
       string FormatLetter(string content);
   }

This interface is for something that can "format" a letter in some way. For starters, I will define two implementations\:

.. code-block:: c#



   class ImpersonalLetterFormatter : ILetterFormatter
   {
       public string MakeLetter(string content)
       {
           return "To Whom It May Concern:nn" + content;
       }
   }

   class PersonalLetterFormatter : ILetterFormatter
   {
       public string MakeLetter(string content)
       {
           return "Dear Individual,nn" + content;
       }
   }

Now, here is a simple program that will use these formatters\:

.. code-block:: c#



   class MainClass
   {
       public static void Main (string[] args)
       {
           var builder = new ContainerBuilder();

           //register all ILetterFormatters in this assembly
           builder.RegisterAssemblyTypes(typeof(MainClass).Assembly)
               .Where(c => c.IsAssignableTo<ILetterFormatter>())
               .AsImplementedInterfaces();

           var container = builder.Build();

           using (var scope = container.BeginLifetimeScope())
           {
               //resolve all formatters
               IEnumerable<ILetterFormatter> formatters = scope.Resolve<IEnumerable<ILetterFormatter>>();

               //What do we do now??? So many formatters...which is which?
           }
       }
   }

Ok, so we have ran into a problem\: We have a list of formatters, but we don't know which is which. There are a couple different solutions\:


* Use the "is" test or do a "soft cast" using the "as" operator to a specific type. This is bad because it requires that the resolver know about the specific implementations of the interface (which is what we are trying to avoid)


* Just choose one based on order. This is bad because the resolution order is just as guaranteed as reflection order in C#...which is not guaranteed at all. We can't be sure they will be resolved in the same order each time.


* Use metadata at registration time and resolve it with metadata. The issue here is that if we used RegisterAssemblyTyps like above, it makes registration difficult. Also, once we get any sizable number of things registered with metadata, it becomes unmanageable IMO.


* Use attributed metadata! Example follows...



We define another class\:

.. code-block:: c#



   [MetadataAttribute]
   sealed class LetterFormatterAttribute : Attribute
   {
       public string Name { get; private set; }

       public LetterFormatterAttribute(string name)
       {
           this.Name = name;
       }
   }

Marking it with System.ComponetModel.Composition.MetadataAttributeAttribute (no, that's not a typo) will make the Attributed Metadata module place the public properties of the Attribute into the metadata dictionary that is associated with the class at registration time.

We mark the classes as follows\:

.. code-block:: c#



   [LetterFormatter("Impersonal")]
   class ImpersonalLetterFormatter : ILetterFormatter
   ...

   [LetterFormatter("Personal")]
   class PersonalLetterFormatter : ILetterFormatter
   ...



And then we change the builder to take into account the metadata by asking it to register the Autofac.Extras.Attributed.AttributedMetadataModule. This will cause the Attributed Metadata extensions to scan all of the registered types (past, present, and future) for MetadataAttribute-marked attributes and use the public properties as metadata\:

.. code-block:: c#



   var builder = new ContainerBuilder();

   builder.RegisterModule<AttributedMetadataModule>();

   builder.RegisterAssemblyTypes(typeof(MainClass).Assembly)
       .Where(c => c.IsAssignableTo<ILetterFormatter>())
       .AsImplementedInterfaces();

Now, when we resolve the ILetterFormatter classes, we can either use Autofac.Features.Meta<TImplementation> or Autofac.Features.Meta<TImplementation, TMetadata>. I'm a personal fan of the "strong" metadata, or the latter. It causes the metadata dictionary to be "forced" into a class rather than just directly accessing the metadata dictionary. This removes any uncertainty about types and such. So, I will create a class that will hold the metadata when the implementations are resolved\:

.. code-block:: c#



   class LetterMetadata
   {
       public string Name { get; set; }
   }

It would worthwhile to note that the individual properties must have a value in the metadata dictionary unless the DefaultValue attribute is applied to the property. For example, if I had an integer property called Foo an exception would be thrown when metadata was resolved since I have no corresponding Foo metadata. However, if I put DefaultValue(6) on the Foo property, no exception would be thrown and Foo would be set to 6.

So, we now have the following inside our using statement that controls our scope in the main method\:

.. code-block:: c#



   //resolve all formatters
   IEnumerable<Meta<ILetterFormatter, LetterMetadata>> formatters = scope.Resolve<IEnumerable<Meta<ILetterFormatter, LetterMetadata>>>();

   //we will ask how the letter should be formatted
   Console.WriteLine("Formatters:");
   foreach (var formatter in formatters)
   {
       Console.Write("- ");
       Console.WriteLine(formatter.Metadata.Name);
   }

   ILetterFormatter chosen = null;
   while (chosen == null)
   {
       Console.WriteLine("Choose a formatter:");
       string name = Console.ReadLine();
       chosen = formatters.Where(f => f.Metadata.Name == name).Select(f => f.Value).FirstOrDefault();

       if (chosen == null)
           Console.WriteLine(string.Format("Invalid formatter: {0}", name));
   }

   //just for kicks, we say the first argument  is our letter, so we format it and output it to the console
   Console.WriteLine(chosen.FormatLetter(args[0]));


The IMetadataProvider Interface
===============================


So, in the contrived example above, we were able to identify a class based solely on its metadata rather than doing type checking. What's more, we were able to define the metadata through attributes. However, this is old hat for Autofac. This feature has been around for a while.

When I was at work the other day, I needed to be able to handle putting sets of things into metadata (such as a list of strings). Autofac makes no prohibition on this in its metadata dictionary. The dictionary is of the type IDictionary<string, object>, so it can hold pretty much anything, including arbitrary objects. The problem is that the Attributed Metadata module had no way to do this easily. Attributes can only take certain types as constructor arguments and that seriously places a limit on what sort of things could be put into metadata via attributes easily.

I decided to remedy this and after submitting an idea for autofac `via a pull request <https://github.com/autofac/Autofac/pull/519>`__, having some discussion, changing the exact way to accomplish this goal, and fixing things up, my pull request was merged into autofac which resulted in a new feature\: The IMetadataProvider interface. This interface provides a way for metadata attributes to control how exactly they produce metadata. By default, the attribute would just have its properties scanned. However, if the attribute implemented the IMetadataProvider interface, a method will be called to get the metadata dictionary rather than doing the property scan. When an IMetadataProvider is found, the GetMetadata(Type targetType) method will be called with the first argument set to the type that is being registered. This allows the IMetadataProvider the opportunity to know which class it is actually applied to; something normally not possible without explicitly passing the attribute a Type in a constructor argument.

To get an idea of what this would look like, here is a metadata attribute which implements this interface\:

.. code-block:: c#



   [MetadataAttribute]
   class LetterFormatterAttribute : Attribute, IMetadataProvider
   {
       public string Name { get; private set; }

       public LetterFormatterAttribute(string name)
       {
           this.Name = name;
       }

       #region IMetadataProvider implementation

       public IDictionary<string, object> GetMetadata(Type targetType)
       {
           return new Dictionary<string, object>()
           {
               { "Name", this.Name }
           };
       }

       #endregion
   }

This metadata doesn't do much more than the original. It actually returns exactly what would be created via property scanning. However, this allows much more flexibility in how MetadataAttributes can provide metadata. They can scan the type for other attributes, create arbitrary objects, and many other fun things that I can't even think of.

IMetadataProvider\: Making a set of objects
===========================================


Perhaps the simplest application of this new IMetadataProvider is having the metadata contain a list of objects. Building on our last example, we saw that the "personal" letter formatter just said "Dear Individual" every time. What if we could change that so that there was some way to pass in some "properties" or "options" provided by the caller of the formatting function? We can do this using an IMetadataProvider. We make the following changes\:

.. code-block:: c#



   class FormatOptionValue
   {
       public string Name { get; set; }
       public object Value { get; set; }
   }

   interface IFormatOption
   {
       string Name { get; }
       string Description { get; }
   }

   interface IFormatOptionProvider
   {
       IFormatOption GetOption();
   }

   interface ILetterFormatter
   {
       string FormatLetter(string content, IEnumerable<FormatOptionValue> options);
   }

   [MetadataAttribute]
   sealed class LetterFormatterAttribute : Attribute, IMetadataProvider
   {
       public string Name { get; private set; }

       public LetterFormatterAttribute(string name)
       {
           this.Name = name;
       }

       public IDictionary<string, object> GetMetadata(Type targetType)
       {
           var options = targetType.GetCustomAttributes(typeof(IFormatOptionProvider), true)
               .Cast<IFormatOptionProvider>()
               .Select(p => p.GetOption())
               .ToList();

           return new Dictionary<string, object>()
           {
               { "Name", this.Name },
               { "Options", options }
           };
       }
   }

   //note the lack of the [MetadataAttribute] here. We don't want autofac to scan this for properties
   [AttributeUsage(AttributeTargets.Class, AllowMultiple = true)]
   sealed class StringOptionAttribute : Attribute, IFormatOptionProvider
   {
       public string Name { get; private set; }

       public string Description { get; private set; }

       public StringOptionAttribute(string name, string description)
       {
           this.Name = name;
           this.Description = description;
       }

       public IFormatOption GetOption()
       {
           return new StringOption()
           {
               Name = this.Name,
               Description = this.Description
           };
       }
   }

   public class StringOption : IFormatOption
   {
       public string Name { get; set; }

       public string Description { get; set; }

       //note that we could easily define other properties that
       //do not appear in the interface
   }

   class LetterMetadata
   {
       public string Name { get; set; }

       public IEnumerable<IFormatOption> Options { get; set; }
   }

Ok, so this is just a little bit more complicated. There are two changes to pay attention to\: Firstly, the FormatLetter function now takes a list of FormatOptionValues. The second change is what enables the caller of FormatLetter to know which options to pass in. The LetterFormatterAttribute now scans the type in order to construct its metadata dictionary by looking for attributes that describe what options it needs. I feel like the usage of this is best illustrated by decorating our PersonalLetterFormatter for it to have some metadata describing the options that it requires\:

.. code-block:: c#



   [LetterFormatter("Personal")]
   [StringOption(ToOptionName, "Name of the individual to address the letter to")]
   class PersonalLetterFormatter : ILetterFormatter
   {
       const string ToOptionName = "To";

       public string FormatLetter(string content, IEnumerable<FormatOptionValue> options)
       {
           var toName = options.Where(o => o.Name == ToOptionName).Select(o => o.Value).FirstOrDefault() as string;
           if (toName == null)
               throw new ArgumentException("The " + ToOptionName + " string option is required");

           return "Dear " + toName + ",nn" + content;
       }
   }

When the metadata for the PersonalLetterFormatter is resolved, it will contain an IFormatOption which represents the To option. The resolver can attempt to cast the IFormatOption to a StringOption to find out what type it should pass in using the FormatOptionValue.

This can be extended quite easily for other IFormatOptionProviders and IFormatOption pairs, making for a very extensible way to easily declare metadata describing a set of options attached to a class.

IMetadataProvider\: Hierarchical Metadata
=========================================


The last example showed that the IMetadataProvider could be used to scan the class to provide metadata into a structure containing an IEnumerable of objects. It is a short leap to see that this could be used to create hierarchies of arbitrary objects.

For now, I won't provide a full example of how this could be done, but in the future I plan on having a gist or something showing arbitrary metadata hierarchy creation.

Conclusion
==========


I probably use Metadata more than I should in Autofac. With the addition of the IMetadataProvider I feel like its quite easy to define complex metadata and use it with Autofac's natural constructor injection system. Overall, the usage of metadata & reflection in my programs has made them quite a bit more flexible and extendable and I feel like Autofac and its metadata system complement the built in reflection system of C# quite well.