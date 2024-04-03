from typing import TYPE_CHECKING, Sequence

import rich_click as click
from rich import print as rprint
from rich.text import Text

from lightlike.app import _get, _pass, render, shell_complete
from lightlike.app.config import AppConfig
from lightlike.app.group import AliasedRichGroup, _RichCommand
from lightlike.internal import markup, utils
from lightlike.lib.third_party import _questionary

if TYPE_CHECKING:
    from google.cloud.bigquery import Client
    from rich.console import Console

    from lightlike.app.routines import CliQueryRoutines

__all__: Sequence[str] = ("snapshots",)


@click.group(
    cls=AliasedRichGroup,
    name="snapshot",
    short_help="Create & Restore timesheet snapshots.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def snapshot(debug: bool) -> None:
    """Create & Restore timesheet snapshots."""


@snapshot.command(
    cls=_RichCommand,
    name="create",
    no_args_is_help=True,
    short_help="Create a snapshot clone.",
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dim("Did not create snapshot.")),
)
@click.argument(
    "table_name",
    type=click.STRING,
    shell_complete=shell_complete.snapshot_table_name,
)
@_pass.routine
@_pass.console
def snapshot_create(
    console: "Console", routine: "CliQueryRoutines", table_name: str
) -> None:
    """Create a snapshot clone."""
    routine.create_snapshot(table_name)
    console.print(
        Text.assemble(
            markup.saved("Saved"), ". Created snapshot ",  # fmt: skip
            markup.code(table_name), ".",  # fmt: skip
        )
    )


@snapshot.command(
    cls=_RichCommand,
    name="restore",
    short_help="Replace timesheet table with a snapshot clone.",
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dim("Did not restore snapshot.")),
)
@_pass.routine
@_pass.console
@_pass.client
def snapshot_restore(
    client: "Client", console: "Console", routine: "CliQueryRoutines"
) -> None:
    """Replace timesheet table with a snapshot clone."""
    try:
        snapshots = list(
            filter(
                lambda t: t.table_type == "SNAPSHOT",
                client.list_tables(routine.dataset_main),
            )
        )

        selection = _questionary.select(
            message="Which snapshot do you want to restore?",
            choices=list(map(_get.table_id, snapshots)),
            instruction="",
            use_indicator=True,
        )
    except ValueError as e:
        if str(e) == "A list of choices needs to be provided.":
            console.print(markup.dim("No snapshots exist"))
            raise utils.click_exit
        else:
            console.print(f"[red]{e}")
            raise utils.click_exit

    if _questionary.confirm(
        message="This will drop your timesheet table and replace it "
        "with a clone of this snapshot. Are you sure?",
        auto_enter=False,
    ):
        routine.restore_snapshot(selection, wait=True, render=True)
        console.print(
            Text.assemble(
                markup.saved("Saved"), ". Restored snapshot ",  # fmt: skip
                markup.code(selection), ".",  # fmt: skip
            )
        )

    else:
        console.print(markup.dim("Did not restore snapshot."))


@snapshot.command(
    cls=_RichCommand,
    name="list",
    short_help="View current snapshot clones.",
)
@_pass.routine
@_pass.console
def snapshot_list(console: "Console", routine: "CliQueryRoutines") -> None:
    """View current snapshot clones."""
    table = render.row_iter_to_rich_table(
        row_iterator=routine.select(
            resource=f"{routine.dataset_main}.INFORMATION_SCHEMA.TABLES",
            fields=[
                "table_name",
                "timestamp_trunc(creation_time, second) as creation_time",
                "timestamp_trunc(snapshot_time_ms, second) as snapshot_time_ms",
            ],
            where=["snapshot_time_ms is not null"],
            order=["creation_time"],
        ).result(),
    )

    if not table.row_count:
        console.print(markup.dim("No snapshots found"))
    else:
        render.new_console_print(table)


@snapshot.command(
    cls=_RichCommand,
    name="delete",
    short_help="Drop a snapshot clone.",
)
@utils._handle_keyboard_interrupt(
    callback=lambda: rprint(markup.dim("Did not delete snapshot.")),
)
@_pass.console
@_pass.client
def snapshot_delete(client: "Client", console: "Console") -> None:
    """Drop a snapshot clone."""
    dataset = AppConfig().get("bigquery", "dataset")

    snapshots = list(
        filter(
            lambda t: t.table_type == "SNAPSHOT",
            client.list_tables(dataset),
        )
    )

    choices = list(map(_get.table_id, snapshots))

    if not choices:
        console.print(markup.dim("No snapshots exist"))
        raise utils.click_exit

    selection = _questionary.checkbox(
        message="Select snapshots to delete $",
        choices=list(map(_get.table_id, snapshots)),
    )

    if selection and _questionary.confirm(
        message="Are you sure?", auto_enter=True, default=False
    ):
        for snapshot in selection:
            client.delete_table(f"{dataset}.{snapshot}")
            console.print(Text.assemble(f"Deleted ", markup.code(snapshot), "."))
    else:
        console.print(markup.dim("Did not select any snapshots."))
