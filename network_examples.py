from fractions import Fraction as F

A_B = ((0, 0), ("1/2", "1/4"), (1, 1))
B_C = ((0, 0), ("1/2", "3/4"), (1, 1))
B_C_INVERSE = ((0, 0), ("1/4", "1/2"), (1, 1))
IDENTITY = ((0, 0), (1, 1))
UP = ((0, 0), (1, 1))

EDGE_01 = ("e01", "A", "B", A_B)
CASCADE_EDGES = (EDGE_01, ("e02", "B", "C", B_C))
CONFLICT_EDGES = (*CASCADE_EDGES, ("e03", "A", "C", IDENTITY))
CANCEL_EDGES = (EDGE_01, ("e02", "C", "B", A_B))
PARALLEL_EDGES = (("e04", "B", "C", B_C_INVERSE), *CANCEL_EDGES)
CANCEL_ROUTE = (("e01", "forward"), ("e02", "reverse"))

# Each item is (start, end, original segment indices in route order, integral).
CASES = (
    dict(name="cascade", edges=CASCADE_EDGES, source="A", target="C", samples=UP,
         window=(0, 1), route=(("e01", "forward"), ("e02", "forward")),
         items=((F(0), F(1, 2), (0, 0), F(3, 32)),
                (F(1, 2), F(2, 3), (1, 0), F(3, 32)),
                (F(2, 3), F(1), (1, 1), F(7, 24))),
         coverage=F(1), total=F(23, 48)),
    dict(name="cancellation", edges=CANCEL_EDGES, source="A", target="C", samples=UP,
         window=(0, 1), route=CANCEL_ROUTE,
         items=((F(0), F(1, 2), (0, 0), F(1, 8)),
                (F(1, 2), F(1), (1, 1), F(3, 8))), coverage=F(1), total=F(1, 2)),
    dict(name="descending", edges=CANCEL_EDGES, source="A", target="C",
         samples=((0, 1), (4, 0)), window=(1, 3), route=CANCEL_ROUTE,
         items=((F(1), F(2), (1, 1), F(5, 8)),
                (F(2), F(3), (0, 0), F(3, 8))), coverage=F(2), total=F(1)),
    dict(name="constant_at_knot", edges=CANCEL_EDGES, source="A", target="C",
         samples=((0, "1/2"), (1, "1/2")), window=(0, 1), route=CANCEL_ROUTE,
         items=((F(0), F(1), (1, 1), F(1, 2)),), coverage=F(1), total=F(1, 2)),
    dict(name="parallel_reverse", edges=PARALLEL_EDGES, source="C", target="A", samples=UP,
         window=(0, 1), route=(("e02", "forward"), ("e01", "reverse")),
         items=((F(0), F(1, 2), (0, 0), F(1, 8)),
                (F(1, 2), F(1), (1, 1), F(3, 8))), coverage=F(1), total=F(1, 2)),
    dict(name="identity", edges=CANCEL_EDGES, source="A", target="A", samples=UP,
         window=(0, 1), route=(), items=((F(0), F(1), (), F(1, 2)),),
         coverage=F(1), total=F(1, 2)),
)
