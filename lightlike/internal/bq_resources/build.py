from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from typing import Sequence

from google.api_core.exceptions import BadRequest
from google.cloud.bigquery import Client
from more_itertools import zip_equal
from rich import get_console
from rich.console import Group
from rich.live import Live
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

from lightlike.internal.utils import _regexp_replace
from lightlike.lib.third_party import _questionary

__all__: Sequence[str] = ("run",)


SCRIPTS = Path(f"{__file__}/../sql/").resolve()


@dataclass
class Build:
    name: str
    ordinal: int

    @property
    def path(self) -> Path:
        return SCRIPTS.joinpath(f"build{self.ordinal}")

    @property
    def scripts(self) -> Sequence[Path]:
        return tuple(
            filter(
                lambda p: p.suffix == ".sql" and not p.name.startswith("_"),
                self.path.iterdir(),
            )
        )

    @property
    def names(self) -> Sequence[str]:
        return tuple((path.name for path in self.scripts))


builds = (
    Build(name="Schemas", ordinal=1),
    Build(name="Tables and Functions", ordinal=2),
    Build(name="Views, Procedures, and Table Functions", ordinal=3),
)


def _run_script(
    client: "Client",
    path: Path,
    patterns: dict[str, str],
    step_progress: Progress,
    task_id: TaskID,
) -> None:
    try:
        step_progress.update(task_id, advance=1)
        script = _regexp_replace(patterns=patterns, text=path.read_text())
        step_progress.update(task_id, advance=1)
        script = script.replace("${__name__}", path.stem)
        step_progress.update(task_id, advance=1)
        client.query_and_wait(script)  # type: ignore[attr-defined]
        step_progress.update(task_id, advance=1)
    except BadRequest as err:
        get_console().print("[b][red]Error in script: %s\n[/b]%s\n" % (path.name, err))


def _run_build(
    client: "Client",
    build: Build,
    patterns: dict[str, str],
    app_steps_task_id: TaskID,
    step_progress: Progress,
    build_steps_progress: Progress,
) -> None:
    threads: list[Thread] = []
    task_ids: list[TaskID] = []

    for idx, path in enumerate(build.scripts):
        task_id = step_progress.add_task(
            "", action=build.names[idx], name=build.name, total=7, start=False
        )

        thread = Thread(
            target=_run_script,
            name=f"Thread-N{task_id}",
            args=(client, path, patterns, step_progress, task_id),
            daemon=True,
        )
        threads.append(thread)
        task_ids.append(task_id)

    for thread, task_id in zip_equal(threads, task_ids):
        step_progress.start_task(task_id)
        thread.start()

    for thread in threads:
        step_progress.update(task_id, advance=1)
        task_id = TaskID(int(thread.name.removeprefix("Thread-N")))
        step_progress.update(task_id, advance=1, visible=False)
        step_progress.stop_task(task_id)
        build_steps_progress.update(app_steps_task_id, advance=1)
        thread.join()


def run(client: "Client", patterns: dict[str, str]) -> bool:
    get_console().print(
        Padding(
            Panel.fit(
                "Press [code]y[/code] to build tables/procedures in BigQuery.\n"
                f"These scripts can be viewed in [repr.url][link={SCRIPTS.as_uri()}]"
                f"{escape(SCRIPTS.as_uri())}[/repr.url]."
            ),
            (1, 0, 1, 1),
        )
    )

    if _questionary.confirm(message="Run SQL scripts?", default=False, auto_enter=True):
        get_console().print()
        overall_progress = Progress(
            TimeElapsedColumn(),
            BarColumn(),
            TextColumn("{task.description}"),
            refresh_per_second=30,
        )

        current_build_progress = Progress(
            TimeElapsedColumn(),
            TextColumn("{task.description}"),
            refresh_per_second=30,
        )

        step_progress = Progress(
            TextColumn("  "),
            TimeElapsedColumn(),
            TextColumn("[b][purple]{task.fields[action]}"),
            SpinnerColumn("aesthetic"),
            refresh_per_second=30,
        )

        build_steps_progress = Progress(
            TextColumn(
                "[notice]Progress for build: "
                "{task.fields[name]}: {task.percentage:.0f}%"
            ),
            BarColumn(),
            TextColumn("[b][#f0f0ff]({task.completed} of {task.total} scripts done)"),
            refresh_per_second=30,
        )

        progress_group = Group(
            Padding(
                Panel.fit(
                    Group(
                        current_build_progress,
                        step_progress,
                        build_steps_progress,
                    )
                ),
                (1, 1, 1, 1),
            ),
            Padding(overall_progress, (1, 0, 0, 0)),
        )

        overall_task_id = overall_progress.add_task("", total=len(builds))

        with get_console().screen(style="bold white on red") as screen:
            with Live(progress_group, transient=True):
                for idx, build in enumerate(builds):
                    description_overall_progress = (
                        "[b][#888888](%d out of %d builds completed)"
                        % (idx, len(builds))
                    )

                    overall_progress.update(
                        overall_task_id, description=description_overall_progress
                    )

                    current_task_id = current_build_progress.add_task(
                        "[#f0f0ff]Running scripts for %s" % build.name
                    )

                    build_steps_task_id = build_steps_progress.add_task(
                        "", total=len(range(len(build.scripts))), name=build.name
                    )

                    _run_build(
                        client,
                        build,
                        patterns,
                        build_steps_task_id,
                        step_progress,
                        build_steps_progress,
                    )

                    build_steps_progress.update(
                        build_steps_task_id, advance=1, visible=False
                    )
                    current_build_progress.stop_task(current_task_id)

                    current_build_progress.update(
                        current_task_id,
                        description="[b][green]%s completed." % build.name,
                    )

                    overall_progress.update(overall_task_id, advance=1)

                overall_progress.update(
                    overall_task_id,
                    description="[b][green]%d/%d builds completed."
                    % (len(builds), len(builds)),
                )

            _questionary.press_any_key_to_continue(
                message="Build complete. Press any key to return to console."
            )
            return True

    return False
