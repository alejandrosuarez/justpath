"""Explore PATH environment variable and demonstrate how to modify it."""

import os
import sys
from collections import Counter, UserDict
from dataclasses import dataclass
from json import dumps
from os.path import realpath
from pathlib import Path
from typing import Annotated, Type

from colorama import Fore
from typer import Option, Typer


class PathVar(UserDict[int, Path]):
    @classmethod
    def populate(cls):
        paths = os.environ["PATH"].split(os.pathsep)
        return cls([(i + 1, Path(p)) for i, p in enumerate(paths)])

    def drop(self, i: int):
        del self.data[i]

    def append(self, path: Path):
        key = 1 + max(self.keys())
        self.data[key] = path

    @property
    def max_digits(self) -> int:
        """Number of digits in a line number."""
        return len(str(max(self.keys()))) if self.keys() else 0


@dataclass
class Row:
    i: int
    path: Path
    count: int

    @property
    def error(self) -> Type[FileNotFoundError] | Type[NotADirectoryError] | None:
        if not os.path.exists(self.path):
            return FileNotFoundError
        elif not os.path.isdir(self.path):
            return NotADirectoryError
        else:
            return None

    @property
    def has_error(self):
        return self.error is not None

    def __hash__(self):
        return hash(realpath(self.path).lower())


typer_app = Typer(
    add_completion=False, help="Explore PATH environment variable on Windows and Linux."
)


def show_raw():
    """Print PATH as is."""
    print(os.environ["PATH"])


def show_stats(json: bool = False):
    """Number of directories in your PATH."""
    path_var = PathVar.populate()
    t = len(path_var)
    rows = to_rows(path_var)
    e = sum([1 for row in rows if row.has_error])
    d = sum([1 for row in rows if row.count > 1])
    if json:
        info = dict(total=t, invalid=e, duplicates=d)
        print(dumps(info))
    else:
        print(t, "directories in your PATH")
        print(e, "do" if e > 1 else "does", "not exist")
        print(d, "duplicate" + "s" if d > 1 else "")


def option(help_: str, t=bool):
    return Annotated[t, Option(help=help_)]


@typer_app.command()
def show(
    raw: option("Print PATH variable as is.") = False,  # type: ignore
    count: option("Print number of directories in your PATH.") = False,  # type: ignore
    sort: option("Sort output alphabetically.") = False,  # type: ignore
    invalid: option("Show invalid paths only.") = False,  # type: ignore
    purge_invalid: option("Exclude invalid paths.") = False,  # type: ignore
    duplicates: option("Show duplicate paths only.") = False,  # type: ignore
    purge_duplicates: option("Exclude duplicate paths.") = False,  # type: ignore
    correct: option("Exclude invalid and duplicate paths.") = False,  # type: ignore
    includes: option("Show paths that include a specific string.", str) = "",  # type: ignore
    excludes: option("Show paths that do not include a specific string.", str) = "",  # type: ignore
    bare: option("Hide extra information about paths.") = False,  # type: ignore
    color: option("Use color to highlight errors.") = True,  # type: ignore
    string: option("Print a single string suitable as PATH content.") = False,  # type: ignore
    json: option("Format output as JSON.") = False,  # type: ignore
):
    """Show directories from PATH."""
    if raw:
        show_raw()
        sys.exit(0)
    if count:
        show_stats(json)
        sys.exit(0)
    path_var = PathVar.populate()
    rows = to_rows(path_var)
    if correct:
        purge_duplicates = True
        purge_invalid = True
    rows = modify_rows(
        rows,
        sort,
        duplicates,
        purge_duplicates,
        invalid,
        purge_invalid,
        includes,
        excludes,
    )
    paths = [str(row.path) for row in rows]
    if string:
        print(os.pathsep.join(paths))
    elif json:
        print(dumps(paths, indent=2))
    else:
        for row in rows:
            if bare:
                modifier = get_color(row) if color else ""
                print(modifier + str(row.path))
            else:
                print_row(row, color, path_var.max_digits)


def modify_rows(
    rows,
    sort,
    duplicates,
    purge_duplicates,
    invalid,
    purge_invalid,
    includes,
    excludes,
):
    if sort:
        rows = sorted(rows, key=lambda r: realpath(r.path))
    if duplicates:
        rows = [row for row in rows if row.count > 1]
    if purge_duplicates:
        rows = no_duplicates(rows)
    if invalid:
        rows = [row for row in rows if row.has_error]
    if purge_invalid:
        rows = [row for row in rows if not row.has_error]
    if includes:
        rows = [row for row in rows if includes.lower() in realpath(row.path).lower()]
    if excludes:
        rows = [
            row for row in rows if excludes.lower() not in realpath(row.path).lower()
        ]
    return rows


def get_color(row: Row):
    """Get color modifier for regular, invalid or duplicate directories."""
    if row.has_error:
        return Fore.RED
    elif row.count > 1:
        return Fore.YELLOW
    return Fore.GREEN


def get_postfix(row: Row) -> str:
    """Create a string that tells about a type of error encountered."""
    items = []
    if row.error == FileNotFoundError:
        items.append("directory does not exist")
    elif row.error == NotADirectoryError():
        items.append("not a directory")
    if (n := row.count) > 1:
        items.append(f"duplicates: {n}")
    if items:
        return "(" + ", ".join(items) + ")"
    return ""


def print_row(row: Row, color: bool, n: int):
    modifier = get_color(row) if color else ""
    postfix = get_postfix(row)
    print(modifier + str(row.i).rjust(n), str(row.path), postfix)


def unseen_before(xs):
    seen = set()
    return [x for x in xs if not (x in seen or seen.add(x))]


def no_duplicates(rows):
    paths = [realpath(r.path).lower() for r in rows]
    return make_rows(unseen_before(paths))


def make_rows(paths: list[str]) -> list[Row]:
    counter = Counter([realpath(p) for p in paths])
    rows = []
    for i, path in enumerate(paths):
        row = Row(i, Path(path), counter[realpath(path)])
        rows.append(row)
    return rows


def to_rows(path_var: PathVar) -> list[Row]:
    return make_rows([str(p) for p in path_var.values()])
