import ast
import typing as t

import click
from click.shell_completion import CompletionItem

from lightlike.internal import utils

__all__: t.Sequence[str] = ("Param",)


class Param:
    def __init__(
        self, param_name: str, completion_items: t.Sequence[t.Any] = []
    ) -> None:
        self.param_name = param_name
        self.completion_items = completion_items

    def bool(
        self,
        ctx: click.Context,
        param: click.Parameter,
        incomplete: str,
    ) -> t.Sequence[CompletionItem]:
        completion_items = []

        if ctx.params.get(self.param_name) is None or param.default is not None:
            bool_values = {
                "true": ("1", "true", "t", "yes", "y"),
                "false": ("0", "false", "f", "no", "n"),
            }

            for k, v in bool_values.items():
                if any(i.startswith(incomplete) for i in v):
                    completion_items.append(
                        CompletionItem(value=k, help=f"[{', '.join(v)}]")
                    )

        return completion_items

    def string(
        self,
        ctx: click.Context,
        param: click.Parameter,
        incomplete: str,
    ) -> t.Sequence[str | None]:
        completion_items = []
        if (
            ctx.params.get(self.param_name) is None
            or ctx.params.get(self.param_name) == param.default
        ):
            for item in self.completion_items:
                if utils._match_str(incomplete, item):
                    completion_items.append(item)

        return completion_items


class LiteralEvalArg(click.Argument):
    def type_cast_value(self, ctx: click.Context, value: t.Any) -> t.Any:
        try:
            return ast.literal_eval(value)
        except:
            raise click.BadParameter(value)
