from dataclasses import dataclass

from calibration.curves import Knot, normalize_knots
from quantities import require_name


@dataclass(frozen=True, slots=True)
class NetworkEdge:
    edge_id: str
    source: str
    target: str
    knots: tuple[Knot, ...]


@dataclass(frozen=True, slots=True)
class CalibrationNetwork:
    network_id: str
    edges: tuple[NetworkEdge, ...]


def _unpack_edge(record: object) -> tuple[object, object, object, object]:
    if isinstance(record, (str, bytes)):
        raise ValueError('network edge must be a four-item record')
    try:
        items = tuple(record)
    except TypeError as error:
        raise ValueError('network edge must be a four-item record') from error
    if len(items) != 4:
        raise ValueError('network edge must be a four-item record')
    return items[0], items[1], items[2], items[3]


def freeze_network(network_id: object, edge_records: object) -> CalibrationNetwork:
    require_name(network_id, 'network ID')
    if isinstance(edge_records, (str, bytes, dict)):
        raise ValueError('network edges must be a sequence of four-item records')
    try:
        iterator = iter(edge_records)
    except TypeError as error:
        raise ValueError('network edges must be a sequence of four-item records') from error
    edges = []
    seen: set[str] = set()
    for record in iterator:
        raw_id, raw_source, raw_target, raw_knots = _unpack_edge(record)
        edge_id = require_name(raw_id, 'edge ID')
        source = require_name(raw_source, 'edge source scale')
        target = require_name(raw_target, 'edge target scale')
        if source == target:
            raise ValueError('edge endpoints must be different scales')
        if edge_id in seen:
            raise ValueError(f'duplicate edge ID {edge_id!r} within network')
        seen.add(edge_id)
        edges.append(NetworkEdge(edge_id, source, target, normalize_knots(raw_knots)))
    edges.sort(key=lambda edge: edge.edge_id)
    return CalibrationNetwork(network_id, tuple(edges))
