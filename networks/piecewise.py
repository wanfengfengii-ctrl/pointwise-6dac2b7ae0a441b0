from bisect import bisect_right
from fractions import Fraction

Point = tuple[Fraction, Fraction]
Piecewise = tuple[Point, ...]

IDENTITY: Piecewise = ((Fraction(0), Fraction(0)), (Fraction(1), Fraction(1)))


def _xs(function: Piecewise) -> tuple[Fraction, ...]:
    return tuple(point[0] for point in function)


def pl_evaluate(function: Piecewise, value: Fraction) -> Fraction:
    """Evaluate a continuous piecewise-linear function at an exact rational point."""
    if not function[0][0] <= value <= function[-1][0]:
        raise ValueError('piecewise input is outside its domain')
    xs = _xs(function)
    index = bisect_right(xs, value) - 1
    if index == len(function) - 1:
        return function[-1][1]
    x0, y0 = function[index]
    x1, y1 = function[index + 1]
    if value == x0:
        return y0
    relative = (value - x0) / (x1 - x0)
    return y0 + relative * (y1 - y0)


def pl_invert(function: Piecewise) -> Piecewise:
    """Swap the axes of a strictly monotone piecewise-linear function."""
    return tuple((y, x) for x, y in function)


def pl_compose(outer: Piecewise, inner: Piecewise) -> Piecewise:
    """Return outer(inner(x)); both functions stay exact and strictly increasing."""
    inverse_inner = pl_invert(inner)
    cuts = {x for x, _ in inner}
    cuts.update(pl_evaluate(inverse_inner, u) for u, _ in outer)
    points = []
    for x in sorted(cuts):
        points.append((x, pl_evaluate(outer, pl_evaluate(inner, x))))
    return tuple(points)


def pl_equal(left: Piecewise, right: Piecewise) -> bool:
    """Exact equality of two [0,1] piecewise-linear functions over the full range."""
    cuts = {x for x, _ in left} | {x for x, _ in right}
    return all(pl_evaluate(left, x) == pl_evaluate(right, x) for x in cuts)
