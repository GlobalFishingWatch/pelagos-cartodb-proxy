#! /usr/bin/python

from setuptools.command import easy_install
from setuptools import setup, find_packages
import shutil
import os.path
import sys
import hashlib

setup(
    name = "appomatic_pelagos_cartodb_proxy",
    description = "A CartoDB proxy presenting CartoDB maps as pelagos tilesets",
    keywords = "cartodb pelagos",
    install_requires = ["Django==1.7", "appomatic", "fcdjangoutils", "python-dateutil", "slugify", "python-geohash"],
    version = "0.0.1",
    author = "Egil Moeller",
    author_email = "egil@skytruth.org",
    license = "Apache 2.0",
    url = "https://github.com/GlobalFishingWatch/pelagos-cartodb-proxy",
    packages = find_packages()
)
