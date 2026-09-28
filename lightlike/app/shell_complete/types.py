import typing as t
from gettext import gettext
from inspect import cleandoc

import click
from click.types import IntParamType, _NumberParamTypeBase

__all__: t.Sequence[str] = ("CallableIntRange", "DynamicHelpOption")


class _CallableNumberRangeBase(_NumberParamTypeBase):
    def __init__(
        self,
        min: float | t.Callable[..., float] | None = None,
        max: float | t.Callable[..., float] | None = None,
        min_open: bool = False,
        max_open: bool = False,
        clamp: bool = False,
    ) -> None:
        self.min = min
        self.max = max
        self.min_open = min_open
        self.max_open = max_open
        self.clamp = clamp

    def convert(
        self,
        value: t.Any,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> t.Any:
        if self.min and callable(self.min):
            min_ = self.min()
        else:
            min_ = self.min  # type: ignore[assignment]
        if self.max and callable(self.max):
            max_ = self.max()
        else:
            max_ = self.max  # type: ignore[assignment]

        import operator

        rv = super().convert(value, param, ctx)
        lt_min: bool = min_ is not None and (operator.le if self.min_open else operator.lt)(
            rv,
            min_,
        )
        gt_max: bool = max_ is not None and (operator.ge if self.max_open else operator.gt)(
            rv,
            max_,
        )

        if self.clamp:
            if lt_min:
                return self._clamp(min_, 1, self.min_open)  # type: ignore

            if gt_max:
                return self._clamp(max_, -1, self.max_open)  # type: ignore

        if lt_min or gt_max:
            self.fail(
                gettext("{value} is not in the range {range}.").format(
                    value=rv,
                    range=self._describe_range(),
                ),
                param,
                ctx,
            )

        return rv

    def _describe_range(self) -> str:
        if self.min and callable(self.min):
            min_ = self.min()
        else:
            min_ = self.min  # type: ignore[assignment]
        if self.max and callable(self.max):
            max_ = self.max()
        else:
            max_ = self.max  # type: ignore[assignment]

        """Describe the range for use in help text."""
        if min_ is None:
            op = "<" if self.max_open else "<="
            return f"x{op}{max_}"

        if max_ is None:
            op = ">" if self.min_open else ">="
            return f"x{op}{min_}"

        lop = "<" if self.min_open else "<="
        rop = "<" if self.max_open else "<="
        return f"{min_}{lop}x{rop}{max_}"

    def __repr__(self) -> str:
        clamp = " clamped" if self.clamp else ""
        return f"<{type(self).__name__} {self._describe_range()}{clamp}>"


class CallableIntRange(_CallableNumberRangeBase, IntParamType):
    name = "integer range"

    def _clamp(self, bound: int, dir: t.Literal[1, -1], open: bool) -> int:
        if not open:
            return bound

        return bound + dir


class DynamicHelpOption(click.Option):
    def __init__(
        self,
        param_decls: t.Sequence[str] | None = None,
        show_default: bool | str | None = None,
        prompt: bool | str = False,
        confirmation_prompt: bool | str = False,
        prompt_required: bool = True,
        hide_input: bool = False,
        is_flag: bool | None = None,
        flag_value: t.Any | None = None,
        multiple: bool = False,
        count: bool = False,
        allow_from_autoenv: bool = True,
        type: click.ParamType | t.Any | None = None,
        help: str | None = None,
        hidden: bool = False,
        show_choices: bool = True,
        show_envvar: bool = False,
        **attrs: t.Any,
    ) -> None:
        super().__init__(
            param_decls,
            show_default,
            prompt,
            confirmation_prompt,
            prompt_required,
            hide_input,
            is_flag,
            flag_value,
            multiple,
            count,
            allow_from_autoenv,
            type,
            None,  # help,
            hidden,
            show_choices,
            show_envvar,
            **attrs,
        )

        self.help = cleandoc(help) if help and not callable(help) else help
