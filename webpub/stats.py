from collections import defaultdict
from contextlib import AbstractContextManager

import click.exceptions

class FileStats(AbstractContextManager):
    def __init__(self, global_stats, filepath):
        self.global_stats = global_stats
        self.filepath = filepath

    def set_changed(self, stat=None, value=None):
        if stat is not None:
            self.set(stat, value)
        self.global_stats.add('changed', self.filepath)

    def set(self, stat, value=None):
        self.global_stats.add(stat, value or self.filepath)

    def has_changed(self):
        return self.filepath in self.global_stats.statistics['changed']

    def __exit__(self, exc_t, exc_v, traceback):
        if exc_t is None:
            self.global_stats.add('processed', self.filepath)
        elif exc_t is not click.exceptions.Abort:
            self.global_stats.add('failed', self.filepath)


class GlobalStats(object):
    stats_formatters = {}

    def __init__(self, include=['changed', 'saved'], exclude=[]):
        self.statistics = defaultdict(set)
        for stat in include:
            self.include(stat)
        self.exclude = exclude[:]

    @classmethod
    def register_statistic_formatter(cls, stat, formatter):
        if isinstance(formatter, str):
            formatter = formatter.format
        cls.stats_formatters[stat] = formatter

    @classmethod
    def remove_statistic_formatter(cls, stat):
        return cls.stats_formatters.pop(stat, None)

    def include(self, stat):
        self.statistics[stat]

    def exclude(self, stat):
        self.statistics.pop(stat, None)
        self.exclude.append(stat)

    def add(self, stat, value):
        if stat not in self.exclude:
            self.statistics[stat].add(value)

    def scope(self, src):
        return FileStats(self, src)

    def format_summary(self):
        summaries = []
        for stat, values in self.statistics.items():
            formatter = self.stats_formatters.get(stat)
            if formatter is None:
                continue
            summaries.append(formatter(count=len(values), stat=stat))
        return ", ".join(summaries)


def _format_file_stat(count, stat):
    files = "files"
    count = count
    if count == 0:
        count = "no"
    elif count == 1:
        files = "file"

    return "{count} {files} {stat}".format(count=count, files=files, stat=stat)


GlobalStats.register_statistic_formatter('processed', _format_file_stat)
GlobalStats.register_statistic_formatter('saved', _format_file_stat)
GlobalStats.register_statistic_formatter('failed', _format_file_stat)
GlobalStats.register_statistic_formatter('changed', _format_file_stat)

global_stats = GlobalStats()
format_summary = global_stats.format_summary
