import argparse
import itertools as it


def int_or_toc(val):
    try:
        i = int(val)
    except ValueError:
        if val == 'toc':
            i = 0
        else:
            raise argparse.ArgumentTypeError(
                "Invalid argument, must be 'toc' or a number greater than 0"
            )
    else:
        if i < 1:
            raise argparse.ArgumentTypeError("Numbers must be greater than 0")
    return i


class make_order(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        filled_values = it.chain(
            values[:],
            (i for i in it.count(1) if i not in values)
        )
        setattr(namespace, self.dest + '_orig', values)
        setattr(namespace, self.dest, filled_values)


parser = argparse.ArgumentParser(
    description="Process EPUB documents for web publishing."
)
parser.add_argument('-d', dest='output_dir', metavar='DIR', default='_result',
                    help="Output directory (defaults to ./_result/)")
parser.add_argument('--spine-order', metavar='N', default=it.count(),
                    nargs='+', type=int_or_toc, action=make_order,
                    help="Reorder the chapter order for next/previous buttons."
                    " Input is a sequence of one or more positive non-zero"
                    " numbers, or the special value 'toc'."
                    " (defaults to 'toc 1 2 3 ...')")
parser.add_argument('--toc-order', metavar='N', default=None, nargs='+',
                    type=int_or_toc, action=make_order,
                    help="Reorder the order of the entries in the table of"
                    " contents. Input is a sequence of one or more positive"
                    " non-zero numbers, or the special value 'toc'."
                    " (defaults to --spine-order or 'toc 1 2 3 ...')")
parser.add_argument('epub_filename', metavar='INFILE',
                    help="The EPUB input file.")
parser.add_argument('-t', '--template', metavar='TEMPLATE',
                    default='./default_template.html',
                    help="The template HTML file in which the content is"
                    " inserted for each section.")


def parse_args():
    args = parser.parse_args()

    if not args.toc_order:
        args.spine_order, args.toc_order = it.tee(args.spine_order)

    return args


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


args = parse_args()
