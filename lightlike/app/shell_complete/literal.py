import ast
from typing import Any, Sequence

import rich_click as click

__all__: Sequence[str] = ("PythonLiteralOption",)


class PythonLiteralOption(click.Option):
    def type_cast_value(self, ctx: click.Context, value: Any) -> Any:
        try:
            return ast.literal_eval(value)
        except:
            raise click.BadParameter(value)
