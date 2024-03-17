# mypy: disable-error-code="arg-type, misc"

import functools
from pathlib import Path
from typing import Any, ParamSpec, Sequence

import questionary  # type: ignore[import-not-found]
import rtoml
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.styles import Style

from lightlike._console import PROMPT_TOML

__all__: Sequence[str] = (
    "checkbox",
    "autocomplete",
    "confirm",
    "press_any_key_to_continue",
    "select",
    "text",
)

PROMPT_CONFIG = rtoml.load(PROMPT_TOML)
PROMPT_STYLE = Style.from_dict(PROMPT_CONFIG["style"])
CURSOR_SHAPE = getattr(CursorShape, PROMPT_CONFIG["cursor-shape"])
POINTER = "▸"
DEFAULT_QUESTION_KWARGS = {"style": PROMPT_STYLE}


P = ParamSpec("P")


# Wrap original functions to automatically call unsafe_ask method.


@functools.wraps(questionary.checkbox)
def checkbox(*args: P.args, **kwargs: P.kwargs) -> Any:
    kwargs.update(DEFAULT_QUESTION_KWARGS)
    return questionary.checkbox(**kwargs).unsafe_ask(patch_stdout=True)


@functools.wraps(questionary.autocomplete)
def autocomplete(*args: P.args, **kwargs: P.kwargs) -> Any:
    kwargs.update(DEFAULT_QUESTION_KWARGS)
    return questionary.autocomplete(**kwargs).unsafe_ask(patch_stdout=True)


@functools.wraps(questionary.confirm)
def confirm(*args: P.args, **kwargs: P.kwargs) -> Any:
    kwargs.update(DEFAULT_QUESTION_KWARGS)
    return questionary.confirm(**kwargs).unsafe_ask(patch_stdout=True)


@functools.wraps(questionary.press_any_key_to_continue)
def press_any_key_to_continue(*args: P.args, **kwargs: P.kwargs) -> Any:
    kwargs.update(DEFAULT_QUESTION_KWARGS)
    return questionary.press_any_key_to_continue(**kwargs).unsafe_ask(patch_stdout=True)


@functools.wraps(questionary.select)
def select(*args: P.args, **kwargs: P.kwargs) -> Any:
    kwargs.update(DEFAULT_QUESTION_KWARGS)
    kwargs.update(pointer=POINTER)
    return questionary.select(**kwargs).unsafe_ask(patch_stdout=True)


@functools.wraps(questionary.text)
def text(*args: P.args, **kwargs: P.kwargs) -> Any:
    kwargs.update(DEFAULT_QUESTION_KWARGS)
    return questionary.text(**kwargs).unsafe_ask(patch_stdout=True)
