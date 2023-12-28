#!/usr/bin/env python3

"""
Imports and updates pages and posts from an RSS export file produced by
wordpress
"""

# Theory of operation:
#
# This importer does two basic things with the XML:
# 1. Interpret post and page content into ReST
# 2. Note attachments (images) and download them
#
# For #1, the functionality is centered around the TagHandler class in
# combination with the ordpressToRst HTMLParser. As HTML is parsed, the
# WordpressToRst will request handlers from the TagHandler for each HTML tag
# encoutered, noting nesting and other things like "malformed" closing tags. It
# gathers these handler instances into a "content" list which is used to
# generate the final output ReST for the HTML content.
#
# Simple tags such bold, italics, etc are very straightforwardly processed
# into their ReST equivalents. Non-trivial handling exists for links, iamges
# tables, and code blocks.
#
# Posts/Pages are generally processed into folders matching the original
# wordpress URL structure, creating an "index.rst" for each page or post that
# lives in the path.
#
# For #2, as TagHandlers are created, cross references between elements and
# attachments are noted. Attachments are downloaded into the destination folder
# (living alongside the index.rst) and the URLs in the corresponding TagHandler
# are updated to either be relative URLs or set to a value indicating that the
# attachment couldn't be downloaded (causing the corresponding output ReST
# block to be omitted).
#
# The order of operations generally for each path consists of 3 steps:
# 1. Load the HTML into a new WordpressToRst instance, parsing the HTML into
#    a list of TagHandlers.
# 2. Process any attachments that have appeared, including updating the URLs
#    in corresponding TagHandlers
# 3. Processing the gathered content into restructured text using the to_rst
#    method of each TagHandler.
#
# With that in mind, you'll usually find that attachments must be processed in
# the __init__ of a TagHandler subclass and that the to_rst method takes a
# variety of arguments to handle cases such as nesting tags where additional
# context is needed when the element was initially created. All ReST generation
# is deferred until the to_rst method is called in order to allow updating of
# the parsed content tree.
#
# There are a LOT of little quirks stemming from how wordpress expresses HTML
# within its RSS XML (and generally internally to its database). It's critical
# to manually evaluate the output of this script for correctness and tweak as
# necessary (trying not to break things as you tweak).

from abc import ABC, abstractmethod
import argparse
from collections import deque
from itertools import chain
from html.parser import HTMLParser
import pathlib
import re
import textwrap
import urllib.parse
import urllib.request
import logging

from xml.etree import ElementTree as ET

_log = logging.getLogger(__name__)

XML_NAMESPACES = {
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "wfw": "http://wellformedweb.org/CommentAPI/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "wp": "http://wordpress.org/export/1.2/",
}


class Category:
    def __init__(self, el):
        self.id = el.find("wp:term_id", XML_NAMESPACES).text
        self.nicename = el.find("wp:category_nicename", XML_NAMESPACES).text
        self.parent_id = el.find("wp:category_parent", XML_NAMESPACES).text
        self.name = el.find("wp:cat_name", XML_NAMESPACES).text


class Tag:
    def __init__(self, el):
        self.id = el.find("wp:term_id", XML_NAMESPACES).text
        self.slug = el.find("wp:tag_slug", XML_NAMESPACES).text
        self.name = el.find("wp:tag_name", XML_NAMESPACES).text


class Item(ABC):
    HANDLERS = {}

    @classmethod
    def register_post_type(cls, post_type):
        def wrapper(fn):
            cls.HANDLERS[post_type] = fn
            return fn

        return wrapper

    @classmethod
    def from_xml(cls, el):
        post_type = el.find("wp:post_type", XML_NAMESPACES).text
        return cls.HANDLERS[post_type](el)

    def __init__(self, el):
        self.title = el.find("title").text
        self.link = el.find("link").text
        self.post_type = el.find("wp:post_type", XML_NAMESPACES).text
        self.status = el.find("wp:status", XML_NAMESPACES).text

    @property
    def discard(self):
        return self.status not in ("publish", "inherit")


