import sqlite3
from fractions import Fraction

from networks.ledger import NetworkContribution, PathStep
from observations.revisions import RevisionRef
from observations.series import Sample
from reports.bindings import NetworkBinding
from reports.storage import ReportSnapshot


class NetworkReportSnapshot(ReportSnapshot):
    """Published network ledger; binding is a NetworkBinding and contributions carry paths."""

    __slots__ = ('route',)

    def __init__(self, report_id: str, binding: NetworkBinding, source: str,
                 coverage: Fraction, total: Fraction,
                 contributions: tuple[NetworkContribution, ...], route: tuple) -> None:
        super().__init__(report_id, binding, source, coverage, total, contributions)
        object.__setattr__(self, 'route', tuple(route))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NetworkReportSnapshot):
            return NotImplemented
        return (
            self.report_id == other.report_id
            and self.binding == other.binding
            and self.source == other.source
            and self.coverage == other.coverage
            and self.total == other.total
            and self.contributions == other.contributions
            and self.route == other.route
        )

    def __hash__(self) -> int:
        return hash((
            self.report_id, self.binding, self.source, self.coverage, self.total,
            self.contributions, self.route,
        ))


def insert_network_report(connection: sqlite3.Connection,
                          report: NetworkReportSnapshot) -> None:
    binding = report.binding
    connection.execute('''
        INSERT INTO network_reports (
            report_id, batch_id, revision, network_id, source, target,
            window_start, window_end, coverage, total
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        report.report_id, binding.revision.batch_id, binding.revision.number,
        binding.network_id, report.source, binding.target,
        str(binding.window[0]), str(binding.window[1]),
        str(report.coverage), str(report.total),
    ))
    connection.executemany('''
        INSERT INTO network_report_routes (report_id, ordinal, edge_id, direction)
        VALUES (?, ?, ?, ?)
    ''', (
        (report.report_id, index, edge_id, direction)
        for index, (edge_id, direction) in enumerate(report.route)
    ))
    for ordinal, item in enumerate(report.contributions):
        first, last = item.samples
        connection.execute('''
            INSERT INTO network_report_contributions (
                report_id, ordinal, start_s, end_s,
                sample_start_s, sample_start_reading, sample_end_s, sample_end_reading, integral
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            report.report_id, ordinal, str(item.start), str(item.end),
            str(first.time_s), str(first.reading), str(last.time_s), str(last.reading),
            str(item.integral),
        ))
        connection.executemany('''
            INSERT INTO network_report_steps (
                report_id, contribution_ordinal, step_ordinal, edge_id, direction,
                segment_index, knot_start_x, knot_start_y, knot_end_x, knot_end_y
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            (
                report.report_id, ordinal, step_ordinal, step.edge_id, step.direction,
                step.segment_index,
                str(step.knots[0][0]), str(step.knots[0][1]),
                str(step.knots[1][0]), str(step.knots[1][1]),
            )
            for step_ordinal, step in enumerate(item.path)
        ))
    connection.execute(
        'INSERT INTO report_registry (report_id, kind) VALUES (?, ?)',
        (report.report_id, 'network'),
    )


def load_network_report(connection: sqlite3.Connection,
                        report_id: str) -> NetworkReportSnapshot | None:
    header = connection.execute('''
        SELECT batch_id, revision, network_id, source, target, window_start, window_end,
               coverage, total
        FROM network_reports WHERE report_id = ?
    ''', (report_id,)).fetchone()
    if header is None:
        return None
    batch_id, revision, network_id, source, target, start, end, coverage, total = header
    binding = NetworkBinding(
        RevisionRef(batch_id, revision), network_id, target, (int(start), int(end)),
    )
    route = tuple(connection.execute('''
        SELECT edge_id, direction FROM network_report_routes
        WHERE report_id = ? ORDER BY ordinal
    ''', (report_id,)))
    contributions = []
    rows = connection.execute('''
        SELECT ordinal, start_s, end_s, sample_start_s, sample_start_reading,
               sample_end_s, sample_end_reading, integral
        FROM network_report_contributions WHERE report_id = ? ORDER BY ordinal
    ''', (report_id,))
    for ordinal, start_s, end_s, t0, v0, t1, v1, integral in rows:
        samples = (Sample(int(t0), Fraction(v0)), Sample(int(t1), Fraction(v1)))
        path = tuple(
            PathStep(
                edge_id, direction, segment_index,
                ((Fraction(x0), Fraction(y0)), (Fraction(x1), Fraction(y1))),
            )
            for edge_id, direction, segment_index, x0, y0, x1, y1 in connection.execute('''
                SELECT edge_id, direction, segment_index, knot_start_x, knot_start_y,
                       knot_end_x, knot_end_y
                FROM network_report_steps
                WHERE report_id = ? AND contribution_ordinal = ?
                ORDER BY step_ordinal
            ''', (report_id, ordinal))
        )
        contributions.append(NetworkContribution(
            Fraction(start_s), Fraction(end_s), samples, path, Fraction(integral),
        ))
    return NetworkReportSnapshot(
        report_id, binding, source, Fraction(coverage), Fraction(total),
        tuple(contributions), route,
    )
