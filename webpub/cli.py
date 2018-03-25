#!/usr/bin/env python
import itertools as it
import os
import zipfile as zf

import click


class IntOrTocType(click.ParamType):
    name = 'integer or "toc"'

    def convert(self, value, param, ctx):
        try:
            i = int(value)
        except ValueError:
            if value == 'toc':
                i = 0
            else:
                self.fail("Invalid argument, must be 'toc' or a"
                          " number greater than 0")
        else:
            if i < 1:
                self.fail("Numbers must be greater than 0")
        return i


def make_order(ctx, param, values):
    if len(values) == 0:
        return None
    filled_values = it.chain(
        values[:],
        (i for i in it.count() if i not in values)
    )
    return filled_values


webpub_epilog = """The --spine-order and --toc-order are specified multiple times to
determine the order. For example, '-o 2 -o toc -o 1' first puts the
second document, then the generated Table of Contents, then the first
document. The order defaults to '-o toc -o 1 -o 2 ...'.
"""

templates_path = os.path.join(os.path.dirname(__file__), 'templates')


@click.command(epilog=webpub_epilog)
@click.option('--directory', '-d', 'output_dir', metavar='DIR',
              type=click.Path(dir_okay=True, file_okay=False, writable=True),
              default='_result',
              help="Output directory (defaults to ./_result/)")
@click.option('--template', metavar='TEMPLATE',
              type=click.Path(dir_okay=False, file_okay=True, readable=True),
              default='default_template.html',
              help="The template HTML file in which the content is"
              " inserted for each section (defaults to"
              " {}/default_template.html).".format(templates_path))
@click.option('--spine-order', '-o', metavar='N', type=IntOrTocType(),
              default=None, multiple=True, callback=make_order,
              help="Reorder the chapter order for next/previous"
              " buttons. Input must be a positive number or the"
              " value 'toc' (for 'table of contents').")
@click.option('--toc-order', '-t', metavar='N', type=IntOrTocType(),
              default=None, multiple=True, callback=make_order,
              help="Reorder the order of the entries in the table of"
              " contents. Input is specified in the same way as with"
              " --spine-order. The default value, if unspecified, is"
              " inherited from --spine-order.")
@click.argument('epub_filename', metavar='INFILE',
                type=click.File('rb'))
@click.pass_context
def main(context, output_dir, template, spine_order, toc_order, epub_filename):
    """Process EPUB documents for web publishing.

    Given INFILE as input, this script:

    \b
    1. routes internal links
    2. adds cross-references to suttas
    3. generates a Table of Contents
    """
    import webpub.epub
    if spine_order is None:
        spine_order = it.count()
    if toc_order is None:
        spine_order, toc_order = it.tee(spine_order)
        context.params['spine_order'] = spine_order
        context.params['toc_order'] = toc_order
    with zf.ZipFile(epub_filename) as epub_zip:
        webpub.epub.make_webbook(context, epub_zip)


def linkfix_crossref_common_options(f):
    f = click.option('--dry-run', '-n', default=False, is_flag=True,
                     help="Don't write anything, only show what would"
                     " happen.")(f)
    f = click.option('--directory', '-d', 'output_dir',
                     type=click.Path(file_okay=False, dir_okay=True,
                                     writable=True, exists=True),
                     help="The output directory to save the files.")(f)
    f = click.option('--overwrite/--no-overwrite', '-f/ ', default=False,
                     help="Whether or not to overwrite existing files.")(f)
    f = click.argument('filenames', metavar='INFILE', nargs=-1, required=True,
                       type=click.Path(file_okay=True, dir_okay=False,
                                       readable=True, writable=True,
                                       exists=True))(f)
    return f


@click.command()
@click.option('--fallback-url', '-u', metavar="[URL or PATH]",
              help="Test against this URL if the internal link is not found"
              " locally. If an absolute PATH is given, test against the"
              " local filesystem with this as base directory."
              " If the resource exists (i.e. does not 404 as URL), this link"
              " won't be fixed. Useful if you have a relative link"
              " to a file on a server to which the given files are uploaded.")
@click.option('--basedir', '-b', metavar="PATH", default='',
              help="Base directory that all links share. All given files are"
              " pretended to be in this non-existing subdirectory of the"
              " common root directory that they're in.")
@click.option('--route', '-r', 'custom_routes', type=(str, str), multiple=True,
              metavar="<PATH PATH> ...",
              help="Specifies a custom route. Expects two arguments, and may"
              " be used multiple times.")
@linkfix_crossref_common_options
def linkfix_cmd(fallback_url, basedir, custom_routes, dry_run, output_dir,
                overwrite, filenames):
    """Attempts to fix relative links among the given files.
    """
    import webpub.linkfix
    webpub.linkfix.fixlinks(filenames, fallback_url, dry_run, basedir,
                            custom_routes, output_dir, overwrite)


@click.command()
@linkfix_crossref_common_options
def sutta_cross_ref_cmd(dry_run, output_dir, overwrite, filenames):
    """Creates cross-references to suttas. Leaves existing references
    intact. Only affects HTML files.
    """
    import webpub.sutta_ref
    webpub.sutta_ref.cross_ref(filenames, dry_run, output_dir, overwrite)


if __name__ == '__main__':
    main()