@Item.register_post_type("attachment")
class Attachment(Item):
    def __init__(self, el):
        super().__init__(el)
        self.guid = el.find("guid").text
        self.attachment_url = el.find("wp:attachment_url", XML_NAMESPACES).text
        self.meta = dict(
            [
                (e.find("wp:meta_key", XML_NAMESPACES).text, e.find("wp:meta_value"))
                for e in el.findall("wp:postmeta", XML_NAMESPACES)
            ]
        )
        self.upload_path = self.meta["_wp_attached_file"]

    @property
    def keys(self):
        _, _, link_path, _, _, _ = urllib.parse.urlparse(self.link)
        _, _, guid_path, _, _, _ = urllib.parse.urlparse(self.guid)
        paths = set((link_path, guid_path))
        return (self.link, self.guid, *paths)

    def download(self, dst_dir):
        _, _, path, _, _, _ = urllib.parse.urlparse(self.guid)
        name = pathlib.Path(path).name
        urllib.request.urlretrieve(self.attachment_url, dst_dir / name)
        return name


class TextBody:
    def __init__(self, text, pos):
        self.text = text
        self.line = pos[0]
        self.offset = pos[1]
        self._attachments = []

    @property
    def attachments(self):
        yield from self._attachments

    def add_attachment(self, attachment):
        self._attachments.append(attachment)

    def to_rst(self, *args, escape=":`*", **kwargs):
        text = self.text
        for c in escape:
            text = text.replace(c, f"\\{c}")
        return text

    def __repr__(self):
        text = self.text[:10]
        if len(self.text) > 10:
            text += ".."
        return f'<{type(self)} "{text}">'


class PostBreak:
    def __init__(self, pos):
        self.line = pos[0]
        self.offset = pos[1]

    @property
    def attachments(self):
        return []

    def to_rst(self, *args, **kwargs):
        return "\n.. rstblog-break::\n"


class TagHandler(ABC):
    HANDLERS = {}

    @classmethod
    def register_tag(cls, tag):
        def wrapper(fn):
            cls.HANDLERS[tag] = fn
            return fn

        return wrapper

    @classmethod
    def from_tag(cls, *args, **kwargs):
        tag = args[0]
        pos = args[2]
        handler = cls.HANDLERS.get(tag, None)
        if handler is None:
            raise ValueError(
                (
                    f"No handle registered for tag {tag} at line "
                    f"{pos[0]} column {pos[1]}"
                )
            )
        return handler(*args, **kwargs)

    def __init__(self, tag, attrs, pos, *args, **kwargs):
        self.tag = tag
        self.attrs = dict(attrs)
        self.line = pos[0]
        self.offset = pos[1]
        self._attachments = []

    @property
    def attachments(self):
        yield from self._attachments
        content = getattr(self, "content", [])
        for c in content:
            yield from c.attachments

    def add_attachment(self, attachment):
        self._attachments.append(attachment)

    @abstractmethod
    def to_rst(self, *args, **kwargs):
        pass

    @property
    def pos_str(self):
        return f"line {self.line} column {self.offset}"


