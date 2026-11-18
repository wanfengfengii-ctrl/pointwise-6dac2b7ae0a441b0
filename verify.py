import sys
import unittest
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def verify_network_chains() -> None:
    from archive import Archive
    from network_examples import CASES
    from review.network_audit import audit_network_json

    for case in CASES:
        with Archive() as archive:
            archive.register_network('net', case['edges'])
            revision = archive.put_batch('day', case['source'], case['samples'])
            report = archive.build_network_report(
                'sheet', revision, 'net', case['target'], case['window'],
            )
            actual = tuple(
                (item.start, item.end,
                 tuple(step.segment_index for step in item.path), item.integral)
                for item in report.contributions
            )
            expected = (case['route'], case['items'], case['coverage'], case['total'])
            if (report.route, actual, report.coverage, report.total) != expected:
                raise AssertionError(f"network case {case['name']} does not match hand figures")
            if archive.read_report('sheet') != report:
                raise AssertionError(f"network case {case['name']} replay changed the snapshot")
            audit = audit_network_json(archive.export_report('sheet'))
            if (audit['coverage'], audit['total']) != (case['coverage'], case['total']):
                raise AssertionError(f"network case {case['name']} failed the independent audit")
            if not all(isinstance(value, Fraction) for value in audit['integrals']):
                raise AssertionError(f"network case {case['name']} lost exact rational arithmetic")


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.testsRun:
        print('No regression tests discovered', file=sys.stderr)
        return 1
    if not result.wasSuccessful():
        return 1
    verify_network_chains()
    print('Network hand figures and independent audits reconciled:', 'OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
