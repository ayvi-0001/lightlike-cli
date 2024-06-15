import typing as t

import rich_click as click

from lightlike.app.core import LazyAliasedRichGroup


# Debug param exists but print statements have not been adding to functions yet.
# They will be added in the next udpate.
@click.group(
    name="project",
    cls=LazyAliasedRichGroup,
    lazy_subcommands={
        "archive": "lightlike.cmd.project.commands.archive",
        "create": "lightlike.cmd.project.commands.create",
        "delete": "lightlike.cmd.project.commands.delete",
        "list": "lightlike.cmd.project.commands.list_",
        "set": "lightlike.cmd.project.commands.set_",
        "unarchive": "lightlike.cmd.project.commands.unarchive",
    },
    short_help="Create & manage projects.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def project(debug: bool) -> None:
    """Create & manage projects."""


__all__: t.Sequence[str] = ("project",)
