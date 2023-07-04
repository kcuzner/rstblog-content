#!/usr/bin/env python3

"""
Imports and updates pages and posts from an RSS export file produced by
wordpress
"""

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

    def __init__(self, tag, attrs, pos):
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
                image = images[0].to_rst(*args, **kwargs).strip()
                return f"\n{image}\n   :target: {ref}\n\n"
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
        self.add_attachment(self)

    @property
    def src(self):
        return self._src

    @src.setter
    def src(self, value):
        _, _, path, _, _, _ = urllib.parse.urlparse(value)
        self._last_src = path
        self._src = path

    def to_rst(self, *args, **kwargs):
        if self.src is None:
            # Silently drop empty images
            return ""
        return f".. image:: {self.src}\n\n"


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
        content = "".join([c.to_rst(*args, **kwargs) for c in self.content])
        return f"**{content}**"


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
            rest = textwrap.indent("\n".join(lines[1:]), " " * len(prefix)).strip()
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
        return r"\ :sub:`{content}`\ "


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
        decl = ".. code-block:: {lang}\n\n" if lang else "::\n\n"
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

    def __len__(self):
        return len(self._content)

    @property
    def min_width(self):
        # The minimum width of a column is the length of the longest word, plus
        # 3 for the column separator and terminating spaces.
        words = self._content.split()
        return max([len(w) + 3 for w in words]) if len(words) else 0

    def wrapped(self, width):
        content = "\n\n".join([c.to_rst() for c in self.content])
        return "\n\n".join(
            ["\n".join(textwrap.wrap(p, width=width)) for p in content.split("\n\n")]
        )

    def cell(self, width):
        wrapped = self.wrapped(width - 3)
        return "\n".join(["| " + l.ljust(width - 2) for l in wrapped.splitlines()])

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

    def render(self, widths):
        cells = [c.cell(w).splitlines() for c, w in zip(self.columns, widths)]
        height = max([len(c) for c in cells])
        for c, w in zip(cells, widths):
            c.extend(["| " + " " * (w - 2) for _ in range(height - len(c))])
        return "\n".join(["".join(t) + "|" for t in zip(*cells)]) + "\n"

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
        all_rows = list(chain.from_iterable([r.rows for r in self.rows]))
        if not len(all_rows):
            return ""
        column_count = max([len(r.columns) for r in all_rows])
        if not column_count:
            return ""
        # first entry is width, 2nd is min width
        # NOTE: Rows return an empty cell if a column is requested that isn't
        # present on the row
        column_widths = [
            (
                max([len(r.column(i)) for r in all_rows]),
                max([r.column(i).min_width for r in all_rows]),
            )
            for i in range(column_count)
        ]
        # Nominally, we'll allow a width of 20 (arbitrary) per column to compute the full
        # table width, capping the width to 120 (arbitrary) characters. The columns will
        # then be scaled according to their relative proportions, though they will not be made
        # smaller than the column's minimum width.
        total_width = sum([w for w, _ in column_widths])
        width_fractions = [w / total_width for w, _ in column_widths]
        width = w if (w := 20 * column_count) < 120 else 120
        widths = [
            max(min_width, int(w * f))
            for f, (w, min_width) in zip(width_fractions, column_widths)
        ]
        separator_hdr = "".join(["+" + "=" * (w - 1) for w in widths]) + "+" + "\n"
        separator = "".join(["+" + "-" * (w - 1) for w in widths]) + "+" + "\n"
        return (
            separator
            + separator.join([r.render(widths) for r in all_rows if r.is_header])
            + separator_hdr
            + separator.join([r.render(widths) for r in all_rows if not r.is_header])
            + separator
        )


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
        self.stack = deque()
        self.content = []

    def handle_starttag(self, tag, attrs):
        self.stack.append(TagHandler.from_tag(tag, attrs, self.getpos()))

    def handle_startendtag(self, tag, attrs):
        if len(self.stack):
            self.stack[-1].append(TagHandler.from_tag(tag, attrs, self.getpos()))
        else:
            self.content.append(TagHandler.from_tag(tag, attrs, self.getpos()))

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
