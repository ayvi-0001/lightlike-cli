import typing as t
from pathlib import Path

import click
from rich import get_console
from rich import print as rprint
from rich.filesize import decimal
from rich.markup import escape
from rich.padding import Padding
from rich.text import Text
from rich.tree import Tree

from lightlike.app import shell_complete
from lightlike.app.core import FormattedCommand
from lightlike.internal import utils

__all__: t.Sequence[str] = ("tree",)


@click.command(
    cls=FormattedCommand,
    name="tree",
    hidden=True,
    allow_name_alias=False,
    context_settings=dict(
        allow_extra_args=True,
        ignore_unknown_options=True,
        help_option_names=[],
    ),
)
@utils.handle_keyboard_interrupt()
@click.argument(
    "path",
    type=Path,
    default=lambda: Path.cwd(),
    shell_complete=shell_complete.path,
)
@click.option(
    "-s",
    "--size",
    type=click.BOOL,
    shell_complete=shell_complete.Param("value").bool,
    default=True,
)
def tree(path: Path, size: bool) -> None:
    try:
        with get_console().status(""):
            directory = (path or Path.cwd()).resolve()
            tree = Tree(
                f"[repr.url][link={directory.as_uri()}]" f"{directory.name}",
                highlight=True,
            )

            def walk_directory(directory: Path, tree: Tree) -> None:
                paths = sorted(
                    directory.iterdir(),
                    key=lambda path: (path.is_file(), path.name.lower()),
                )
                for _path in paths:
                    if _path.is_dir():
                        style = "dim " if _path.name.startswith("__") else ""
                        style += "#729fcf"
                        branch = tree.add(
                            f"[link={_path.resolve().as_uri()}]{escape(_path.name)}/",
                            style=style,
                            guide_style=style,
                        )
                        walk_directory(_path, branch)
                    else:
                        text_filename = Text(_path.name, "#f0f0ff")
                        if not _path.name.startswith("."):
                            text_filename.highlight_regex(r"\..*$", "red")
                        text_filename.stylize(f"link {_path.resolve().as_uri()}")
                        if size:
                            text_filename.append(
                                f" ({decimal(_path.stat().st_size)})", "blue"
                            )
                        tree.add(text_filename)

            walk_directory(directory, tree)
            rprint(Padding(tree, (1, 0, 1, 0)))

    except Exception as error:
        rprint(f"{error!r}; {str(path.resolve())!r}")


# import os
# from pathlib import Path
# from lightlike.app import shell_complete
# from lightlike.internal import markup, utils

# @click.command(
#     cls=FormattedCommand,
#     name="ls",
#     hidden=True,
#     context_settings=dict(
#         allow_extra_args=True,
#         ignore_unknown_options=True,
#         help_option_names=[],
#     ),
# )
# @click.argument(
#     "path",
#     type=Path,
#     default=lambda: Path.cwd(),
#     shell_complete=shell_complete.path,
# )
# @utils._nl_start(before=True)
# def ls_(path: Path) -> None:
#     import shutil
#     from contextlib import suppress

#     try:
#         table_kwargs = dict(
#             header_style="#f0f0ff",
#             show_edge=False,
#             show_header=False,
#             box=box.SIMPLE_HEAD,
#         )

#         tables = []
#         for _path in path.iterdir():
#             table = Table(**table_kwargs)  # type: ignore
#             name = Text(_path.name)

#             if " " in name:
#                 name = Text(f"'{name}'")

#             is_link = False
#             if _path.is_symlink() or os.path.islink(_path):
#                 is_link = True
#             with suppress(OSError):
#                 _path.readlink()
#                 is_link = True

#             if not str(name).startswith("."):
#                 name.highlight_regex(r"\.(.*)$", "not bold not dim #f0f0ff")
#             elif _path.is_file():
#                 name.style = "#f0f0ff"
#             if is_link:
#                 name += "@"
#                 name.style = "bold #34e2e2"
#             elif _path.is_dir():
#                 name += "/"
#                 name.style = "bold #729fcf"
#             elif _path.is_socket():
#                 name += "="
#             # elif os.access(_path.resolve(), os.X_OK) or (
#             #     _path.stat().st_mode & stat.S_IXUSR
#             # ):
#             #     name += "*"
#             elif shutil.which(_path.resolve()):
#                 name += "*"
#                 name.style = "bold green"

#             name.highlight_regex(r"@|/|=|\*|\'", "not bold not dim #f0f0ff")
#             name.stylize(f"link {_path.resolve().as_uri()}")

#             table.add_row(name)
#             tables.append(table)

#         rprint(Columns(tables, equal=True))
#     except Exception as error:
#         rprint(f"{error!r}; {str(path.resolve())!r}")
