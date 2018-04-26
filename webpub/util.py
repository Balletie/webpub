import os
import shutil
import itertools as it
import functools as ft
from urllib.parse import urlparse

from lxml import html
from inxs import Any, MatchesAttributes

import webpub


def tostring(input):
    return html.tostring(
        input,
        doctype='<!DOCTYPE html>',
        encoding='unicode',
    ).encode()


tostring.verbose_name = "Convert back to string"
tostring.verbosity = 1


def guard_dry_run(input, routes, filepath, dry_run):
    if dry_run:
        dst = routes[filepath]
        dst = os.path.relpath(dst)
        raise webpub.handlers.AbortHandling(
            "Would write {}".format(dst), verbosity=1
        )

    return input


guard_dry_run.verbose_name = "Check if it's a dry-run"
guard_dry_run.verbosity = 2


def guard_overwrite(input, filepath, routes, overwrite):
    dst = routes[filepath]
    if os.path.exists(dst):
        dst = os.path.relpath(dst)
        if not overwrite:
            raise webpub.handlers.AbortHandling(
                "Not writing because it would overwrite {}".format(dst)
            )
        webpub.ui.echo("File {} overwritten".format(dst), verbosity=2)

    return input


guard_overwrite.verbose_name = "Check if file would be overwritten"
guard_overwrite.verbosity = 2


def copy_out(epub_zip, filepath, root_dir, routes):
    src_zip_path = os.path.join(root_dir, filepath)
    routed_path = routes[filepath]
    os.makedirs(os.path.dirname(routed_path), exist_ok=True)

    with epub_zip.open(src_zip_path, 'r') as src:
        with open(routed_path, 'wb') as dst:
            shutil.copyfileobj(src, dst, 8192)


copy_out.verbose_name = "Copy file"
copy_out.verbosity = 1


def write_out(input, filepath, routes):
    routed_path = routes[filepath]
    os.makedirs(os.path.dirname(routed_path), exist_ok=True)

    with open(routed_path, 'wb') as dst:
        dst.write(input)


write_out.verbose_name = "Write result to file"
write_out.verbosity = 1


def reorder(entries, order):
    entries_order = list(it.islice(order, len(entries)))
    for i in entries_order:
        if i >= len(entries):
            raise ValueError(
                "The value '{}' is out of bounds,"
                " only values from 1 up to {}"
                " can be used.".format(i, len(entries) - 1)
            )
    return [entries[i] for i in entries_order]


def ensure(result, error_message):
    if not result:
        raise Exception(error_message)

    return result[0]


has_link = Any(MatchesAttributes({'href': None}),
               MatchesAttributes({'src': None}),)


def matched_url(element):
    url = None
    for attrib in ['href', 'src']:
        url = element.attrib.get(attrib)
        if url:
            return attrib, url
    else:
        raise ValueError("No URL attribute found on element")


def _ensure_url(f):
    @ft.wraps(f)
    def wrapped(url_str):
        if isinstance(url_str, str):
            return f(urlparse(url_str))
        return f(url_str)
    return wrapped


@_ensure_url
def is_path(url):
    return not url.netloc and not url.scheme and url.path


@_ensure_url
def is_relative(url):
    return is_path(url) and not os.path.isabs(url.path)


@_ensure_url
def is_absolute(url):
    return is_path(url) and os.path.isabs(url.path)


def has_path_url(element, transformation):
    try:
        attrib, url = matched_url(element)
        return is_path(url)
    except ValueError:
        return False


def has_relative_url(element, transformation):
    try:
        attrib, url = matched_url(element)
        return is_relative(url)
    except ValueError:
        return False


def has_absolute_url(element, transformation):
    try:
        attrib, url = matched_url(element)
        return is_absolute(url)
    except ValueError:
        return False
