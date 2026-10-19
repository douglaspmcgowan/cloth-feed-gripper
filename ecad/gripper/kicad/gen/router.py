"""Two-layer grid router used by gen_pcb.py (pure geometry, no KiCad imports).

Coordinates are board-local millimetres with the origin at the board's top-left corner. The grid
pitch is 0.127 mm (2.54 mm / 20), so a track can run exactly midway between two 2.54 mm header pads.

Clearance is checked against exact distances, not a dilated raster. For each layer the grid keeps,
per cell centre, d1 (distance to the nearest copper), n1 (the net that copper is on) and d2 (distance
to the nearest copper of any net other than n1). The distance from a cell to the nearest copper of a
net other than N is then d2 where n1 == N, else d1. A track of width w on net N may put its centre
on a cell when that distance is at least w/2 + clearance + EPS; EPS covers the dip a straight segment
between two legal cell centres can make towards a corner (0.052 mm worst case on a diagonal step).
"""
import heapq
import math

import numpy as np

G = 0.127          # grid pitch, mm
CLR = 0.2          # copper-to-copper clearance the router keeps, mm
EPS = 0.06         # see module docstring
EDGE = 0.55        # copper to board edge, mm
VIA_D = 0.8        # via pad diameter, mm
VIA_DRILL = 0.4    # via drill, mm
HOLE_GAP = 0.55    # drill edge to drill edge, mm
REACH = 2.2        # how far a shape's distance is written into the grid, mm
FAR = 99.0


