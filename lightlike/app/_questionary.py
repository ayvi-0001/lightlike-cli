import typing as t

import rtoml
from prompt_toolkit.completion import Completer
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.shortcuts.prompt import CompleteStyle
from prompt_toolkit.styles import Style
from questionary import Question
from questionary import autocomplete as _autocomplete
from questionary import checkbox as _checkbox
from questionary import confirm as _confirm
from questionary import press_any_key_to_continue as _press_any_key_to_continue
from questionary import select as _select
from questionary import text as _text
from questionary.prompts.common import Choice

from lightlike.__about__ import __config__
from lightlike.internal import constant, utils

__all__: t.Sequence[str] = (
    "checkbox",
    "autocomplete",
    "confirm",
    "press_any_key_to_continue",
    "select",
    "text",
)


STYLE: Style
if not __config__.exists():

    STYLE = Style.from_dict(rtoml.load(constant.PROMPT_STYLE))
else:
    from lightlike.app.config import AppConfig

    STYLE = Style.from_dict(
        utils.update_dict(
            rtoml.load(constant.PROMPT_STYLE),
            AppConfig().get("prompt", "style", default={}),
        )
    )

# Wrapping original functions with default arguments and to automatically call unsafe_ask method.


def checkbox(
    message: str,
    choices: t.Sequence[t.Union[str, Choice, dict[str, t.Any]]],
    default: str | None = None,
    validate: t.Callable[[list[str]], t.Union[bool, str]] = lambda a: True,
    qmark: str = "?",
    pointer: str = "▸",
    style: Style | None = STYLE,
    cursor: CursorShape = CursorShape.BLOCK,
    initial_choice: str | Choice | dict[str, t.Any] | None = None,
    use_arrow_keys: bool = True,
    use_jk_keys: bool = True,
    use_emacs_keys: bool = True,
    instruction: str | None = None,
    **kwargs: t.Any,
) -> t.Any:
    question: Question = _checkbox(
        message,
        choices,
        default=default,
        validate=validate,
        qmark=qmark,
        pointer=pointer,
        style=style,
        cursor=cursor,
        initial_choice=initial_choice,
        use_arrow_keys=use_arrow_keys,
        use_jk_keys=use_jk_keys,
        use_emacs_keys=use_emacs_keys,
        instruction=instruction,
        **kwargs,
    )
    return question.unsafe_ask(patch_stdout=True)


def autocomplete(
    message: str,
    choices: list[str],
    default: str = "",
    qmark: str = "?",
    completer: Completer | None = None,
    meta_information: dict[str, t.Any] | None = None,
    ignore_case: bool = True,
    match_middle: bool = True,
    complete_style: CompleteStyle = CompleteStyle.COLUMN,
    validate: t.Any = None,
    style: Style | None = STYLE,
    cursor: CursorShape = CursorShape.BLOCK,
    **kwargs: t.Any,
) -> t.Any:
    question: Question = _autocomplete(
        message,
        choices=choices,
        default=default,
        qmark=qmark,
        completer=completer,
        meta_information=meta_information,
        ignore_case=ignore_case,
        match_middle=match_middle,
        complete_style=complete_style,
        validate=validate,
        style=style,
        cursor=cursor,
        **kwargs,
    )
    return question.unsafe_ask(patch_stdout=True)


def confirm(
    message: str,
    default: bool = True,
    qmark: str = "?",
    style: Style | None = STYLE,
    cursor: CursorShape = CursorShape.BLOCK,
    auto_enter: bool = True,
    instruction: str | None = None,
    **kwargs: t.Any,
) -> t.Any:
    question: Question = _confirm(
        message,
        default=default,
        qmark=qmark,
        style=style,
        cursor=cursor,
        auto_enter=auto_enter,
        instruction=instruction,
        **kwargs,
    )
    return question.unsafe_ask(patch_stdout=True)


def press_any_key_to_continue(
    message: str | None = None,
    style: Style | None = STYLE,
    cursor: CursorShape = CursorShape.BLOCK,
    **kwargs: t.Any,
) -> t.Any:
    question: Question = _press_any_key_to_continue(
        message,
        style=style,
        cursor=cursor,
        **kwargs,
    )
    return question.unsafe_ask(patch_stdout=True)


def select(
    message: str,
    choices: t.Sequence[t.Union[str, Choice, dict[str, t.Any]]],
    default: str | Choice | dict[str, t.Any] | None = None,
    qmark: str = "?",
    pointer: str = "▸",
    style: Style | None = STYLE,
    cursor: CursorShape = CursorShape.BLOCK,
    use_shortcuts: bool = False,
    use_arrow_keys: bool = True,
    use_indicator: bool = False,
    use_jk_keys: bool = True,
    use_emacs_keys: bool = True,
    show_selected: bool = False,
    instruction: str | None = None,
    **kwargs: t.Any,
) -> t.Any:
    question: Question = _select(
        message,
        choices,
        default=default,
        qmark=qmark,
        pointer=pointer,
        style=style,
        cursor=cursor,
        use_shortcuts=use_shortcuts,
        use_arrow_keys=use_arrow_keys,
        use_indicator=use_indicator,
        use_jk_keys=use_jk_keys,
        use_emacs_keys=use_emacs_keys,
        show_selected=show_selected,
        instruction=instruction,
        **kwargs,
    )
    return question.unsafe_ask(patch_stdout=True)


def text(
    message: str,
    default: str = "",
    validate: t.Any = None,
    qmark: str = "?",
    style: Style | None = STYLE,
    cursor: CursorShape = CursorShape.BLOCK,
    multiline: bool = False,
    instruction: str | None = None,
    lexer: Lexer | None = None,
    **kwargs: t.Any,
) -> t.Any:
    question: Question = _text(
        message,
        default=default,
        validate=validate,
        qmark=qmark,
        style=style,
        cursor=cursor,
        multiline=multiline,
        instruction=instruction,
        lexer=lexer,
        **kwargs,
    )
    return question.unsafe_ask(patch_stdout=True)
