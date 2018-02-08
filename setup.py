from setuptools import setup, find_packages
import os

PACKAGE_NAME = "webpub"

setup(
    name=PACKAGE_NAME,
    version="0.1",
    scripts=["webpub.py"],
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'inxs',
        'cssutils',
        'mimeparse',
        'dependency-injection',
        'python-mimeparse',
    ],
)
