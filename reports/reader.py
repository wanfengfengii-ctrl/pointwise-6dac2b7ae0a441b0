import sqlite3

from networks.snapshots import load_network_report
from networks.storage import report_kind
from quantities import require_name
from reports.storage import ReportSnapshot, load_report


def read_report(connection: sqlite3.Connection, report_id: str) -> ReportSnapshot:
    require_name(report_id, 'report ID')
    kind = report_kind(connection, report_id)
    if kind is None:
        snapshot = load_report(connection, report_id)
        if snapshot is None:
            raise KeyError(report_id)
        return snapshot
    if kind == 'network':
        snapshot = load_network_report(connection, report_id)
        if snapshot is None:
            raise KeyError(report_id)
        return snapshot
    snapshot = load_report(connection, report_id)
    if snapshot is None:
        raise KeyError(report_id)
    return snapshot
