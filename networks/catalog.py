import sqlite3

from networks.consistency import verify_network
from networks.frozen import CalibrationNetwork, freeze_network
from networks.storage import load_network, store_network
from quantities import require_name


def register_network(connection: sqlite3.Connection, network_id: object,
                     edges: object) -> str:
    proposed = freeze_network(network_id, edges)
    verify_network(proposed)
    connection.execute('BEGIN IMMEDIATE')
    with connection:
        existing = load_network(connection, proposed.network_id)
        if existing is None:
            store_network(connection, proposed)
            return proposed.network_id
        if existing != proposed:
            raise ValueError(
                f'network {proposed.network_id!r} has a different fixed content',
            )
        return existing.network_id


def get_network(connection: sqlite3.Connection, network_id: str) -> CalibrationNetwork:
    require_name(network_id, 'network ID')
    network = load_network(connection, network_id)
    if network is None:
        raise KeyError(network_id)
    return network
