from collections import OrderedDict
import dependency_injection
import mimetypes
import mimeparse
import os

from webpub.transform_document import transform_document
from webpub.transform_toc import transform_toc
from webpub.transform import render_template
from webpub.css import replace_urls
from webpub.util import copy_out, write_out


class Route(object):
    def __init__(self, src, mimetype=None):
        self.src = src
        self._mimetype = mimetype

    @property
    def dst(self):
        raise NotImplementedError()

    @property
    def handlers(self):
        raise NotImplementedError()

    @property
    def mimetype(self):
        return self._mimetype or mimetypes.guess_type(self.src)[0]


class IdentityRoute(Route):
    def __init__(self, src, dst, mimetype=None):
        super().__init__(src, mimetype)
        self._dst = dst

    @property
    def dst(self):
        return self._dst or os.path.basename(self.src)

    def handlers(self):
        return (copy_out,)


def _ensure_html_extension(path):
    return './' + os.path.basename(os.path.splitext(path)[0] + '.html')


# Dict from mimetype media ranges to handlers and destination directory.
default_mime_to_dst_and_handlers = {
    'text/html': (_ensure_html_extension,
                  (transform_document, render_template,
                   write_out)),
    'application/xhtml+xml': 'text/html',
    'application/x-dtbncx+xml': (lambda _: './Contents.html',
                                 (transform_toc, render_template,
                                  write_out)),
    'text/css': ('./css/', (replace_urls, write_out)),
    'image/*': ('./img/', (copy_out,)),
    '*/*': ('./etc/', (copy_out,))
}


class MimetypeRoute(Route):
    def get_mime_to_handlers(self):
        return default_mime_to_dst_and_handlers

    def get_handlers(self):
        mimetype_handlers = self.get_mime_to_handlers()
        mime_match = mimeparse.best_match(
            mimetype_handlers.keys(), self.mimetype
        )
        str_or_tup = mimetype_handlers[mime_match]
        while isinstance(str_or_tup, str):
            str_or_tup = mimetype_handlers[str_or_tup]
        return str_or_tup

    @property
    def dst(self):
        dst, _handlers = self.get_handlers()

        if callable(dst):
            return dst(self.src)
        return os.path.join(dst, os.path.basename(self.src))

    @property
    def handlers(self):
        _dst, handlers = self.get_handlers()
        return handlers


class AbortHandling(Exception):
    """Aborts handlers."""


class SkipHandler(Exception):
    """Skips the current handler and continues to the next one."""


def _apply_handlers(handlers, context):
    print("Start handling {}.".format(context['filepath']))
    for handler in handlers:
        kwargs = dependency_injection.resolve_dependencies(
            handler, context
        ).as_kwargs
        print(" - {}".format(handler.__name__))
        try:
            context['input'] = handler(**kwargs)
        except SkipHandler:
            continue
        except AbortHandling:
            break

    del context['input']


def handle_routes(routes, context):
    context.setdefault('routes', {})
    context.setdefault('src_to_title', {})
    handlers_with_input = OrderedDict()
    for route in routes:
        src = route.src
        handlers = route.handlers
        context['routes'][src] = route.dst
        handlers_with_input.setdefault(handlers, []).append(src)

    for handlers, srcs in handlers_with_input.items():
        for src in srcs:
            context['filepath'] = src
            context['section_title'] = context['src_to_title'].get(src, '')
            _apply_handlers(handlers, context)