@TagHandler.register_tag("a")
class LinkTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.href = self.attrs.get("href", None)
        self.name = self.attrs.get("name", None)
        self.caption = kwargs.get("caption", {})
        self.content = []

    def append(self, tag):
        self.content.append(tag)

    def to_rst(self, *args, **kwargs):
        if len(self.content) == 0:
            if self.name is None:
                # Silently drop empty link tags
                return ""
            if self.href is not None:
                # Slently drop hyperlinks without text
                return ""
            # Internal hyperlink target without text
            return f".. _{self.name}:\n"
        elif self.name is not None:
            if self.href is not None:
                raise ValueError(
                    f"Ambiguous link tag: Contains both name and href at {self.pos_str}"
                )
            # This is a hyperlink target
            content = "".join([c.to_rst(*args, **kwargs) for c in self.content])
            return f".. _{self.name}:\n" + content
        else:
            if self.href is None:
                # Silently drop links to nowhere
                return ""
            # Strip leading #'s, local page links are easy
            ref = self.href.lstrip("#")
            # We support text or images, nothing else, and content can't be mixed
            types = [ImgTag, TextBody, BoldTag, ItalicsTag]
            text = []
            images = []
            for c in self.content:
                if any(isinstance(c, t) for t in [TextBody, BoldTag, ItalicsTag]):
                    text.append(c)
                elif isinstance(c, ImgTag):
                    images.append(c)
                else:
                    raise ValueError(f"Content {c} is not supported in a link")
            if len(images):
                if len(text):
                    raise ValueError("Mixed images and text in links are not supporteD")
                if len(images) > 1:
                    raise ValueError("Multiple images cannot be in a link")
                return images[0].to_rst(
                    *args, target=ref, parent_caption=self.caption, **kwargs
                )
            content = "".join([c.to_rst(*args, **kwargs) for c in text]).strip()
            if not content:
                # Links without content are silently dropped
                return f""
            return f"`{content} <{ref}>`__"


@TagHandler.register_tag("img")
class ImgTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.src = self.attrs.get("src")
        self.caption = kwargs.get("caption", {})
        self.add_attachment(self)

    def _from_bb_caption(self, attr, parent_caption):
        if (v := self.caption.get(attr, None)) is not None:
            return v
        if (v := parent_caption.get(attr, None)) is not None:
            return v
        if (v := self.attrs.get(attr, None)) is not None:
            # While strictly this isn't from the bbcode caption, some
            # attributes appear in either the bbcode or in the contained
            # elements attribute.
            return v
        return None

    @property
    def src(self):
        return self._src

    @src.setter
    def src(self, value):
        if value is not None:
            _, _, path, _, _, _ = urllib.parse.urlparse(value)
            self._src = path
        else:
            self._src = None

    def to_rst(self, *args, target=None, parent_caption={}, **kwargs):
        if self.src is None:
            # Silently drop empty images that couldn't be downloaded
            return ""
        caption = self._from_bb_caption("caption", parent_caption)
        width = self._from_bb_caption("width", parent_caption)
        align_raw = self._from_bb_caption("align", parent_caption) or ""
        align = next((a for a in ["left", "center", "right"] if a in align_raw), None)
        directive = "figure" if caption else "image"
        lines = [f".. {directive}:: {self.src}"]
        if target:
            lines.append(f"   :target: {target}")
        if width:
            lines.append(f"   :width: {width}")
        if align:
            lines.append(f"   :align: {align}")
        if caption:
            lines.extend(["", f"   {caption}"])
        return "\n".join(lines) + "\n\n"


@TagHandler.register_tag("h1")
@TagHandler.register_tag("h2")
@TagHandler.register_tag("h3")
class HeaderTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = []
        self.id = self.attrs.get("id", None)

    def append(self, tag):
        self.content.append(tag)

    def to_rst(self, *args, **kwargs):
        link = f".. _{self.id}:\n\n" if self.id else ""
        content = "".join([c.to_rst(*args, **kwargs) for c in self.content]).strip()
        if content.count("\n") > 1:
            raise ValueError(
                f"Multiple newlines in a header is not supported at {self.pos_str}"
            )
        char = "=" if self.tag == "h1" else "-" if self.tag == "h2" else "~"
        line = char * len(content)
        return f"\n{link}{content}\n{line}\n\n"


@TagHandler.register_tag("em")
@TagHandler.register_tag("i")
class ItalicsTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = []

    def append(self, tag):
        self.content.append(tag)

    def to_rst(self, *args, **kwargs):
        content = "".join([c.to_rst(*args, **kwargs) for c in self.content])
        return f"*{content}*"


