import os.path
import functools as ft

import cssutils

from .route import routed_url

cssutils.ser.prefs.keepUsedNamespaceRulesOnly = True
cssutils.ser.prefs.indentClosingBrace = False
cssutils.ser.prefs.omitLastSemicolon = False


def replace_urls(epub_zip, routes, root_dir, filepath, verbosity):
    style_string = epub_zip.read(os.path.join(root_dir, filepath))
    stylesheet = cssutils.parseString(style_string)
    cssutils.replaceUrls(
        stylesheet,
        ft.partial(routed_url, filepath, routes, root_dir, verbosity)
    )
    return stylesheet.cssText
