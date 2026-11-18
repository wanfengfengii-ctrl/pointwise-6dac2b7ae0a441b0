import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from fractions import Fraction as F
from pathlib import Path

from archive import Archive, RevisionRef
from network_examples import (
    CANCEL_EDGES,
    CASCADE_EDGES,
    CONFLICT_EDGES,
    PARALLEL_EDGES,
    CASES,
)
from review.network_audit import audit_network_export


class NetworkRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.archive = Archive()
        self.addCleanup(self.archive.close)

    def test_hand_computed_cases(self):
        for case in CASES:
            with self.subTest(case=case['name']):
                with Archive() as archive:
                    self.assertEqual(archive.register_network('net', case['edges']), 'net')
                    revision = archive.put_batch('day', case['source'], case['samples'])
                    report = archive.build_network_report(
                        'sheet', revision, 'net', case['target'], case['window'],
                    )
                    actual = tuple(
                        (item.start, item.end,
                         tuple(step.segment_index for step in item.path), item.integral)
                        for item in report.contributions
                    )
                    self.assertEqual(
                        (report.route, actual, report.coverage, report.total),
                        (case['route'], case['items'], case['coverage'], case['total']),
                    )
                    self.assertEqual(archive.read_report('sheet'), report)

    def test_replay_same_content_any_order_conflicts_rejected(self):
        self.assertEqual(self.archive.register_network('net', CASCADE_EDGES), 'net')
        reordered = tuple(reversed(CASCADE_EDGES))
        self.assertEqual(self.archive.register_network('net', reordered), 'net')
        with self.assertRaises(ValueError):
            self.archive.register_network('net', CONFLICT_EDGES)
        with self.assertRaises(ValueError):
            self.archive.register_network('net', CANCEL_EDGES)
        network = self.archive.get_network('net')
        self.assertEqual([edge.edge_id for edge in network.edges], ['e01', 'e02'])

    def test_conflicting_network_fully_rejected_then_id_reusable(self):
        with self.assertRaises(ValueError):
            self.archive.register_network('net', CONFLICT_EDGES)
        with self.assertRaises(KeyError):
            self.archive.get_network('net')
        self.assertEqual(self.archive.register_network('net', CASCADE_EDGES), 'net')

    def test_invalid_edge_payloads(self):
        bad_payloads = (
            [('e1', 'A', 'B')],
            [('e1', 'A', 'A', [(0, 0), (1, 1)])],
            [('e1', 'A', 'B', [(0, 0), ('1/2', '1/2')])],
            [('e1', 'A', 'B', [(0, 0), ('1/2', 0), (1, 1)])],
            [('  ', 'A', 'B', [(0, 0), (1, 1)])],
            [('e1', '', 'B', [(0, 0), (1, 1)])],
        )
        for payload in bad_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.archive.register_network('bad', payload)
        with self.assertRaises(ValueError):
            self.archive.register_network(
                'dup', [('e', 'A', 'B', [(0, 0), (1, 1)]),
                        ('e', 'B', 'C', [(0, 0), (1, 1)])],
            )

    def test_parallel_edges_and_disconnected_components(self):
        self.archive.register_network('par', PARALLEL_EDGES)
        revision = self.archive.put_batch('day', 'C', [(0, 0), (1, 1)])
        report = self.archive.build_network_report('sheet', revision, 'par', 'A', (0, 1))
        self.assertEqual(report.route, (('e02', 'forward'), ('e01', 'reverse')))
        self.assertEqual(report.total, F(1, 2))

    def test_empty_network_and_container_modification(self):
        self.assertEqual(self.archive.register_network('empty', []), 'empty')
        edges = [list(edge) for edge in CASCADE_EDGES]
        self.archive.register_network('net', edges)
        edges[0][0] = 'tampered'
        network = self.archive.get_network('net')
        self.assertEqual([edge.edge_id for edge in network.edges], ['e01', 'e02'])
        self.assertEqual(self.archive.register_network('net', CASCADE_EDGES), 'net')
        with self.assertRaises(ValueError):
            self.archive.build_network_report(
                'x', self.archive.put_batch('b', 'A', [(0, 0), (1, 1)]),
                'empty', 'C', (0, 1),
            )

    def test_lexicographic_route_tie_break(self):
        identity = [(0, 0), (1, 1)]
        # Two equal-length routes S->M->T; lexicographically smallest edge sequence wins.
        self.archive.register_network('diamond', [
            ('a', 'S', 'M', identity), ('z', 'S', 'M', identity),
            ('b', 'M', 'T', identity), ('y', 'M', 'T', identity),
        ])
        revision = self.archive.put_batch('day', 'S', [(0, 0), (1, 1)])
        report = self.archive.build_network_report('d', revision, 'diamond', 'T', (0, 1))
        self.assertEqual(report.route, (('a', 'forward'), ('b', 'forward')))
        # Edge id dominates direction; 'aa' reverse beats 'bb' forward.
        self.archive.register_network('ordered', [
            ('aa', 'X', 'B', identity), ('bb', 'B', 'X', identity),
        ])
        other = self.archive.put_batch('other', 'B', [(0, 0), (1, 1)])
        routed = self.archive.build_network_report('o', other, 'ordered', 'X', (0, 1))
        self.assertEqual(routed.route, (('aa', 'reverse'),))
        from networks.routing import _route_key
        self.assertLess(_route_key((('e', 'forward'),)), _route_key((('e', 'reverse'),)))

    def test_loop_must_be_identity_over_full_range(self):
        forward = [(0, 0), ('1/3', '1/2'), ('2/3', '3/4'), (1, 1)]
        inverse = [(y, x) for x, y in forward]
        self.archive.register_network(
            'loop', [('ab', 'A', 'B', forward), ('ba', 'B', 'A', inverse)],
        )
        revision = self.archive.put_batch('day', 'A', [(0, 0), (2, 1)])
        report = self.archive.build_network_report('loop-sheet', revision, 'loop', 'A', (0, 2))
        self.assertEqual(report.route, ())
        self.assertEqual(report.total, 1)
        with self.assertRaises(ValueError):
            self.archive.register_network('broken', [
                ('ab', 'A', 'B', [(0, 0), ('1/2', '1/3'), (1, 1)]),
                ('ba', 'B', 'A', [(0, 0), ('1/2', '2/3'), (1, 1)]),
            ])


class NetworkReportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'meter.sqlite'

    def test_route_selection_and_empty_route(self):
        with Archive(self.path) as archive:
            archive.register_network('net', CASCADE_EDGES)
            revision = archive.put_batch('day', 'A', [(0, 0), (1, 1)])
            report = archive.build_network_report('c', revision, 'net', 'C', (0, 1))
            self.assertEqual(report.route, (('e01', 'forward'), ('e02', 'forward')))
            same = archive.build_network_report('s', revision, 'net', 'A', (0, 1))
            self.assertEqual(same.route, ())
            self.assertEqual([item.path for item in same.contributions], [()])
            self.assertEqual(same.total, F(1, 2))

    def test_unreachable_and_missing_references(self):
        with Archive(self.path) as archive:
            archive.register_network('net', CASCADE_EDGES)
            revision = archive.put_batch('day', 'A', [(0, 0), (1, 1)])
            with self.assertRaises(KeyError):
                archive.build_network_report('m1', revision, 'missing', 'C', (0, 1))
            with self.assertRaises(KeyError):
                archive.build_network_report(
                    'm2', RevisionRef('day', 9), 'net', 'C', (0, 1),
                )
            archive.register_network('iso', [('z', 'P', 'Q', [(0, 0), (1, 1)])])
            with self.assertRaises(ValueError):
                archive.build_network_report('m3', revision, 'iso', 'Q', (0, 1))
            for report_id in ('m1', 'm2', 'm3'):
                with self.assertRaises(KeyError):
                    archive.read_report(report_id)

    def test_cancellation_path_keeps_original_segments(self):
        with Archive(self.path) as archive:
            archive.register_network('net', CANCEL_EDGES)
            revision = archive.put_batch('day', 'A', [(0, 0), (1, 1)])
            report = archive.build_network_report('sheet', revision, 'net', 'C', (0, 1))
            first, second = report.contributions
            self.assertEqual(
                [(step.edge_id, step.direction, step.segment_index) for step in first.path],
                [('e01', 'forward', 0), ('e02', 'reverse', 0)],
            )
            for step in first.path:
                self.assertEqual(step.knots, ((0, 0), (F(1, 2), F(1, 4))))
            self.assertEqual(
                [(step.edge_id, step.segment_index) for step in second.path],
                [('e01', 1), ('e02', 1)],
            )
            self.assertEqual((first.integral, second.integral), (F(1, 8), F(3, 8)))

    def test_binding_replay_and_cross_kind_conflict(self):
        with Archive(self.path) as archive:
            archive.register_network('net', CASCADE_EDGES)
            archive.register_curve('probe', 'A', 'B', [(0, 0), ('1/2', '1/4'), (1, 1)])
            old = archive.put_batch('day', 'A', [(0, 0), (1, 1)])
            new = archive.put_batch('day', 'A', [(0, 0), (1, 0)])
            request = ('sheet', old, 'net', 'C', (0, 1))
            report = archive.build_network_report(*request)
            for changed in (
                (new, 'net', 'C', (0, 1)),
                (old, 'net', 'C', (0, 0)),
                (old, 'net', 'A', (0, 1)),
            ):
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    archive.build_network_report('sheet', *changed)
            self.assertEqual(archive.build_network_report(*request), report)
            with self.assertRaises(ValueError):
                archive.build_report('sheet', old, 'probe', 'B', (0, 1))
            archive.build_report('direct', old, 'probe', 'B', (0, 1))
            with self.assertRaises(ValueError):
                archive.build_network_report('direct', old, 'net', 'C', (0, 1))

    def test_persisted_snapshot_survives_reopen_and_correction(self):
        with Archive(self.path) as archive:
            archive.register_network('net', CANCEL_EDGES)
            old = archive.put_batch('day', 'A', [(0, 0), (1, 1)])
            original = archive.build_network_report('old', old, 'net', 'C', (0, 1))
            original_json = archive.export_report('old')
            new = archive.put_batch('day', 'A', [(0, 0), (1, 0)])
            corrected = archive.build_network_report('new', new, 'net', 'C', (0, 1))
        with Archive(self.path) as archive:
            archive.initialize()
            self.assertEqual(archive.read_report('old'), original)
            self.assertEqual(archive.export_report('old'), original_json)
            self.assertEqual(archive.read_report('old').total, F(1, 2))
            self.assertEqual(archive.read_report('new').total, 0)
            self.assertEqual(archive.read_report('new'), corrected)

    def test_write_failure_rolls_back_network_report(self):
        with Archive(self.path) as archive:
            archive.register_network('net', CASCADE_EDGES)
            revision = archive.put_batch('day', 'A', [(0, 0), (1, 1)])
            with closing(sqlite3.connect(self.path)) as connection, connection:
                connection.execute('''
                    CREATE TRIGGER stop_route BEFORE INSERT ON network_report_routes
                    WHEN NEW.report_id = 'sheet'
                    BEGIN
                        SELECT RAISE(ABORT, 'route rejected');
                    END
                ''')
            with self.assertRaisesRegex(sqlite3.IntegrityError, 'route rejected'):
                archive.build_network_report('sheet', revision, 'net', 'C', (0, 1))
            with self.assertRaises(KeyError):
                archive.read_report('sheet')
        with Archive(self.path) as archive:
            with self.assertRaises(KeyError):
                archive.read_report('sheet')

    def test_empty_window_keeps_route_context(self):
        with Archive(self.path) as archive:
            archive.register_network('net', CASCADE_EDGES)
            revision = archive.put_batch('day', 'A', [(0, 0), (1, 1)])
            for window in ((0, 0), (4, 5), (-1, 0)):
                report = archive.build_network_report(
                    f'empty-{window[0]}', revision, 'net', 'C', window,
                )
                self.assertEqual((report.coverage, report.total, report.contributions), (0, 0, ()))
                self.assertEqual(report.route, (('e01', 'forward'), ('e02', 'forward')))


