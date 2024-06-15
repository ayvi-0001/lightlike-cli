# mypy: disable-error-code="arg-type"

import sys
import typing as t
from datetime import datetime

from prompt_toolkit.shortcuts import CompleteStyle, PromptSession
from prompt_toolkit.validation import Validator

from lightlike.app import cursor, dates, shell_complete, validate
from lightlike.app.config import AppConfig
from lightlike.internal import appdir, utils

__all__: t.Sequence[str] = ("PromptFactory", "REPL_PROMPT_KWARGS")


if len(sys.argv) == 1:
    from lightlike.app.key_bindings import PROMPT_BINDINGS

    bindings = PROMPT_BINDINGS
else:
    from prompt_toolkit.key_binding import KeyBindings

    bindings = KeyBindings()

REPL_PROMPT_KWARGS = dict(
    message=cursor.build,
    history=appdir.REPL_FILE_HISTORY(),
    style=AppConfig().prompt_style,
    cursor=AppConfig().cursor_shape,
    key_bindings=bindings,
    refresh_interval=1,
    complete_in_thread=True,
    complete_while_typing=True,
    validate_while_typing=True,
    enable_system_prompt=True,
    enable_open_in_editor=True,
    reserve_space_for_menu=AppConfig().get(
        "settings",
        "reserve_space_for_menu",
        default=7,
    ),
    complete_style=t.cast(
        CompleteStyle,
        AppConfig().get("settings", "complete_style", default="COLUMN"),
    ),
)


class PromptFactory(PromptSession):
    def __init__(self, **prompt_kwargs) -> None:
        super().__init__(**prompt_kwargs)
        self.style = AppConfig().prompt_style
        self.history = appdir.REPL_FILE_HISTORY()
        self.cursor = AppConfig().cursor_shape
        self.complete_in_thread = True
        self.validate_while_typing = True
        self.complete_while_typing = True
        self.enable_open_in_editor = True
        self.refresh_interval = 1
        self.key_bindings = bindings

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def _prompt(cls, message: str, pre_run: bool = False, **prompt_kwargs) -> t.Any:
        prompt = cls().prompt(
            message=cursor.build(message),
            pre_run=utils._prerun_autocomplete if pre_run else None,
            **prompt_kwargs,
        )
        return prompt

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def prompt_date(cls, message: str, **prompt_kwargs) -> datetime:
        from calendar import day_name, month_name

        from lightlike.app.autosuggest import threaded_autosuggest

        session = cls()
        suggestions = ["yesterday", "today", "now"]
        suggestions.extend(month_name)
        suggestions.extend(day_name)

        session_pk = dict(
            message=cursor.build(message),
            auto_suggest=threaded_autosuggest(suggestions),
            validator=Validator.from_callable(
                lambda d: False if not d else True,
                error_message="Input cannot be None.",
            ),
        )
        session_pk.update(**prompt_kwargs)
        date = session.prompt(**session_pk)
        parsed_date = dates.parse_date(date, tzinfo=AppConfig().tz)
        return parsed_date

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def prompt_note(cls, project: str, message: str = "(note)", **prompt_kwargs) -> str:
        session = cls()
        session_pk = dict(
            message=cursor.build(message, hide_rprompt=True),
            pre_run=utils._prerun_autocomplete,
            completer=shell_complete.notes.Notes(project),
            rprompt=f"Project: {project}",
            validator=Validator.from_callable(
                lambda d: False if not d else True,
                error_message="Input cannot be None.",
            ),
        )
        session_pk.update(**prompt_kwargs)
        note = session.prompt(**session_pk)
        return note

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def prompt_project(
        cls, message: str = "(project)", new: bool = False, **prompt_kwargs
    ) -> str:
        session = cls()
        validator = validate.ExistingProject() if not new else validate.NewProject()
        completer = shell_complete.projects.Active() if not new else None
        bottom_toolbar = lambda: (
            "Name must match regex ^[a-zA-Z0-9-\_]{3,20}$" if new else None
        )
        session_pk = dict(
            message=cursor.build(message, hide_rprompt=True),
            pre_run=utils._prerun_autocomplete,
            completer=completer,
            validator=validator,
            bottom_toolbar=bottom_toolbar,
        )
        session_pk.update(**prompt_kwargs)
        project = session.prompt(**session_pk)
        return project