@TagHandler.register_tag("strong")
@TagHandler.register_tag("b")
class BoldTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = []

    def append(self, tag):
        self.content.append(tag)

    def to_rst(self, *args, **kwargs):
        # NOTE: ReST requires there to be no trailing whitespace. Just in case,
        # we insert one space after these. Shouldn't result in too many
        # problems, I rarely use this in a word.
        content = "".join([c.to_rst(*args, **kwargs) for c in self.content]).strip()
        return f"**{content}** "


@TagHandler.register_tag("li")
class ListItemTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = []

    def append(self, tag):
        self.content.append(tag)

    def to_rst(self, *args, **kwargs):
        return "".join([c.to_rst(*args, **kwargs) for c in self.content])


class ListTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = []

    def append(self, tag):
        if not isinstance(tag, ListItemTag):
            # Silently drop anything that's not a list item
            return
        self.content.append(tag)

    @abstractmethod
    def prefix(self, i):
        pass

    def to_rst(self, *args, **kwargs):
        def process(i, rst):
            lines = rst.split("\n")
            prefix = self.prefix(i)
            lines[0] = prefix + lines[0]
            rest = textwrap.indent("\n".join(lines[1:]), " " * len(prefix))
            return lines[0] + "\n" + rest

        items = [
            process(i, c.to_rst(*args, **kwargs)) for i, c in enumerate(self.content)
        ]
        # Items are separated by a blank space and the list is terminated by a blank space
        return "\n\n" + "\n\n".join(items) + "\n\n"


@TagHandler.register_tag("ol")
class OrderedListTag(ListTag):
    def prefix(self, i):
        return f"#. "


@TagHandler.register_tag("ul")
class UnorderedLastTag(ListTag):
    def prefix(self, i):
        return f"* "


@TagHandler.register_tag("sub")
class SubscriptTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = []

    def append(self, tag):
        self.content.append(tag)

    def to_rst(self, *args, **kwargs):
        content = "".join([c.to_rst(*args, **kwargs) for c in self.content])
        return rf"\ :sub:`{content}`\ "


@TagHandler.register_tag("blockquote")
class BlockquoteTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = []

    def append(self, tag):
        self.content.append(tag)

    def to_rst(self, *args, **kwargs):
        content = "".join([c.to_rst(*args, **kwargs) for c in self.content])
        return textwrap.indent(content, " " * 4)


@TagHandler.register_tag("span")
class SpanTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO support attributes
        self.content = []

    def append(self, tag):
        self.content.append(tag)

    def to_rst(self, *args, **kwargs):
        # Just a passthrough
        return "".join([c.to_rst(*args, **kwargs) for c in self.content])


@TagHandler.register_tag("div")
@TagHandler.register_tag("p")
class ParagraphTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO support attributes
        self.content = []

    def append(self, tag):
        self.content.append(tag)

    def to_rst(self, *args, **kwargs):
        # The end of a paragraph is marked by two newlines. Passthrough content otherwise.
        return "".join([c.to_rst(*args, **kwargs) for c in self.content]) + "\n\n"


@TagHandler.register_tag("code")
@TagHandler.register_tag("pre")
class CodeTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = []

    def append(self, tag):
        self.content.append(tag)

    def to_rst(self, *args, **kwargs):
        kwargs["escape"] = ""  # All chars allowed without escaping
        cls = self.attrs.get("class", "")
        lang_match = re.search(r"(?:^|\s)lang:(\S+)(?:$|\s)", cls)
        lang = lang_match.group(1) if lang_match else ""
        if not lang:
            _log.warning(f'Can\'t find code-block language in "{cls}"')
        if lang in ("default",):
            lang = ""
        decl = f".. code-block:: {lang}\n\n" if lang else "::\n\n"
        return (
            f"\n{decl}\n\n"
            + textwrap.indent(
                "".join([c.to_rst(*args, **kwargs) for c in self.content]), " " * 3
            )
            + "\n"
        )