class NetworkExportTests(unittest.TestCase):
    def setUp(self):
        self.archive = Archive()
        self.addCleanup(self.archive.close)
        self.archive.register_network('net', CANCEL_EDGES)
        self.revision = self.archive.put_batch('day', 'A', [(0, 0), (1, 1)])

    def test_v2_export_shape_and_independent_audit(self):
        report = self.archive.build_network_report('sheet', self.revision, 'net', 'C', (0, 1))
        payload = json.loads(self.archive.export_report('sheet'))
        self.assertEqual(payload['format_version'], 2)
        self.assertEqual(payload['route'], [['e01', 'forward'], ['e02', 'reverse']])
        self.assertEqual(set(payload['binding']),
                         {'batch_id', 'revision', 'network_id', 'source', 'target', 'window'})
        self.assertNotIn('curve_id', payload['binding'])
        item = payload['contributions'][0]
        self.assertEqual(set(item), {'start_s', 'end_s', 'samples', 'path', 'integral'})
        self.assertEqual(set(item['path'][0]),
                         {'edge_id', 'direction', 'segment_index', 'knots'})
        result = audit_network_export(payload)
        self.assertEqual((result['coverage'], result['total']), (report.coverage, report.total))

    def test_empty_route_export_matches_worked_example(self):
        report = self.archive.build_network_report('same', self.revision, 'net', 'A', (0, 1))
        payload = json.loads(self.archive.export_report('same'))
        self.assertEqual(payload['route'], [])
        self.assertEqual(payload['contributions'][0]['path'], [])
        audit_network_export(payload)
        self.assertEqual((payload['coverage'], payload['total']), ([1, 1], [1, 2]))

    def test_assessment_works_for_network_reports(self):
        self.archive.build_network_report('sheet', self.revision, 'net', 'C', (0, 1))
        assessment = self.archive.assess_report('sheet', 1, '1/2', '1/2')
        self.assertTrue(assessment.passed)
        failed = self.archive.assess_report('sheet', 2, 0, 1)
        self.assertEqual([finding.code for finding in failed.findings], ['coverage_insufficient'])

    def test_direct_export_stays_version_one(self):
        self.archive.register_curve('probe', 'A', 'B', [(0, 0), ('1/2', '1/4'), (1, 1)])
        direct = self.archive.build_report('d', self.revision, 'probe', 'B', (0, 1))
        payload = json.loads(self.archive.export_report('d'))
        self.assertEqual(payload['format_version'], 1)
        self.assertIn('curve_id', payload['binding'])
        self.assertEqual(direct.contributions[0].curve_id, 'probe')


if __name__ == '__main__':
    unittest.main()
