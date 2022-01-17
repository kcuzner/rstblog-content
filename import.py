#!/usr/bin/env python3

"""
Imports and updates pages and posts from an RSS export file produced by
wordpress
"""

import argparse

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rss", help="Path to RSS XML file")

    args = parser.parse_args()

if __name__ == "__main__":
    main()