@TagHandler.register_tag("tt")
class InlineLiteralTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = []

    def append(self, tag):
        self.content.append(tag)

    def to_rst(self, *args, **kwargs):
        kwargs[
            "escape"
        ] = "`"  # Most chars are allowed, but backticks still need escaping
        return "``" + "".join([c.to_rst(*args, **kwargs) for c in self.content]) + "``"


@TagHandler.register_tag("del")
class StrikethroughTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = []

    def append(self, tag):
        self.content.append(tag)

    def to_rst(self, *args, **kwargs):
        return (
            r"\ :raw-html:`<del>`\ "
            + "".join([c.to_rst(*args, **kwargs) for c in self.content])
            + r"\ :raw-html:`</del>`\ "
        )


@TagHandler.register_tag("td")
@TagHandler.register_tag("th")
class ColumnTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = []

    @property
    def is_header(self):
        return self.tag == "th"

    def append(self, tag):
        self.content.append(tag)

    @property
    def _content(self):
        return "\n\n".join([c.to_rst() for c in self.content])

    def cell(self, leader):
        lines = self._content.splitlines()
        lines[0] = leader + lines[0]
        rest = textwrap.indent("\n".join(lines[1:]), " " * len(leader))
        return lines[0] + "\n" + rest

    def to_rst(self, *args, **kwargs):
        raise NotImplementedError(
            f"Table columns cannot be directly rendered at {self.pos_str}"
        )

    def __repr__(self):
        return f'<Column: "{self._content}">'


@TagHandler.register_tag("tr")
class RowTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.columns = []
        self.is_header = False

    def append(self, tag):
        if isinstance(tag, ColumnTag):
            self.columns.append(tag)
            if tag.is_header:
                self.is_header = True
        # All other silently dropped

    def column(self, index):
        return (
            self.columns[index]
            if index < len(self.columns)
            else ColumnTag("td", {}, (self.line, self.offset))
        )

    @property
    def rows(self):
        return [self]

    def render(self, column_count):
        # NOTE: This doesn't support colspans or rowspans
        def leader(index):
            return "   * - " if index == 0 else "     - "

        cells = [c.cell(leader(i)) for i, c in enumerate(self.columns)]
        return "\n".join(cells)

    def to_rst(self, *args, **kwargs):
        raise NotImplementedError(
            f"Table rows cannot be directly rendered at {self.pos_str}"
        )

    def __repr__(self):
        name = "Row (header)" if self.is_header else "Row"
        return f"<{name}: {self.columns}>"


@TagHandler.register_tag("thead")
@TagHandler.register_tag("tbody")
@TagHandler.register_tag("tfoot")
class RowGroupTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = []

    def append(self, tag):
        if not isinstance(tag, RowTag):
            # Silently drop non-rows
            return
        if self.tag == "thead":
            tag.is_header = True
        self.rows.append(tag)

    def to_rst(self, *args, **kwargs):
        raise NotImplementedError(
            f"Table row groups cannot be directly rendered at {self.pos_str}"
        )

    def __repr__(self):
        return f"<RowGroup: {self.rows}>"


