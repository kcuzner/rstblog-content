#!/usr/bin/env python3

"""
Imports and updates pages and posts from an RSS export file produced by
wordpress
"""

import argparse

from xml.etree import ElementTree as ET

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


class Item:
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
        return self.status != "publish"


@Item.register_post_type("attachment")
class Attachment(Item):
    def __init__(self, el):
        super().__init__(el)
        self.attachment_url = el.find("wp:attachment_url", XML_NAMESPACES).text
        self.meta = dict(
            [
                (e.find("wp:meta_key", XML_NAMESPACES).text, e.find("wp:meta_value"))
                for e in el.findall("wp:postmeta", XML_NAMESPACES)
            ]
        )
        self.upload_path = self.meta["_wp_attached_file"]


class Content(Item):
    def __init__(self, el):
        super().__init__(el)

    @property
    def repo_path(self):
        raise NotImplementedError

    def process(self, attachments):
        print(self.repo_path)


@Item.register_post_type("post")
class Post(Content):
    def __init__(self, el):
        super().__init__(el)
        from dateutil import parser

        self.content = el.find("content:encoded", XML_NAMESPACES).text
        self.date = parser.parse(el.find("wp:post_date", XML_NAMESPACES).text)
        self.name = el.find("wp:post_name", XML_NAMESPACES).text

    @Content.repo_path.getter
    def repo_path(self):
        date = self.date.strftime("%Y/%m/%d")
        # WIP here:
        return f"posts/{date}/{self.name}"


@Item.register_post_type("page")
class Page(Content):
    def __init__(self, el):
        super().__init__(el)
        from dateutil import parser

        self.content = el.find("content:encoded", XML_NAMESPACES).text
        self.date = parser.parse(el.find("wp:post_date", XML_NAMESPACES).text)
        self.name = el.find("wp:post_name", XML_NAMESPACES).text

    @Content.repo_path.getter
    def repo_path(self):
        return f"pages/{self.name}"

class AttachmentRegistry:
    def __init__(self, items):
        self.registry = dict(((i.link, i) for i in items if isinstance(i, Attachment)))

    def find(self, link):
        return self.registry.get(link, None)


def load_rss(file):
    tree = ET.parse(file)
    root = tree.getroot()
    channel = root.find("channel")
    categories = [Category(el) for el in channel.findall("wp:category", XML_NAMESPACES)]
    items = [Item.from_xml(el) for el in channel.findall("item")]
    items = [i for i in items if not i.discard]
    attachments = AttachmentRegistry(items)
    for i in (i for i in items if isinstance(i, Content)):
        i.process(attachments)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rss", help="Path to RSS XML file")

    args = parser.parse_args()

    load_rss(args.rss)


if __name__ == "__main__":
    main()