class Grid:
    def __init__(self, w_mm, h_mm):
        self.w, self.h = w_mm, h_mm
        self.nx = int(round(w_mm / G)) + 1
        self.ny = int(round(h_mm / G)) + 1
        self.n = self.nx * self.ny
        shape = (2, self.ny, self.nx)
        self.d1 = np.full(shape, FAR, np.float32)
        self.n1 = np.zeros(shape, np.int32)
        self.d2 = np.full(shape, FAR, np.float32)
        self.hard = np.zeros(shape, bool)                       # no copper at all (rule areas)
        self.dh = np.full((self.ny, self.nx), FAR, np.float32)  # distance to nearest drill edge
        self.dsmd = np.full((self.ny, self.nx), FAR, np.float32)  # distance to nearest SMD pad copper
        xs = np.arange(self.nx, dtype=np.float32) * G
        ys = np.arange(self.ny, dtype=np.float32) * G
        self.X, self.Y = np.meshgrid(xs, ys)
        self.de = np.minimum(np.minimum(self.X, w_mm - self.X), np.minimum(self.Y, h_mm - self.Y))
        self.tracks = []   # (net, layer, x1, y1, x2, y2, width)
        self.vias = []     # (net, x, y)

    # ---- shapes: ('rect', cx, cy, hx, hy) | ('circle', cx, cy, r) | ('seg', x1, y1, x2, y2, hw)
    def _window(self, shape, reach):
        k = shape[0]
        if k == 'rect':
            x0, x1, y0, y1 = shape[1] - shape[3], shape[1] + shape[3], shape[2] - shape[4], shape[2] + shape[4]
        elif k == 'circle':
            x0, x1, y0, y1 = shape[1] - shape[3], shape[1] + shape[3], shape[2] - shape[3], shape[2] + shape[3]
        else:
            hw = shape[5]
            x0, x1 = min(shape[1], shape[3]) - hw, max(shape[1], shape[3]) + hw
            y0, y1 = min(shape[2], shape[4]) - hw, max(shape[2], shape[4]) + hw
        ix0 = max(0, int(math.floor((x0 - reach) / G)))
        ix1 = min(self.nx, int(math.ceil((x1 + reach) / G)) + 1)
        iy0 = max(0, int(math.floor((y0 - reach) / G)))
        iy1 = min(self.ny, int(math.ceil((y1 + reach) / G)) + 1)
        return (slice(iy0, iy1), slice(ix0, ix1))

    def _dist(self, shape, sl):
        X, Y = self.X[sl], self.Y[sl]
        k = shape[0]
        if k == 'rect':
            dx = np.maximum(np.abs(X - shape[1]) - shape[3], 0)
            dy = np.maximum(np.abs(Y - shape[2]) - shape[4], 0)
            return np.hypot(dx, dy)
        if k == 'circle':
            return np.maximum(np.hypot(X - shape[1], Y - shape[2]) - shape[3], 0)
        x1, y1, x2, y2, hw = shape[1:]
        vx, vy = x2 - x1, y2 - y1
        L2 = vx * vx + vy * vy
        if L2 == 0:
            return np.maximum(np.hypot(X - x1, Y - y1) - hw, 0)
        t = np.clip(((X - x1) * vx + (Y - y1) * vy) / L2, 0, 1)
        return np.maximum(np.hypot(X - (x1 + t * vx), Y - (y1 + t * vy)) - hw, 0)

    def add_copper(self, layers, net, shape):
        sl = self._window(shape, REACH)
        ds = self._dist(shape, sl).astype(np.float32)
        for L in layers:
            d1, n1, d2 = self.d1[L][sl], self.n1[L][sl], self.d2[L][sl]
            same = n1 == net
            closer = ds < d1
            m = same & closer
            d1[m] = ds[m]
            m = (~same) & closer
            d2[m] = d1[m]
            d1[m] = ds[m]
            n1[m] = net
            m = (~same) & (~closer) & (ds < d2)
            d2[m] = ds[m]

    def add_hole(self, x, y, r):
        shape = ('circle', x, y, r)
        sl = self._window(shape, REACH)
        self.dh[sl] = np.minimum(self.dh[sl], self._dist(shape, sl))

    def add_smd(self, shape):
        sl = self._window(shape, REACH)
        self.dsmd[sl] = np.minimum(self.dsmd[sl], self._dist(shape, sl))

    def add_keepout(self, layers, x0, y0, x1, y1, margin=0.6):
        """No track centre or via centre within `margin` of the rectangle (covers half a via pad)."""
        sl = self._window(('rect', (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2), margin)
        for L in layers:
            self.hard[L][sl] = True

    def dist_other(self, L, net):
        return np.where(self.n1[L] == net, self.d2[L], self.d1[L])

    def cells_in(self, shape, shrink):
        """Flat cell indices whose centres lie inside the shape shrunk by `shrink` (>= 1 cell)."""
        k = shape[0]
        if k == 'rect':
            s = ('rect', shape[1], shape[2], max(shape[3] - shrink, 0.0), max(shape[4] - shrink, 0.0))
        else:
            s = ('circle', shape[1], shape[2], max(shape[3] - shrink, 0.0))
        sl = self._window(s, G)
        d = self._dist(s, sl)
        iy, ix = np.nonzero(d <= 1e-6)
        if len(iy) == 0:
            j = int(np.argmin(d))
            iy, ix = np.array([j // d.shape[1]]), np.array([j % d.shape[1]])
        return ((iy + sl[0].start) * self.nx + (ix + sl[1].start)).tolist()

    def xy(self, cell):
        return (cell % self.nx) * G, (cell // self.nx) * G

    # ---- legality masks for one net
    def masks(self, net, width, own_pad_shapes=None, neck=None, neck_reach=2.5):
        """Returns (legal[2] bytes, wide[2] bytes or None, via_ok bytes)."""
        do = [self.dist_other(L, net) for L in (0, 1)]

        def ok(L, w):
            return (do[L] >= w / 2 + CLR + EPS) & (~self.hard[L]) & (self.de >= w / 2 + EDGE)

        wide = None
        if neck is None:
            legal = [ok(L, width) for L in (0, 1)]
        else:
            near = np.full((self.ny, self.nx), FAR, np.float32)
            for s in own_pad_shapes:
                sl = self._window(s, neck_reach + G)
                near[sl] = np.minimum(near[sl], self._dist(s, sl))
            wide = [ok(L, width) for L in (0, 1)]
            legal = [wide[L] | (ok(L, neck) & (near <= neck_reach)) for L in (0, 1)]
        need = VIA_D / 2 + CLR + EPS
        via_ok = ((do[0] >= need) & (do[1] >= need) & (~self.hard[0]) & (~self.hard[1])
                  & (self.de >= VIA_D / 2 + EDGE) & (self.dh >= VIA_DRILL / 2 + HOLE_GAP)
                  & (self.dsmd >= VIA_D / 2 + 0.15))
        if wide is not None:
            via_ok = via_ok & wide[0] & wide[1]
        else:
            via_ok = via_ok & legal[0] & legal[1]
        return ([m.tobytes() for m in legal], None if wide is None else [m.tobytes() for m in wide], via_ok.tobytes())

    # ---- search
    def search(self, starts, is_target, legal, via_ok, anchor, bottom_cost=1.8, via_cost=40.0, hweight=1.3,
               limit=3000000, layers=(0, 1)):
        """A* from start nodes (layer * n + cell) to the first node where is_target[node] is set."""
        nx, n = self.nx, self.n
        moves = ((1, 1.0), (-1, 1.0), (nx, 1.0), (-nx, 1.0),
                 (nx + 1, 1.4142), (nx - 1, 1.4142), (-nx + 1, 1.4142), (-nx - 1, 1.4142))
        lcost = (1.0, bottom_cost)
        ax, ay = (None, None) if anchor is None else (int(round(anchor[0] / G)), int(round(anchor[1] / G)))
        best = {}
        prev = {}
        heap = []
        for s in starts:
            best[s] = 0.0
            heapq.heappush(heap, (0.0, s))
        pops = 0
        while heap:
            f, node = heapq.heappop(heap)
            g = best[node]
            if is_target[node]:
                path = [node]
                while node in prev:
                    node = prev[node]
                    path.append(node)
                return path[::-1]
            pops += 1
            if pops > limit:
                return None
            L, cell = divmod(node, n)
            lg = legal[L]
            lc = lcost[L]
            cx = cell % nx
            for dc, c in moves:
                nc = cell + dc
                if nc < 0 or nc >= n:
                    continue
                ncx = nc % nx
                if abs(ncx - cx) > 1:
                    continue
                nn = L * n + nc
                if not lg[nc] and not is_target[nn]:
                    continue
                ng = g + c * lc
                if ng < best.get(nn, 1e18):
                    best[nn] = ng
                    prev[nn] = node
                    if ax is None:
                        h = 0.0
                    else:
                        dx, dy = abs(ncx - ax), abs(nc // nx - ay)
                        h = (max(dx, dy) + 0.4142 * min(dx, dy)) * hweight
                    heapq.heappush(heap, (ng + h, nn))
            if via_ok[cell] and len(layers) == 2:
                nn = (1 - L) * n + cell
                ng = g + via_cost
                if ng < best.get(nn, 1e18):
                    best[nn] = ng
                    prev[nn] = node
                    if ax is None:
                        h = 0.0
                    else:
                        dx, dy = abs(cx - ax), abs(cell // nx - ay)
                        h = (max(dx, dy) + 0.4142 * min(dx, dy)) * hweight
                    heapq.heappush(heap, (ng + h, nn))
        return None

    def commit(self, net, path, width, wide=None, neck=None):
        """Turn a node path into track segments and vias, add them to the grid, return path cells."""
        n = self.n
        segs = []
        cur = None   # [layer, start_cell, last_cell, direction, width]
        for a, b in zip(path, path[1:]):
            La, ca = divmod(a, n)
            Lb, cb = divmod(b, n)
            if La != Lb:
                if cur:
                    segs.append(cur)
                    cur = None
                x, y = self.xy(ca)
                self.vias.append((net, x, y))
                self.add_copper((0, 1), net, ('circle', x, y, VIA_D / 2))
                self.add_hole(x, y, VIA_DRILL / 2)
                continue
            w = width
            if wide is not None and not (wide[La][ca] and wide[La][cb]):
                w = neck
            d = cb - ca
            if cur and cur[0] == La and cur[3] == d and cur[4] == w and cur[2] == ca:
                cur[2] = cb
            else:
                if cur:
                    segs.append(cur)
                cur = [La, ca, cb, d, w]
        if cur:
            segs.append(cur)
        for L, c0, c1, d, w in segs:
            x1, y1 = self.xy(c0)
            x2, y2 = self.xy(c1)
            self.tracks.append((net, L, x1, y1, x2, y2, w))
            self.add_copper((L,), net, ('seg', x1, y1, x2, y2, w / 2))
        return path

    def add_track(self, net, L, x1, y1, x2, y2, w):
        self.tracks.append((net, L, x1, y1, x2, y2, w))
        self.add_copper((L,), net, ('seg', x1, y1, x2, y2, w / 2))
