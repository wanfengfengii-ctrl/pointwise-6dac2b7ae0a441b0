from networks.frozen import CalibrationNetwork

RouteStep = tuple[str, str]
Route = tuple[RouteStep, ...]

_DIRECTION_ORDER = {'forward': 0, 'reverse': 1}


def _step_key(step: RouteStep) -> tuple[str, int]:
    return step[0], _DIRECTION_ORDER[step[1]]


def _route_key(route: Route) -> tuple[tuple[str, int], ...]:
    return tuple(_step_key(step) for step in route)


def choose_route(network: CalibrationNetwork, source: str, target: str) -> Route:
    """Shortest oriented route; ties resolve by the lexicographic step sequence."""
    if source == target:
        return ()
    adjacency: dict[str, list[tuple[str, str, str]]] = {}
    for edge in network.edges:
        adjacency.setdefault(edge.source, []).append((edge.target, edge.edge_id, 'forward'))
        adjacency.setdefault(edge.target, []).append((edge.source, edge.edge_id, 'reverse'))
    if source not in adjacency:
        raise ValueError(f'no route from {source!r} to {target!r} in network {network.network_id!r}')

    best: dict[str, Route] = {source: ()}
    frontier = [source]
    while frontier:
        next_frontier: dict[str, Route] = {}
        for current in frontier:
            base = best[current]
            for neighbor, edge_id, direction in adjacency.get(current, ()):
                candidate = (*base, (edge_id, direction))
                if neighbor not in best and (
                    neighbor not in next_frontier
                    or _route_key(candidate) < _route_key(next_frontier[neighbor])
                ):
                    next_frontier[neighbor] = candidate
        if not next_frontier:
            break
        for node, route in next_frontier.items():
            best[node] = route
        if target in best:
            return best[target]
        frontier = sorted(next_frontier)
    raise ValueError(f'no route from {source!r} to {target!r} in network {network.network_id!r}')
