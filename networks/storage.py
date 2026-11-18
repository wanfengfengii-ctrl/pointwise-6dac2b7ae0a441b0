import sqlite3
from fractions import Fraction

from networks.frozen import CalibrationNetwork, NetworkEdge

REPORT_KIND_DIRECT = 'direct'
REPORT_KIND_NETWORK = 'network'


def ensure_network_schema(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS networks (
            network_id TEXT PRIMARY KEY NOT NULL
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS network_edges (
            network_id TEXT NOT NULL REFERENCES networks(network_id),
            edge_id TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            CHECK (source <> target),
            PRIMARY KEY (network_id, edge_id),
            UNIQUE (network_id, ordinal)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS network_edge_knots (
            network_id TEXT NOT NULL,
            edge_id TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            x TEXT NOT NULL,
            y TEXT NOT NULL,
            PRIMARY KEY (network_id, edge_id, ordinal),
            FOREIGN KEY (network_id, edge_id) REFERENCES network_edges(network_id, edge_id)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS network_reports (
            report_id TEXT PRIMARY KEY NOT NULL,
            batch_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            network_id TEXT NOT NULL REFERENCES networks(network_id),
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            coverage TEXT NOT NULL,
            total TEXT NOT NULL,
            FOREIGN KEY (batch_id, revision) REFERENCES batch_revisions(batch_id, revision)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS network_report_routes (
            report_id TEXT NOT NULL REFERENCES network_reports(report_id),
            ordinal INTEGER NOT NULL,
            edge_id TEXT NOT NULL,
            direction TEXT NOT NULL CHECK (direction IN ('forward', 'reverse')),
            PRIMARY KEY (report_id, ordinal)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS network_report_contributions (
            report_id TEXT NOT NULL REFERENCES network_reports(report_id),
            ordinal INTEGER NOT NULL,
            start_s TEXT NOT NULL,
            end_s TEXT NOT NULL,
            sample_start_s TEXT NOT NULL,
            sample_start_reading TEXT NOT NULL,
            sample_end_s TEXT NOT NULL,
            sample_end_reading TEXT NOT NULL,
            integral TEXT NOT NULL,
            PRIMARY KEY (report_id, ordinal)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS network_report_steps (
            report_id TEXT NOT NULL,
            contribution_ordinal INTEGER NOT NULL,
            step_ordinal INTEGER NOT NULL,
            edge_id TEXT NOT NULL,
            direction TEXT NOT NULL CHECK (direction IN ('forward', 'reverse')),
            segment_index INTEGER NOT NULL CHECK (segment_index >= 0),
            knot_start_x TEXT NOT NULL,
            knot_start_y TEXT NOT NULL,
            knot_end_x TEXT NOT NULL,
            knot_end_y TEXT NOT NULL,
            PRIMARY KEY (report_id, contribution_ordinal, step_ordinal),
            FOREIGN KEY (report_id, contribution_ordinal)
                REFERENCES network_report_contributions(report_id, ordinal)
        )
    ''')
    connection.execute(
        'INSERT OR IGNORE INTO report_registry (report_id, kind) '
        "SELECT report_id, 'direct' FROM reports"
    )


def store_network(connection: sqlite3.Connection, network: CalibrationNetwork) -> None:
    connection.execute(
        'INSERT INTO networks (network_id) VALUES (?)', (network.network_id,),
    )
    connection.executemany('''
        INSERT INTO network_edges (network_id, edge_id, ordinal, source, target)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        (network.network_id, edge.edge_id, index, edge.source, edge.target)
        for index, edge in enumerate(network.edges)
    ))
    connection.executemany('''
        INSERT INTO network_edge_knots (network_id, edge_id, ordinal, x, y)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        (network.network_id, edge.edge_id, ordinal, str(x), str(y))
        for edge in network.edges
        for ordinal, (x, y) in enumerate(edge.knots)
    ))


def load_network(connection: sqlite3.Connection, network_id: str) -> CalibrationNetwork | None:
    header = connection.execute(
        'SELECT 1 FROM networks WHERE network_id = ?', (network_id,)
    ).fetchone()
    if header is None:
        return None
    rows = connection.execute('''
        SELECT e.edge_id, e.source, e.target, k.x, k.y
        FROM network_edges e
        JOIN network_edge_knots k
          ON k.network_id = e.network_id AND k.edge_id = e.edge_id
        WHERE e.network_id = ?
        ORDER BY e.ordinal, k.ordinal
    ''', (network_id,))
    edges: list[NetworkEdge] = []
    current_id = None
    knots = []
    source = target = ''
    for edge_id, edge_source, edge_target, x, y in rows:
        if edge_id != current_id:
            if current_id is not None:
                edges.append(NetworkEdge(current_id, source, target, tuple(knots)))
            current_id, source, target, knots = edge_id, edge_source, edge_target, []
        knots.append((Fraction(x), Fraction(y)))
    if current_id is not None:
        edges.append(NetworkEdge(current_id, source, target, tuple(knots)))
    return CalibrationNetwork(network_id, tuple(edges))


def report_kind(connection: sqlite3.Connection, report_id: str) -> str | None:
    row = connection.execute(
        'SELECT kind FROM report_registry WHERE report_id = ?', (report_id,)
    ).fetchone()
    return None if row is None else row[0]
