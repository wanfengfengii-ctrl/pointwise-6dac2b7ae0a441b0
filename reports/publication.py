import sqlite3

from networks.storage import report_kind
from processing.contributions import ContributionLedger
from reports.bindings import ReportBinding, require_same_binding
from reports.storage import ReportSnapshot, insert_report, load_report


def find_replay(connection: sqlite3.Connection, report_id: str,
                binding: ReportBinding) -> ReportSnapshot | None:
    kind = report_kind(connection, report_id)
    if kind == 'network':
        raise ValueError(f'report {report_id!r} has a different fixed binding')
    existing = load_report(connection, report_id)
    if existing is not None:
        require_same_binding(report_id, existing.binding, binding)
    return existing


def publish_report(connection: sqlite3.Connection, report_id: str, binding: ReportBinding,
                   source: str, ledger: ContributionLedger) -> ReportSnapshot:
    connection.execute('BEGIN IMMEDIATE')
    with connection:
        existing = find_replay(connection, report_id, binding)
        if existing is not None:
            return existing
        report = ReportSnapshot(
            report_id, binding, source, ledger.coverage, ledger.total, ledger.contributions,
        )
        insert_report(connection, report)
        connection.execute(
            'INSERT OR IGNORE INTO report_registry (report_id, kind) VALUES (?, ?)',
            (report_id, 'direct'),
        )
        return report
