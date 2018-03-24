import os
import shutil
import itertools as it

from lxml import html

import webpub


def tostring(input):
    return html.tostring(
        input,
        doctype='<!DOCTYPE html>',
        encoding='unicode',
        pretty_print=True,
    ).encode()


def guard_dry_run(input, dry_run):
    if dry_run:
        raise webpub.handlers.AbortHandling("Dry run, aborting.")

    return input


def guard_overwrite(input, filepath, overwrite):
    if not overwrite and os.path.exists(filepath):
        raise webpub.handlers.AbortHandling("Overwriting disabled.")

    return input


def copy_out(epub_zip, filepath, output_dir, root_dir, routes):
    src_zip_path = os.path.join(root_dir, filepath)
    routed_path = os.path.join(output_dir, routes[filepath])
    os.makedirs(os.path.dirname(routed_path), exist_ok=True)

    with epub_zip.open(src_zip_path, 'r') as src:
        with open(routed_path, 'wb') as dst:
            shutil.copyfileobj(src, dst, 8192)


def write_out(input, filepath, output_dir, routes):
    routed_path = os.path.join(output_dir, routes[filepath])
    os.makedirs(os.path.dirname(routed_path), exist_ok=True)

    with open(routed_path, 'wb') as dst:
        dst.write(input)


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