@TagHandler.register_tag("table")
class TableTag(TagHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = []

    def append(self, tag):
        if isinstance(tag, RowTag):
            self.rows.append(tag)
        elif isinstance(tag, RowGroupTag):
            self.rows.extend(tag.rows)
        if not isinstance(tag, RowTag) and not isinstance(tag, RowGroupTag):
            # Silently drop anything that's not a row
            return

    def to_rst(self, *args, **kwargs):
        # This generates tables in the "list-table" style. Originally I had
        # implemented this to use "grid tables", but this was extremely
        # complicated and required all manner of manual tweaking. List tables
        # are much more ergnomic to parse/tweak and look (mostly) just as good.
        all_rows = list(chain.from_iterable([r.rows for r in self.rows]))
        if not len(all_rows):
            return ""
        # Determine how many columns this table has so we can ensure we declare
        # slots for all of them in the list.
        column_count = max([len(r.columns) for r in all_rows])
        if not column_count:
            return ""
        # Separate all header rows from data rows. I just stuff them at the top.
        headers = [r.render(column_count) for r in all_rows if r.is_header]
        data = [r.render(column_count) for r in all_rows if not r.is_header]
        decl = "\n".join(
            (
                ".. list-table",
                "   :widths: auto",
                f"   :header-rows: {len(headers)}",
                "",
            )
        )
        return decl + "\n".join(headers) + "\n".join(data)


@TagHandler.register_tag("object")
@TagHandler.register_tag("param")
@TagHandler.register_tag("embed")
@TagHandler.register_tag("iframe")
class DropMeTag(TagHandler):
    """
    These HTML tags appear in my blog when I embedded a youtube video over a
    decade ago. I'm just going to drop them, they're referencing flash required
    flash or something else.

    Eventually I might implement these.
    """

    def append(self, tag):
        pass

    def to_rst(self, *args, **kwargs):
        return ""


class WordpressToRst(HTMLParser):
    def __init__(self):
        super().__init__()
        self._last_data = ""
        self.stack = deque()
        self.content = []

    def _tag_kwargs(self, tag, attrs):
        kwargs = {}
        if m := re.search(r"\[caption\s([^\]]+)\]\s*$", self._last_data):
            kwargs["caption"] = dict(
                [
                    (kv.group(1), kv.group(2))
                    for kv in re.finditer(r'(\w+)="([^"]+)"', m.group(1))
                ]
            )
        return kwargs

    def handle_starttag(self, tag, attrs):
        kwargs = self._tag_kwargs(tag, attrs)
        self.stack.append(TagHandler.from_tag(tag, attrs, self.getpos(), **kwargs))

    def handle_startendtag(self, tag, attrs):
        kwargs = self._tag_kwargs(tag, attrs)
        if len(self.stack):
            self.stack[-1].append(
                TagHandler.from_tag(tag, attrs, self.getpos(), **kwargs)
            )
        else:
            self.content.append(
                TagHandler.from_tag(tag, attrs, self.getpos(), **kwargs)
            )

    def handle_endtag(self, tag):
        while True:
            # Consume our stack until we encouter this tag. HTML allows tags to
            # never be closed, so we resolve that by inferring a close as we
            # search for this tag in the stack
            completed = self.stack.pop()
            if len(self.stack):
                self.stack[-1].append(completed)
            else:
                self.content.append(completed)
            if completed.tag == tag:
                break
            elif not len(self.stack):
                raise ValueError(f"Unable to locate tag {tag} in the stack")

    def handle_data(self, data):
        self._last_data = data
        for m in re.finditer(r"\[(/?)(\w+)[^\]]*\]", data):
            # Remove all bbcode-style things
            if m.group(2) == "caption":
                if m.group(1) == "/":
                    # Some captions are between any inner elements and the end
                    # tag. However, at this point we've already processed things and I
                    # can only find one instance of this happening, so we just throw everything
                    # away up until and including the closing tag.
                    pos = data.find(m.group(0))
                    data = data[pos:]
                data = data.replace(m.group(0), "")
        if len(self.stack):
            self.stack[-1].append(TextBody(data, self.getpos()))
        else:
            self.content.append(TextBody(data, self.getpos()))

    def handle_comment(self, data):
        if data == "more":
            self.content.append(PostBreak(self.getpos()))

    @property
    def attachments(self):
        for c in self.content:
            yield from c.attachments

    def close(self):
        super().close()
        if len(self.stack):
            raise ValueError("Unclosed tags remain at the end of HTML")
        return "".join([t.to_rst() for t in self.content])


class Content(Item):
    def __init__(self, el):
        super().__init__(el)
        self.content_raw = el.find("content:encoded", XML_NAMESPACES).text

    @property
    @abstractmethod
    def repo_path(self):
        pass

    @property
    @abstractmethod
    def rst_url(self):
        pass

    @property
    def rst_date(self):
        return self.date.strftime("%Y/%m/%d")

    @property
    def rstblog_directive(self):
        return "\n".join(
            [
                f".. rstblog-settings::",
                f"   :title: {self.title}",
                f"   :date: {self.rst_date}",
                f"   :url: /{self.rst_url}",
            ]
        )

    def process(self, attachments):
        # small worry here about path traversal...but whatever, this script
        # isn't ran automatically
        base_dir = pathlib.Path.cwd()
        output_dir = base_dir / pathlib.Path(self.repo_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        index_path = output_dir / "index.rst"
        # Process the HTML content into RST
        content = WordpressToRst()
        content.feed(self.content_raw)
        attachments.process(content.attachments, output_dir)
        rst = content.close()
        with open(index_path, "w") as f:
            f.write(rst)
            f.write("\n\n")
            f.write(self.rstblog_directive)


@Item.register_post_type("post")
class Post(Content):
    def __init__(self, el):
        super().__init__(el)
        from dateutil import parser

        self.content = el.find("content:encoded", XML_NAMESPACES).text
        self.date = parser.parse(el.find("wp:post_date", XML_NAMESPACES).text)
        self.name = el.find("wp:post_name", XML_NAMESPACES).text
        self.title = el.find("title", XML_NAMESPACES).text

    @Content.rst_url.getter
    def rst_url(self):
        return f"{self.rst_date}/{self.name}"

    @Content.repo_path.getter
    def repo_path(self):
        return f"posts/{self.rst_url}"


@Item.register_post_type("page")
class Page(Content):
    def __init__(self, el):
        super().__init__(el)
        from dateutil import parser

        self.content = el.find("content:encoded", XML_NAMESPACES).text
        self.date = parser.parse(el.find("wp:post_date", XML_NAMESPACES).text)
        self.name = el.find("wp:post_name", XML_NAMESPACES).text
        self.title = el.find("title", XML_NAMESPACES).text

    @Content.rst_url.getter
    def rst_url(self):
        return f"{self.name}"

    @Content.repo_path.getter
    def repo_path(self):
        return f"pages/{self.name}"


class AttachmentRegistry:
    def __init__(self, items):
        attachments = (i for i in items if isinstance(i, Attachment))
        self.registry = dict(((k, a) for a in attachments for k in a.keys))
        _log.debug("Logging registry:")
        for k in self.registry:
            _log.debug(k)
        _log.debug("Registery logged.")

    def process(self, attachments, output_dir):
        for a in attachments:
            if attachment := self.find(a.src):
                name = attachment.download(output_dir)
                _log.debug(
                    f"Downloaded attachment {attachment.guid} to {output_dir / name}"
                )
                a.src = name
            else:
                _log.debug(f"Clearing src for {a.src}, attachment not found")
                a.src = None

    def find(self, link):
        # First attempt to find the attachment by the link naturally
        if r := self.registry.get(link, None):
            return r
        # The link may be a resized version. Strip off any resizing information
        # from the end.
        _, _, path, _, _, _ = urllib.parse.urlparse(link)
        if (m := re.search(r"/\w+(-\d+x\d+)\.\w+$", path)) and (
            r := self.registry.get(link.replace(m.group(1), ""), None)
        ):
            return r
        _log.warning(f'Unable to find attachment for "{link}"')
        return None


def load_rss(file):
    tree = ET.parse(file)
    root = tree.getroot()
    channel = root.find("channel")
    categories = [Category(el) for el in channel.findall("wp:category", XML_NAMESPACES)]
    items = [Item.from_xml(el) for el in channel.findall("item")]
    items = [i for i in items if not i.discard]
    attachments = AttachmentRegistry(items)
    for i in (i for i in items if isinstance(i, Content)):
        _log.info(f"Processing {i.name}")
        i.process(attachments)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("rss", help="Path to RSS XML file")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig()
    logging.getLogger().setLevel(level)

    load_rss(args.rss)


if __name__ == "__main__":
    main()
