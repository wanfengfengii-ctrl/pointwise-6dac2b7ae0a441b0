from networks.frozen import CalibrationNetwork, NetworkEdge
from networks.piecewise import IDENTITY, Piecewise, pl_compose, pl_equal


def edge_function(edge: NetworkEdge, direction: str) -> Piecewise:
    """Piecewise-linear mapping of one oriented edge, using registration-direction knots."""
    function = tuple(edge.knots)
    if direction == 'reverse':
        function = tuple((y, x) for x, y in function)
    return function


def _orient(edge: NetworkEdge, source: str, target: str) -> tuple[str, Piecewise]:
    if (source, target) == (edge.source, edge.target):
        return 'forward', edge_function(edge, 'forward')
    if (source, target) == (edge.target, edge.source):
        return 'reverse', edge_function(edge, 'reverse')
    raise ValueError('edge does not connect the requested scales')


def verify_network(network: CalibrationNetwork) -> None:
    """Reject the whole network unless every route inside a component is identical."""
    adjacency: dict[str, list[NetworkEdge]] = {}
    for edge in network.edges:
        adjacency.setdefault(edge.source, []).append(edge)
        adjacency.setdefault(edge.target, []).append(edge)

    canonical: dict[str, Piecewise] = {}
    for root in sorted(adjacency):
        if root in canonical:
            continue
        canonical[root] = IDENTITY
        pending = [root]
        while pending:
            current = pending.pop()
            for edge in adjacency[current]:
                neighbor = edge.target if edge.source == current else edge.source
                direction, function = _orient(edge, current, neighbor)
                expected = pl_compose(function, canonical[current])
                if neighbor in canonical:
                    if not pl_equal(canonical[neighbor], expected):
                        raise ValueError(
                            f'network {network.network_id!r} has conflicting calibration routes',
                        )
                else:
                    canonical[neighbor] = expected
                    pending.append(neighbor)
