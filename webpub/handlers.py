from collections import OrderedDict
import dependency_injection
import mimetypes
import mimeparse
import os

from webpub.ui import echo


class Route(object):
    def __init__(self, src, output_dir=None, mimetype=None):
        self.src = os.path.normpath(src)
        self.output_dir = output_dir
        self._mimetype = mimetype

    def get_dst(self):
        raise NotImplementedError()

    @property
    def dst(self):
        if self.output_dir is None:
            return self.get_dst()
        return os.path.normpath(os.path.join(self.output_dir, self.get_dst()))

    @property
    def handlers(self):
        raise NotImplementedError()

    @property
    def mimetype(self):
        return self._mimetype or mimetypes.guess_type(self.src)[0] or '*/*'


class MimetypeRoute(Route):
    def get_mime_to_handlers(self):
        raise NotImplementedError()

    def get_handlers(self):
        mimetype_handlers = self.get_mime_to_handlers()
        mime_match = mimeparse.best_match(
            mimetype_handlers.keys(), self.mimetype
        )
        str_or_tup = mimetype_handlers[mime_match]
        while isinstance(str_or_tup, str):
            str_or_tup = mimetype_handlers[str_or_tup]
        return str_or_tup

    def get_dst(self):
        dst, _handlers = self.get_handlers()

        if callable(dst):
            return dst(self.src)
        return os.path.join(dst, os.path.basename(self.src))

    @property
    def handlers(self):
        _dst, handlers = self.get_handlers()
        return handlers


class ConstDestMimetypeRoute(MimetypeRoute):
    def __init__(self, src, root_dir, output_dir=None, mimetype=None):
        if output_dir is None:
            output_dir = root_dir
        super().__init__(os.path.join(root_dir, src), output_dir, mimetype)
        root_base = os.path.basename(root_dir)
        self._dst = os.path.join(root_base, src)

    def get_dst(self):
        return self._dst

    @property
    def handlers(self):
        return self.get_handlers()


class AbortHandling(Exception):
    """Aborts handlers."""


class SkipHandler(Exception):
    """Skips the current handler and continues to the next one."""


def _apply_handlers(handlers, context):
    echo(
        "\nStart handling {}.".format(os.path.relpath(context['filepath'])),
        verbosity=1
    )
    for handler in handlers:
        kwargs = dependency_injection.resolve_dependencies(
            handler, context
        ).as_kwargs

        handler_verbosity = getattr(handler, "verbosity", 1)
        handler_name = getattr(handler, "verbose_name", handler.__name__)
        echo("\n - {}".format(handler_name), verbosity=handler_verbosity)

        try:
            context['input'] = handler(**kwargs)
        except SkipHandler:
            continue
        except AbortHandling as e:
            print(str(e))
            break

    context.pop('input', None)


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
            context['currentpath'] = src
            context['section_title'] = context['src_to_title'].get(src, '')
            _apply_handlers(handlers, context)
