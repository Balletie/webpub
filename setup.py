from setuptools import setup, find_packages
import os
import webpub

PACKAGE_NAME = "webpub"

setup(
    name=PACKAGE_NAME,
    version=webpub.__version__,
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'webpub = webpub.cli:main',
            'webpub-linkfix = webpub.cli:linkfix_cmd',
            'webpub-suttaref = webpub.cli:sutta_cross_ref_cmd',
        ],
    },
    install_requires=[
        'lxml',
        'html5-parser',
        'inxs',
        'click',
        'jinja2',
        'css-parser',
        'dependency-injection',
        'python-mimeparse',
        'requests',
    ],
)
