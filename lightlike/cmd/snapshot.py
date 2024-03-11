from typing import TYPE_CHECKING, Sequence

import rich_click as click
from rich import get_console

from lightlike.app import _get, _pass, render, shell_complete
from lightlike.app.config import AppConfig
from lightlike.app.group import AliasedRichGroup, _RichCommand
from lightlike.internal import utils
from lightlike.lib.third_party import _questionary

if TYPE_CHECKING:
    from google.cloud.bigquery import Client
    from rich.console import Console

    from lightlike.app.routines import CliQueryRoutines

__all__: Sequence[str] = ("snapshots",)


get_console().log(f"[log.main]Loading command group: {__name__}")


@click.group(
    cls=AliasedRichGroup,
    help="Create & Restore timesheet snapshots.",
    short_help="Create & Restore timesheet snapshots.",
)
@click.option("-d", "--debug", is_flag=True, hidden=True)
def snapshot(debug: bool) -> None: ...


@snapshot.command(
    cls=_RichCommand,
    name="create",
    no_args_is_help=True,
    short_help="Create a snapshot clone.",
)
@utils._handle_keyboard_interrupt(
    callback=lambda: get_console().print("[d]Did not create snapshot.\n")
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
        f"[saved]Saved[/saved]. Created snapshot [code]{table_name}[/code].\n"
    )


@snapshot.command(
    cls=_RichCommand,
    name="restore",
    short_help="Replace timesheet table with a snapshot clone.",
)
@utils._handle_keyboard_interrupt(
    callback=lambda: get_console().print("[d]Did not restore snapshot.\n")
)
@_pass.routine
@_pass.console
@_pass.client
@click.pass_context
def snapshot_restore(
    ctx: click.Context,
    client: "Client",
    console: "Console",
    routine: "CliQueryRoutines",
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
            ctx.fail("No snapshots exist")
        else:
            ctx.fail(f"{e}")

    if _questionary.confirm(
        message="This will drop your timesheet table and replace it "
        "with a clone of this snapshot. Are you sure?",
        auto_enter=False,
    ):
        routine.restore_snapshot(selection, wait=True, render=True)
        console.print(
            "[saved]Saved[/saved]. " f"Restored snapshot [code]{selection}[/code].\n"
        )

    else:
        console.print("[d]Did not restore snapshot.\n")


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
                "DATE(creation_time) AS creation_time",
                "DATE(snapshot_time_ms) AS snapshot_time_ms",
            ],
            where="snapshot_time_ms is not null",
            order="creation_time",
        ).result(),
    )

    if not table.row_count:
        console.print("[d]No snapshots found.\n")
        return
    else:
        render.new_console_print(table)


@snapshot.command(
    cls=_RichCommand,
    name="delete",
    short_help="Drop a snapshot clone.",
)
@utils._handle_keyboard_interrupt(
    callback=lambda: get_console().print("[d]Did not delete snapshot.\n")
)
@_pass.console
@_pass.client
@utils._nl_start()
def snapshot_delete(client: "Client", console: "Console") -> None:
    """Drop a snapshot clone."""
    dataset = AppConfig().get("bigquery", "dataset")

    snapshots = list(
        filter(
            lambda t: t.table_type == "SNAPSHOT",
            client.list_tables(dataset),
        )
    )

    selection = _questionary.checkbox(
        message="Select snapshots to delete $",
        choices=list(map(_get.table_id, snapshots)),
    )

    if selection and _questionary.confirm(
        message="Are you sure?", auto_enter=True, default=False
    ):
        for snapshot in selection:
            client.delete_table(f"{dataset}.{snapshot}")
            console.print(f"Deleted [code]{snapshot}[/code].")
    else:
        console.print(f"[d]Did not select any snapshots.")
