import json
import tempfile
from fractions import Fraction
from pathlib import Path

from archive import Archive
from network_examples import CASES
from review.network_audit import audit_network_export


def run_network_demo() -> None:
    case = next(item for item in CASES if item['name'] == 'cancellation')
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'network.sqlite'
        with Archive(path) as archive:
            archive.register_network('net', case['edges'])
            original_ref = archive.put_batch('day', case['source'], case['samples'])
            original = archive.build_network_report(
                'cancellation', original_ref, 'net', case['target'], case['window'],
            )
            correction_ref = archive.put_batch('day', case['source'], [(0, 0), (1, 0)])
            archive.build_network_report(
                'cancellation-corrected', correction_ref, 'net', case['target'], case['window'],
            )
        with Archive(path) as archive:
            reopened = archive.read_report('cancellation')
            exported = archive.export_report('cancellation')
            corrected_export = archive.export_report('cancellation-corrected')
            if reopened != original:
                raise RuntimeError('network snapshot changed after reopening the archive')
            audit = audit_network_export(json.loads(exported))
            if (audit['coverage'], audit['total']) != (reopened.coverage, reopened.total):
                raise RuntimeError('independent network audit does not reconcile')
    ledger = [
        {
            'start_s': str(item.start),
            'end_s': str(item.end),
            'path': [
                {
                    'edge_id': step.edge_id,
                    'direction': step.direction,
                    'segment_index': step.segment_index,
                    'knots': [[str(x), str(y)] for x, y in step.knots],
                }
                for step in item.path
            ],
            'integral': str(item.integral),
        }
        for item in original.contributions
    ]
    print('POINTWISE_NETWORK_SCENARIO ' + json.dumps({
        'case_id': 'cancellation',
        'route': list(original.route),
        'ledger': ledger,
        'coverage': str(original.coverage),
        'total': str(original.total),
        'audit_total': str(audit['total']),
        'reopened_total': str(reopened.total),
        'corrected_total': str(Fraction(*json.loads(corrected_export)['total'])),
    }, separators=(',', ':')))
    print(exported)
    print(corrected_export)


def main() -> None:
    examples = Path(__file__).resolve().parent / 'examples'
    curve = json.loads((examples / 'direct-curve.json').read_text(encoding='utf-8'))
    batch = json.loads((examples / 'tide-batch.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'meter.sqlite'
        with Archive(path) as archive:
            fixed_curve = archive.register_curve(**curve)
            first = archive.put_batch(batch['batch_id'], batch['scale'], batch['initial'])
            old = archive.build_report('morning-original', first, fixed_curve.curve_id,
                                       fixed_curve.target, batch['window'])
            assessment = archive.assess_report(old.report_id, 1, '3/8', '3/8')
            old_export = archive.export_report(old.report_id)
            corrected = archive.put_batch(batch['batch_id'], batch['scale'], batch['corrected'])
            new = archive.build_report('morning-corrected', corrected, fixed_curve.curve_id,
                                       fixed_curve.target, batch['window'])
            new_export = archive.export_report(new.report_id)
        with Archive(path) as archive:
            reopened = archive.read_report(old.report_id)
            reopened_new = archive.read_report(new.report_id)
            delivered = archive.export_report(old.report_id)
            delivered_new = archive.export_report(new.report_id)
            if (reopened, reopened_new, delivered, delivered_new) != (old, new, old_export, new_export):
                raise RuntimeError('delivery changed after reopening the archive')
    expected = {
        'coverage': '1', 'total': '3/8',
        'items': [['0', '1/2', 0, '1/16'], ['1/2', '1', 1, '5/16']],
    }
    actual = {
        'coverage': str(old.coverage), 'total': str(old.total),
        'items': [[str(c.start), str(c.end), c.segment_index, str(c.integral)] for c in old.contributions],
    }
    downstream_expected = {
        'approved': True, 'old_revision': 1, 'new_revision': 2,
        'old_export_total': '3/8', 'new_export_total': '0',
    }
    downstream_actual = {
        'approved': assessment.passed,
        'old_revision': reopened.binding.revision.number,
        'new_revision': reopened_new.binding.revision.number,
        'old_export_total': str(Fraction(*json.loads(delivered)['total'])),
        'new_export_total': str(Fraction(*json.loads(delivered_new)['total'])),
    }
    if actual != expected or downstream_actual != downstream_expected:
        raise RuntimeError('published ledger differs from the hand-computed sample')
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': 'v4',
        'input': {'curve': curve, 'batch': batch},
        'expected': expected,
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': [
            'calibration/catalog.py', 'observations/intake.py', 'processing/intervals.py',
            'processing/integrals.py', 'reports/publication.py', 'review/assessment.py',
            'reports/reader.py', 'reports/export.py',
        ],
        'oracle': 'The two half-second trapezoids have endpoint heights 0, 1/4, 1. The corrected reading is zero throughout.',
    }, separators=(',', ':')))
    print(delivered)
    print(delivered_new)
    run_network_demo()


if __name__ == '__main__':
    main()
