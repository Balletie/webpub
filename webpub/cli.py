#!/usr/bin/env python
import re
import itertools as it
import functools as ft
import os
import zipfile as zf

import click

from webpub.ui import UserInterfaceContext
import webpub.linkfix.check
import webpub.sutta_ref


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


class RichHelpOption(click.Option):
    rst_regex = r"(?:" \
                r"\*\*(.+?)\*\*|" \
                r"\*(.+?)\*|" \
                r"\`\`(.+?)\`\`|" \
                r"(?:\:.+?\:)?\`(.+?)\`(?:\:.+?\:)?(?:__)?|" \
                r"(\w+?)_)"

    def __init__(self, *args, **kwargs):
        self.rich_help = kwargs.pop('rich_help', None)
        _help = kwargs.get('help')

        if not self.rich_help:
            self.rich_help = _help or ''
        else:
            kwargs['help'] = self._strip_rst(self.rich_help)

        super().__init__(*args, **kwargs)

    def _strip_rst(self, _help):
        return re.sub(
            self.rst_regex,
            lambda m: ''.join(m.groups('')),
            _help,
            re.DOTALL | re.MULTILINE
        )


def rich_help_option(*args, **kwargs):
    return click.option(*args, cls=RichHelpOption, **kwargs)


def make_order(ctx, param, values):
    if len(values) == 0:
        return None
    filled_values = it.chain(
        values[:],
        (i for i in it.count() if i not in values)
    )
    return filled_values


def ensure_ui_context(f):
    @ft.wraps(f)
    def wrapper(*args, **kwargs):
        ctx = click.get_current_context()
        ctx.ensure_object(UserInterfaceContext)
        return f(*args, **kwargs)
    return wrapper


def set_verbosity(ctx, param, value):
    ui_ctx = ctx.ensure_object(UserInterfaceContext)
    setattr(ui_ctx, 'verbosity', value)


def dry_run_msg(ctx, param, value):
    if value:
        print("Dry run; no files will be written.")
        ctx.call_on_close(lambda: print("Dry run; no files were written."))
    return value


webpub_epilog = """The --spine-order and --toc-order are specified multiple times to
determine the order. For example, '-o 2 -o toc -o 1' first puts the
second document, then the generated Table of Contents, then the first
document. The order defaults to '-o toc -o 1 -o 2 ...'.
"""

templates_path = os.path.join(os.path.dirname(__file__), 'templates')


def common_options(f):
    f = rich_help_option('--fallback-url', '-u', metavar="[URL or PATH]",
                         rich_help="Test against this URL if the internal link"
                         " is not found locally. If an absolute PATH is given,"
                         " test against the local filesystem with this as base"
                         " directory. If the resource exists (i.e. does not"
                         " ``404`` as URL), this link won't be fixed. Useful"
                         " if you have a relative link to a file on a server"
                         " to which the given files are uploaded.")(f)
    f = rich_help_option('--verbose', '-v', count=True, expose_value=False,
                         callback=set_verbosity,
                         rich_help="Enable verbose output. Use this multiple"
                         " times to set different verbosity levels (e.g."
                         " ``-vvv``).")(f)
    f = rich_help_option('--dry-run', '-n', default=False, is_flag=True,
                         callback=dry_run_msg,
                         help="Don't write anything, only show what would"
                         " happen.")(f)
    f = rich_help_option('--overwrite/--no-overwrite', '-f/ ', default=False,
                         help="Whether or not to overwrite existing files.")(f)
    f = ensure_ui_context(f)
    return f


@click.command(epilog=webpub_epilog)
@rich_help_option('--directory', '-d', 'output_dir', metavar='DIR',
                  type=click.Path(
                      dir_okay=True, file_okay=False, writable=True
                  ),
                  default='_result',
                  rich_help="Output directory (defaults to ``./_result/``)")
@rich_help_option('--template', metavar='TEMPLATE',
                  type=click.Path(
                      dir_okay=False, file_okay=True, readable=True
                  ),
                  default='default_template.html',
                  rich_help="The template HTML file in which the content is"
                  " inserted for each section (defaults to"
                  " ``{}/default_template.html``).".format(templates_path))
@rich_help_option('--spine-order', '-o', metavar='N', type=IntOrTocType(),
                  default=None, multiple=True, callback=make_order,
                  rich_help="Reorder the chapter order for next/previous"
                  " buttons. Input must be a positive number or the"
                  " value ``toc`` (for 'table of contents').")
@rich_help_option('--toc-order', '-t', metavar='N', type=IntOrTocType(),
                  default=None, multiple=True, callback=make_order,
                  rich_help="Reorder the order of the entries in the table of"
                  " contents. Input is specified in the same way as with"
                  " :option:`--spine-order`. The default value, if"
                  " unspecified, is inherited from :option:`--spine-order`.")
@common_options
@click.argument('epub_filename', metavar='INFILE',
                type=click.File('rb'))
@click.pass_context
def main(context, output_dir, template, spine_order, toc_order, fallback_url,
         dry_run, overwrite, epub_filename):
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


def collect_files(ctx, param, path):
    if os.path.isfile(path):
        yield os.path.dirname(path), os.path.basename(path)
    elif os.path.isdir(path):
        for dirpath, dirnames, filenames in os.walk(path):
            dirpath = os.path.relpath(dirpath, path)
            yield from (
                (path, os.path.join(dirpath, fname)) for fname in filenames
            )


def linkfix_crossref_common_options(f):
    f = common_options(f)
    f = click.argument('filenames', metavar='PATH', nargs=1,
                       required=True, callback=collect_files,
                       type=click.Path(file_okay=True, dir_okay=True,
                                       readable=True, writable=True,
                                       exists=True))(f)
    return f


def format_action_choice_help(choices):
    prefix = "If unspecified, an option is chosen interactively" + \
             " upon each broken link encountered. Possible options: "
    return prefix + ', '.join(
        str(i) + ') ' + k + ': ' + help_txt
        for i, (k, (help_txt, _)) in enumerate(choices.items(), start=1)
    ) + "."


def set_action_choice(ctx, param, value):
    if value is None:
        return
    ui_ctx = ctx.ensure_object(UserInterfaceContext)
    ui_ctx.choice = value
    ui_ctx.apply_to_all = True


@click.command()
@linkfix_crossref_common_options
@click.option('--action',
              type=click.Choice(
                  list(webpub.linkfix.check.link_choices)),
              callback=set_action_choice,
              expose_value=False,
              help="The action to take when a broken link was found. " +
              format_action_choice_help(
                  webpub.linkfix.check.link_choices
              ))
def linkfix_cmd(fallback_url, dry_run, overwrite, filenames):
    """Attempts to fix relative links among the given files.
    Only root-relative (e.g. /www/a/b/c.html) and optionally
    document-relative (e.g. ../b/c.html) are considered.
    """
    import webpub.linkfix
    webpub.linkfix.fixlinks(filenames, fallback_url, dry_run, overwrite)


@click.command()
@linkfix_crossref_common_options
@click.option('--action',
              type=click.Choice(
                  list(webpub.sutta_ref.sutta_ref_choices)),
              callback=set_action_choice,
              expose_value=False,
              help="The action to take when the link to a sutta is"
              " broken. " + format_action_choice_help(
                  webpub.sutta_ref.sutta_ref_choices
              ))
def sutta_cross_ref_cmd(fallback_url, dry_run, overwrite, filenames):
    """Creates cross-references to suttas. Leaves existing references
    intact. Only affects HTML files.
    """
    webpub.sutta_ref.cross_ref(filenames, fallback_url, dry_run, overwrite)


if __name__ == '__main__':
    main()
