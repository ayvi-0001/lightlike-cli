import typing as t
from gettext import gettext

import rich_click as click
from click.types import IntParamType, _NumberParamTypeBase

__all__: t.Sequence[str] = ("CallableIntRange",)


class _CallableNumberRangeBase(_NumberParamTypeBase):
    def __init__(
        self,
        min: t.Optional[float | t.Callable[..., float]] = None,
        max: t.Optional[float | t.Callable[..., float]] = None,
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
        param: t.Optional[click.Parameter],
        ctx: t.Optional[click.Context],
    ) -> t.Any:

        if self.min and callable(self.min):
            _min = self.min()
        else:
            _min = self.min  # type: ignore[assignment]
        if self.max and callable(self.max):
            _max = self.max()
        else:
            _max = self.max  # type: ignore[assignment]

        import operator

        rv = super().convert(value, param, ctx)
        lt_min: bool = _min is not None and (
            operator.le if self.min_open else operator.lt
        )(rv, _min)
        gt_max: bool = _max is not None and (
            operator.ge if self.max_open else operator.gt
        )(rv, _max)

        if self.clamp:
            if lt_min:
                return self._clamp(_min, 1, self.min_open)  # type: ignore

            if gt_max:
                return self._clamp(_max, -1, self.max_open)  # type: ignore

        if lt_min or gt_max:
            self.fail(
                gettext("{value} is not in the range {range}.").format(
                    value=rv, range=self._describe_range()
                ),
                param,
                ctx,
            )

        return rv

    def _describe_range(self) -> str:
        if self.min and callable(self.min):
            _min = self.min()
        else:
            _min = self.min  # type: ignore[assignment]
        if self.max and callable(self.max):
            _max = self.max()
        else:
            _max = self.max  # type: ignore[assignment]

        """Describe the range for use in help text."""
        if _min is None:
            op = "<" if self.max_open else "<="
            return f"x{op}{_max}"

        if _max is None:
            op = ">" if self.min_open else ">="
            return f"x{op}{_min}"

        lop = "<" if self.min_open else "<="
        rop = "<" if self.max_open else "<="
        return f"{_min}{lop}x{rop}{_max}"

    def __repr__(self) -> str:
        clamp = " clamped" if self.clamp else ""
        return f"<{type(self).__name__} {self._describe_range()}{clamp}>"


class CallableIntRange(_CallableNumberRangeBase, IntParamType):
    name = "integer range"

    def _clamp(self, bound: int, dir: t.Literal[1, -1], open: bool) -> int:  # type: ignore
        if not open:
            return bound

        return bound + dir
