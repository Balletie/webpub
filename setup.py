from setuptools import setup, find_packages
import os

PACKAGE_NAME = "webpub"

setup(
    name=PACKAGE_NAME,
    version="0.1",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': ['webpub = webpub.cli:main'],
    },
    install_requires=[
        'lxml',
        'inxs',
        'cssutils',
        'dependency-injection',
        'python-mimeparse',
    ],
)
