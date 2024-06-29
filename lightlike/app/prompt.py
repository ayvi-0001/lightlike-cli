# mypy: disable-error-code="arg-type"

import typing as t
from datetime import datetime

from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.validation import Validator

from lightlike.app import cursor, dates, shell_complete, validate
from lightlike.app.config import AppConfig
from lightlike.app.key_bindings import PROMPT_BINDINGS
from lightlike.internal import appdir, utils

if t.TYPE_CHECKING:
    from lightlike.app.shell_complete.notes import Notes

__all__: t.Sequence[str] = ("PromptFactory",)


T = t.TypeVar("T", bound="PromptFactory")


class PromptFactory(PromptSession[t.Any]):
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
        self.key_bindings = PROMPT_BINDINGS

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def _prompt(
        cls: type[T], message: str, pre_run: bool = False, **prompt_kwargs
    ) -> t.Any:
        prompt: t.Any = cls().prompt(
            message=cursor.build(message),
            pre_run=utils._prerun_autocomplete if pre_run else None,
            **prompt_kwargs,
        )
        return prompt

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def prompt_date(cls: type[T], message: str, **prompt_kwargs) -> datetime:
        from calendar import day_name, month_name

        from lightlike.app.autosuggest import ThreadedAutoSuggest, threaded_autosuggest

        session: T = cls()
        suggestions: list[str] = ["yesterday", "today", "now"]
        suggestions.extend(month_name)
        suggestions.extend(day_name)

        session_pk: dict[str, str | ThreadedAutoSuggest | Validator] = dict(
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
    def prompt_note(
        cls: type[T], project: str, message: str = "(note)", **prompt_kwargs
    ) -> str:
        session: T = cls()
        session_pk: dict[str, str | t.Callable[..., None] | "Notes" | "Validator"] = (
            dict(
                message=cursor.build(message, hide_rprompt=True),
                pre_run=utils._prerun_autocomplete,
                completer=shell_complete.notes.Notes(project),
                rprompt=f"Project: {project}",
                validator=Validator.from_callable(
                    lambda d: False if not d else True,
                    error_message="Input cannot be None.",
                ),
            )
        )
        session_pk.update(**prompt_kwargs)
        note: str = session.prompt(**session_pk)
        return note

    @classmethod
    @utils.exit_cmd_on_interrupt()
    def prompt_project(
        cls: type[T], message: str = "(project)", new: bool = False, **prompt_kwargs
    ) -> str:
        session: T = cls()
        validator = validate.ExistingProject() if not new else validate.NewProject()
        completer = shell_complete.projects.Active() if not new else None
        bottom_toolbar = lambda: (
            r"Name must match regex ^[a-zA-Z0-9-\\_]{3,20}$" if new else None
        )
        session_pk = dict(
            message=cursor.build(message, hide_rprompt=True),
            pre_run=utils._prerun_autocomplete,
            completer=completer,
            validator=validator,
            bottom_toolbar=bottom_toolbar,
        )
        session_pk.update(**prompt_kwargs)
        project: str = session.prompt(**session_pk)
        return project
