from dataclasses import dataclass
from fractions import Fraction

from calibration.curves import Knot, evaluate_segment, locate_segment
from calibration.frozen import DirectCurve, OrientedCurve
from calibration.inverse import orient_curve
from networks.frozen import CalibrationNetwork, NetworkEdge
from networks.piecewise import IDENTITY, Piecewise, pl_compose, pl_evaluate
from networks.routing import Route
from observations.series import Sample
from processing.spans import ClippedSpan


@dataclass(frozen=True, slots=True)
class PathStep:
    edge_id: str
    direction: str
    segment_index: int
    knots: tuple[Knot, Knot]


@dataclass(frozen=True, slots=True)
class NetworkContribution:
    start: Fraction
    end: Fraction
    samples: tuple[Sample, Sample]
    path: tuple[PathStep, ...]
    integral: Fraction


def orient_step(edge: NetworkEdge, direction: str) -> OrientedCurve:
    curve = DirectCurve(edge.edge_id, edge.source, edge.target, edge.knots)
    if direction == 'forward':
        return orient_curve(curve, edge.source, edge.target)
    return orient_curve(curve, edge.target, edge.source)


def orient_route(network: CalibrationNetwork, route: Route) -> tuple[OrientedCurve, ...]:
    edges = {edge.edge_id: edge for edge in network.edges}
    return tuple(orient_step(edges[edge_id], direction) for edge_id, direction in route)


def oriented_piecewise(step: OrientedCurve) -> Piecewise:
    """Breakpoints of an oriented edge; reversed steps swap the original knot axes."""
    points = tuple(segment.left for segment in step.segments) + (step.segments[-1].right,)
    if step.direction == 'reverse':
        points = tuple((y, x) for x, y in points)
    return points


def route_piecewise(steps: tuple[OrientedCurve, ...]) -> Piecewise:
    function = IDENTITY
    for step in steps:
        function = pl_compose(oriented_piecewise(step), function)
    return function


def _path_for_reading(value: Fraction, steps: tuple[OrientedCurve, ...]) -> tuple[PathStep, ...]:
    path = []
    for step in steps:
        segment = locate_segment(step.segments, value)
        path.append(PathStep(
            step.curve_id, step.direction, segment.index, (segment.left, segment.right),
        ))
        value = evaluate_segment(segment, value)
    return tuple(path)


def split_network_span(span: ClippedSpan, steps: tuple[OrientedCurve, ...],
                       composite: Piecewise):
    cuts = [(span.start, span.start_reading), (span.end, span.end_reading)]
    change = span.end_reading - span.start_reading
    if change:
        low, high = sorted((span.start_reading, span.end_reading))
        duration = span.end - span.start
        for knot, _ in composite[1:-1]:
            if low < knot < high:
                time = span.start + duration * (knot - span.start_reading) / change
                cuts.append((time, knot))
        cuts.sort()
    for (start, x0), (end, x1) in zip(cuts, cuts[1:]):
        output_start = pl_evaluate(composite, x0)
        output_end = pl_evaluate(composite, x1)
        integral = (end - start) * (output_start + output_end) / 2
        yield NetworkContribution(
            start, end, span.samples, _path_for_reading((x0 + x1) / 2, steps), integral,
        )
