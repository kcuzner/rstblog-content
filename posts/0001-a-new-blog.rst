.. rstblog-settings::
   :title: A New Blog
   :url: a-new-blog
   :date: 6 January 2024
   :tags: websites, server, python

For the past several years I've struggled with maintaining the wordpress blog
on this site. Starting 3 or 4 years ago the blog began to receive sustained
stronger than usual traffic from data centers trying to post comments or just
brute-forcing the admin login page. This peaked around 2021 when I finally
decided to turn off all commenting functionality. This cooled things down
except for requiring me to "kick" the server every few days as it ran out of
file handles due to some misconfiguration on my part combined with the spam
traffic.

This became annoying and I needed to find something that would be even lower
maintenance. To that end, I've written my first functioning blogging software
since 2006 or so. There is no dynamic content, all of it is statically
rendered, and the blog content itself is stored in GitHub with updates managed
using GitHub hooks. The content itself is written with ReStructured Text and I
think I've created a pretty easy-to-use and low-maintenance blog platform
(famous last words). Ask me in a decade if I was actually successful lol.

.. rstblog-break::

.. contents::

############################################################
Concept
############################################################

**************************************************
ReStructured Text
**************************************************

One of my biggest frustrations with wordpress, belive it or not, was its
WYSIWYG editor. While it looked good, I found it to be inconsistent and more
geared towards sharing opinions (and pictures) of coffee cups than presenting
technical content. Also, as time went on wordpress kept changing things about
its editor and not in ways that I liked. Furthermore, plugins and such for
things like code blocks that once worked stopped working over the course of the
15 years or so that I ran that blog.

To solve the editing problem, I turned to ReStructured Text, or ReST. This is
the markup language used in Python documentation (docutils) and by the Sphinx
documentation tool. I've been using it quite extensively at work in a crusade
against inadequate or badly maintained documentation and fell in love with the
expressiveness available in contrast to other solutions such as Markdown.

**************************************************
Content Management with Git
**************************************************

Having now chosen ReST as a markup language, the next problem was the editor
itself. Every time I've had to select an editor for web applications I end up
missing my editor of choice (``vim``). So, why not just allow myself to use
``vim`` as my editor for writing blog posts?

With that thought, the idea for how this blog would work began to form:

* I'd store the blog content in a git repository as loose ``rst`` files (one
  file per post) and images. Perhaps I'd organize the posts into folders and
  place the images next door to the relevant ``rst`` file.
* A custom ``rst`` directive would be used to configure blog settings such as
  the post date, post title, tags, and such. All metadata about a post could be
  stored in the ``rst`` file, eliminating the need for any kind of database
  to store that information.
* I'd have something, perhaps written in Python to keep things easy, which
  would be triggered by a push to the repository on GitHub via a webhook. It
  would download the repository storing the content and render it into HTML.
* More than just storing the ``rst``, the content repository could also store
  the entire website theme, written as `Jinja2
  <https://jinja.palletsprojects.com/en/3.1.x/>`_ templates. It could even store
  settings for the website, such as how many posts per page would be displayed,
  in a toml file.

**************************************************
Importing from Wordpress to ReST
**************************************************

I wanted to preserve all of my existing content that I had written, despite the
"cringe" that I feel as I read things I wrote almost 15 years ago. To
accomplish this I decided to write an importer that could take a standard
Wordpress XML export and translate it into ReST, annotating each post to be
compatible with this blog.

The importer is rather extensive and can be found `here
<https://github.com/kcuzner/rstblog-content/blob/main/import.py>`_. It performs
3 main operations:

* Loading and decoding the XML, sorting the attachments (images), pages, and
  posts by their metadata.
* Translating "Wordpress HTML" into ReST and organizing the file structure in
  the content repository.
* Copying in attachments by downloading them from the existing website and
  placing them by their corresponding posts.

Most every HTML element supported by Wordpress is translated into something
equivalent in ReST, though I had to give up on a few things such as mixing
inline styles (in particular, bolded links) and so there are a few warts in the
imported pages that I'll have to manually correct eventually.

############################################################
Execution
############################################################

**************************************************
Configuration Management with Docker
**************************************************

Another problem I faced with my 15 year old blog was server management. When I
first started it I hosted it on a machine running out of my parent's basement.
I soon migrated to a VPS on Rackspace (remember those days?) as hardware
failures plagued that old basement server. I remained on Rackspace for a few
years, but constantly had issues with heavy swapping during high load times. I
decided to try AWS and it's been smooth sailing for nearly 10 years now.
Unfortunately, the VPS that I was using on AWS is (as of December 31, 2023)
deprecated and no longer receiving security updates.

I have less time on my hands now than I did 15 years ago with a demanding job,
a family, and a house to maintain. The prospect of recreating and managing the
server (a task I relished back in the day) felt nothing but daunting. I've
become jaded the past few years in regards to server management and have
realized that I *hate* infrastructure management (IT or Sysadmin work). So, I
needed to find a solution where I could "set it and forget it".

The world has come a long way in the past decade in regards to scripted
configuration, with containers remaining a primary underpinning technology.
They allow for each subpart of an application to essentially live in its own
"virtual machine"-like environment and eliminate issues of dependency or other
conflicts that impact interoperability. The ``docker-compose`` tool takes
things a step farther, allowing a multi-container configuration to be described
with connections between the containers.

**************************************************
Static rendering of the content
**************************************************

**************************************************
Nginx as a content server
**************************************************

**************************************************
Plan for hosting multiple web applications
**************************************************

############################################################
Conclusion
############################################################
