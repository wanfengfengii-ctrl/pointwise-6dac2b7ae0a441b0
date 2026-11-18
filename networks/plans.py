import sqlite3
from dataclasses import dataclass

from networks.catalog import get_network
from networks.frozen import CalibrationNetwork
from networks.ledger import (
    orient_route,
    route_piecewise,
    split_network_span,
)
from networks.routing import choose_route
from networks.snapshots import (
    NetworkReportSnapshot,
    insert_network_report,
    load_network_report,
)
from networks.storage import report_kind
from observations.revisions import RevisionRef, get_revision
from observations.windows import select_window, validate_window
from processing.contributions import close_ledger
from processing.spans import iter_clipped_spans
from quantities import require_name
from reports.bindings import NetworkBinding
from reports.storage import ReportSnapshot


@dataclass(frozen=True, slots=True)
class NetworkPlan:
    binding: NetworkBinding
    network: CalibrationNetwork
    source: str
    route: tuple
    observations: object


def bind_network_plan(connection: sqlite3.Connection,
                      binding: NetworkBinding) -> NetworkPlan:
    revision = get_revision(connection, binding.revision)
    network = get_network(connection, binding.network_id)
    route = choose_route(network, revision.scale, binding.target)
    return NetworkPlan(
        binding, network, revision.scale, route,
        select_window(revision, binding.window),
    )


def find_network_replay(connection: sqlite3.Connection, report_id: str,
                        binding: NetworkBinding) -> ReportSnapshot | None:
    kind = report_kind(connection, report_id)
    if kind is None:
        return None
    if kind != 'network':
        raise ValueError(f'report {report_id!r} has a different fixed binding')
    existing = load_network_report(connection, report_id)
    if existing.binding != binding:
        raise ValueError(f'report {report_id!r} has a different fixed binding')
    return existing


def build_network_report(connection: sqlite3.Connection, report_id: str,
                         batch_revision: RevisionRef, network_id: str, target: str,
                         window: object) -> NetworkReportSnapshot:
    require_name(report_id, 'report ID')
    require_name(network_id, 'network ID')
    require_name(target, 'target scale')
    if not isinstance(batch_revision, RevisionRef):
        raise ValueError('an explicit RevisionRef is required')
    binding = NetworkBinding(batch_revision, network_id, target, validate_window(window))
    existing = find_network_replay(connection, report_id, binding)
    if existing is not None:
        return existing
    plan = bind_network_plan(connection, binding)
    steps = orient_route(plan.network, plan.route)
    composite = route_piecewise(steps)
    items = (
        item
        for span in iter_clipped_spans(plan.observations)
        for item in split_network_span(span, steps, composite)
    )
    ledger = close_ledger(items, plan.observations.intersection)
    return publish_network_report(connection, report_id, plan, ledger)


def publish_network_report(connection: sqlite3.Connection, report_id: str,
                           plan: NetworkPlan,
                           ledger) -> NetworkReportSnapshot:
    connection.execute('BEGIN IMMEDIATE')
    with connection:
        existing = find_network_replay(connection, report_id, plan.binding)
        if existing is not None:
            return existing
        report = NetworkReportSnapshot(
            report_id, plan.binding, plan.source, ledger.coverage, ledger.total,
            tuple(ledger.contributions), plan.route,
        )
        insert_network_report(connection, report)
        return report
