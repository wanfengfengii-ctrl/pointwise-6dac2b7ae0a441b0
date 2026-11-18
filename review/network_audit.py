"""Independent off-library re-audit of network report exports.

Everything here is recomputed from the exported JSON alone: the original sample
pairs, the requested window and each contribution's ordered original-segment
path. No processing or calibration module is imported, so this can run against a
delivery file outside the archive.
"""

import json
from fractions import Fraction


def _ratio(pair) -> Fraction:
    return Fraction(pair[0], pair[1])


def _segment_heights(step):
    (x0, y0), (x1, y1) = (
        (_ratio(coordinate) for coordinate in knot) for knot in step['knots']
    )
    if step['direction'] == 'reverse':
        x0, y0, x1, y1 = y0, x0, y1, x1
    return x0, x1, y0, y1


def _apply_step(step, value):
    x0, x1, y0, y1 = _segment_heights(step)
    relative = (value - x0) / (x1 - x0)
    return y0 + relative * (y1 - y0)


def _reading_at(samples, time_s):
    first, last = samples
    t0 = Fraction(first['time_s'])
    t1 = Fraction(last['time_s'])
    v0 = _ratio(first['reading'])
    v1 = _ratio(last['reading'])
    return v0 + (v1 - v0) * (time_s - t0) / (t1 - t0)


def audit_network_export(payload) -> dict:
    """Recompute coverage, total and every integral from a decoded V2 payload."""
    if payload['format_version'] != 2:
        raise ValueError('network audit expects a format_version 2 export')
    coverage = Fraction(0)
    total = Fraction(0)
    cursor = None
    audited = []
    for item in payload['contributions']:
        start = _ratio(item['start_s'])
        end = _ratio(item['end_s'])
        if not start < end:
            raise ValueError('contribution must have positive duration')
        if cursor is not None and start != cursor:
            raise ValueError('contributions must be adjacent and time ordered')
        cursor = end
        samples = item['samples']
        start_reading = _reading_at(samples, start)
        end_reading = _reading_at(samples, end)
        start_output = start_reading
        end_output = end_reading
        for step in item['path']:
            start_output = _apply_step(step, start_output)
            end_output = _apply_step(step, end_output)
        integral = (end - start) * (start_output + end_output) / 2
        if integral != _ratio(item['integral']):
            raise ValueError('recomputed integral does not match the export')
        coverage += end - start
        total += integral
        audited.append(integral)
    if coverage != _ratio(payload['coverage']):
        raise ValueError('recomputed coverage does not match the export')
    if total != _ratio(payload['total']):
        raise ValueError('recomputed total does not match the export')
    return {'coverage': coverage, 'total': total, 'integrals': tuple(audited)}


def audit_network_json(exported: str) -> dict:
    return audit_network_export(json.loads(exported))
