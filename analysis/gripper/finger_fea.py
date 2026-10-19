#!/usr/bin/env python3
"""2D plane-stress FEA of the TPU Fin Ray finger (gmsh + scikit-fem, P2 triangles).

    uv run --with gmsh --with scikit-fem --with meshio --with numpy --with scipy --with matplotlib \
        python analysis/gripper/finger_fea.py [--quick]

Governing inputs: docs/gripper/DESIGN-BASIS.md via the INPUTS block in finger_beam.py
(TPU 95A E 67 X-Y / 56 Z MPa; L 45 mm, tip pad 5 mm above the tip, r_c 65 mm; k window 0.88-1.63 N/mm).
Geometry: cad/gripper/params.json via finger_beam.load_geometry / finger_profile (a port of
cad/gripper/gripper_concept.py).  Finger-A local frame: pad face x = xf, root line y = y0
(clamped to the PLA root plate), tip at (xf, y0 - L).  Plane stress, thickness = finger depth.
Load cases (object at +x pushes the pad toward -x):
  mid   distributed pressure on a 10 mm patch centred at s = L/2
  tip   distributed pressure on the 6 mm tip pad centred at s = L - 5
  point nodal force at s = L/2
Options per DESIGN-BASIS D7: finger A carries a 1.0 mm PLA nail at the tip, finger B a 1.0 mm
PLA FSR backing plate (bonded strips on the pad face, two-material mesh).
Validation: rectangular cantilever vs Timoshenko (P1 and P2, 4 meshes); solid wedge vs the
tapered EB+Timoshenko hand calc; Fin Ray mesh convergence (5 meshes).
Nonlinear: total-Lagrangian St Venant-Kirchhoff, Newton with step bisection and branch-jump
rejection, dead load, 0 -> cap force; Cauchy stress and Green-Lagrange strain reported.
Then the design sweep at L 45 and the jaw kinematic / contact-force sweep.
Outputs: analysis/gripper/results/fea_*.json, finger_motion.json;
         docs/gripper/figures/fea_*.png, finger_motion.png.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.sparse.linalg import splu, spsolve

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import finger_beam as fb  # noqa: E402  (single constants block lives there)

from skfem import (Basis, BilinearForm, ElementTriP1, ElementTriP2, ElementVector,  # noqa: E402
                   FacetBasis, LinearForm, MeshTri, asm)
from skfem.helpers import ddot, sym_grad, trace  # noqa: E402
from skfem.models.elasticity import lame_parameters  # noqa: E402

RESULTS = fb.RESULTS
FIGS = fb.FIGS
TOL = 1e-6


def clean(o):
    """JSON-safe: numpy -> python, NaN/inf -> None (JSON.parse rejects bare NaN)."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return v if math.isfinite(v) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def dump(path, obj, compact=False):
    txt = json.dumps(clean(obj), allow_nan=False, **({"separators": (",", ":")} if compact else {"indent": 1}))
    path.write_text(txt, encoding="utf-8")
    return path.stat().st_size


# ------------------------------------------------------------------ meshing
def _inside(pt, poly):
    x, y = pt
    xs, ys = [q[0] for q in poly], [q[1] for q in poly]
    return min(xs) - 1e-9 <= x <= max(xs) + 1e-9 and min(ys) - 1e-9 <= y <= max(ys) + 1e-9


def gmsh_mesh(outer, holes, h, pla=None):
    """Mesh (outer - holes) U pla rectangles, conforming.  Returns (MeshTri, mat) with
    mat[e] = 0 TPU, 1 PLA."""
    import gmsh
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("finger")
    occ = gmsh.model.occ

    def surf(poly):
        pts = [occ.addPoint(x, y, 0) for x, y in poly]
        n = len(pts)
        ln = [occ.addLine(pts[i], pts[(i + 1) % n]) for i in range(n)]
        return occ.addPlaneSurface([occ.addCurveLoop(ln)])

    s = surf(outer)
    ents = [(2, s)]
    if holes:
        ents, _ = occ.cut([(2, s)], [(2, surf(c)) for c in holes])
    if pla:
        ents, _ = occ.fragment(ents, [(2, surf(q)) for q in pla])
    occ.synchronize()
    gmsh.option.setNumber("Mesh.MeshSizeMax", h)
    gmsh.option.setNumber("Mesh.MeshSizeMin", 0.25 * h)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
    gmsh.option.setNumber("Mesh.Algorithm", 6)
    gmsh.model.mesh.generate(2)
    tags, xyz, _ = gmsh.model.mesh.getNodes()
    tris, mats = [], []
    for d, tag in gmsh.model.getEntities(2):
        com = gmsh.model.occ.getCenterOfMass(2, tag)[:2]
        m = 1 if pla and any(_inside(com, q) for q in pla) else 0
        et, _, en = gmsh.model.mesh.getElements(2, tag)
        if 2 in list(et):
            tt = np.asarray(en[list(et).index(2)], dtype=np.int64).reshape(-1, 3)
            tris.append(tt)
            mats.append(np.full(len(tt), m, dtype=np.int64))
    gmsh.finalize()
    tri = np.vstack(tris)
    mat = np.concatenate(mats)
    idx = {int(t): i for i, t in enumerate(tags)}
    p = np.asarray(xyz).reshape(-1, 3)[:, :2]
    t = np.vectorize(idx.get)(tri)
    used = np.unique(t)
    remap = -np.ones(len(p), dtype=np.int64)
    remap[used] = np.arange(len(used))
    p, t = p[used], remap[t]
    return MeshTri(p.T.copy(), t.T.copy()), mat  # MeshTri sorts vertices per element: winding is fixed at export


def ccw(p, t):
    """t (3, n) reoriented counter-clockwise for p (2, m)."""
    t = t.copy()
    a = (p[0, t[1]] - p[0, t[0]]) * (p[1, t[2]] - p[1, t[0]]) - (p[0, t[2]] - p[0, t[0]]) * (p[1, t[1]] - p[1, t[0]])
    t[1:, a < 0] = t[1:, a < 0][::-1]
    return t


# ------------------------------------------------------------------ linear solver
def plane(E, nu, mode="stress"):
    lam, mu = lame_parameters(E, nu)
    if mode == "stress":
        lam = 2 * lam * mu / (lam + 2 * mu)
    return lam, mu


@BilinearForm
def lin_el(u, v, w):
    eu, ev = sym_grad(u), sym_grad(v)
    return w["lam"] * trace(eu) * trace(ev) + 2 * w["mu"] * ddot(eu, ev)


def wpct(vals, w, q):
    v, ww = vals.ravel(), w.ravel()
    o = np.argsort(v)
    c = np.cumsum(ww[o])
    return float(v[o][min(np.searchsorted(c, q * c[-1]), len(v) - 1)])


def project_p1(ib, qp):
    b1 = ib.with_element(ElementTriP1())
    M = asm(BilinearForm(lambda u, v, w: u * v), b1)
    r = asm(LinearForm(lambda v, w: w["s"] * v), b1, s=qp)
    return spsolve(M.tocsc(), r)


def vm2d(sxx, syy, sxy, szz=None):
    if szz is None:
        return np.sqrt(sxx ** 2 - sxx * syy + syy ** 2 + 3 * sxy ** 2)
    return np.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2) + 3 * sxy ** 2)


def principal_abs(exx, eyy, exy):
    r = np.sqrt((0.5 * (exx - eyy)) ** 2 + exy ** 2)
    return np.maximum(np.abs(0.5 * (exx + eyy) + r), np.abs(0.5 * (exx + eyy) - r))


class Model:
    """One mesh + factorised stiffness; solve several load cases.  mat: 0 TPU (E, nu), 1 PLA."""

    def __init__(self, mesh, E, nu, depth, clamp, order=2, mode="stress", mat=None):
        self.mesh, self.E, self.nu, self.D, self.mode = mesh, E, nu, depth, mode
        self.mat = np.zeros(mesh.t.shape[1], dtype=np.int64) if mat is None else mat
        self.e = ElementVector(ElementTriP2() if order == 2 else ElementTriP1())
        self.ib = Basis(mesh, self.e)
        lt, mt = plane(E, nu, mode)
        lp, mp = plane(fb.INPUTS["PLA"]["E_MPa"], fb.INPUTS["PLA"]["nu"], mode)
        self.lam_e = np.where(self.mat == 1, lp, lt)
        self.mu_e = np.where(self.mat == 1, mp, mt)
        nq = self.ib.dx.shape[1]
        self.lam_q = np.repeat(self.lam_e[:, None], nq, 1)
        self.mu_q = np.repeat(self.mu_e[:, None], nq, 1)
        self.K = asm(lin_el, self.ib, lam=self.lam_q, mu=self.mu_q) * depth
        facets = mesh.facets_satisfying(clamp, boundaries_only=True)
        self.fixed = self.ib.get_dofs(facets).all()
        self.free = self.ib.complement_dofs(self.fixed)
        self.lu = splu(self.K[self.free][:, self.free].tocsc())
        self.tpu = self.mat == 0

    def patch_load(self, sel, F, direction=(-1.0, 0.0)):
        facets = self.mesh.facets_satisfying(sel, boundaries_only=True)
        if len(facets) == 0:
            raise ValueError("empty load patch")
        fbas = FacetBasis(self.mesh, self.e, facets=facets)
        dx, dy = direction
        f = asm(LinearForm(lambda v, w: dx * v.value[0] + dy * v.value[1]), fbas)
        length = float(asm(LinearForm(lambda v, w: v), FacetBasis(self.mesh, ElementTriP1(), facets=facets)).sum())
        return f * F / length, length

    def point_load(self, xy, F, direction=(-1.0, 0.0)):
        f = np.zeros(self.ib.N)
        i = int(np.argmin(np.hypot(self.mesh.p[0] - xy[0], self.mesh.p[1] - xy[1])))
        f[self.ib.nodal_dofs[0, i]] += direction[0] * F
        f[self.ib.nodal_dofs[1, i]] += direction[1] * F
        return f, i

    def solve(self, f):
        u = np.zeros(self.ib.N)
        u[self.free] = self.lu.solve(f[self.free])
        return u

    def vertex_u(self, u):
        return u[self.ib.nodal_dofs[0]], u[self.ib.nodal_dofs[1]]

    def fields(self, u):
        """Small-strain von Mises and max |principal strain| at quadrature points (linear)."""
        g = self.ib.interpolate(u).grad
        exx, eyy, exy = g[0, 0], g[1, 1], 0.5 * (g[0, 1] + g[1, 0])
        lam, mu = self.lam_e[:, None], self.mu_e[:, None]
        tr = exx + eyy
        sxx, syy, sxy = lam * tr + 2 * mu * exx, lam * tr + 2 * mu * eyy, 2 * mu * exy
        vm = vm2d(sxx, syy, sxy) if self.mode == "stress" else vm2d(sxx, syy, sxy, lam * tr)
        return vm, principal_abs(exx, eyy, exy)

    def stats(self, vm, ep):
        dx, m = self.ib.dx, self.tpu
        d = dict(vm_max=float(vm[m].max()), vm_p99=wpct(vm[m], dx[m], 0.99), vm_p995=wpct(vm[m], dx[m], 0.995),
                 strain_max=float(ep[m].max()), strain_p99=wpct(ep[m], dx[m], 0.99))
        if (~m).any():
            d["pla_vm_max"] = float(vm[~m].max())
            d["pla_vm_p99"] = wpct(vm[~m], dx[~m], 0.99)
        return d

    def stress(self, u):
        vm, ep = self.fields(u)
        return self.stats(vm, ep), vm


# ------------------------------------------------------------------ nonlinear (TL, SVK)
def _mul(A, B):
    return np.einsum("ij...,jk...->ik...", A, B)


def _T(A):
    return np.einsum("ij...->ji...", A)


I2 = np.eye(2)[:, :, None, None]


def _kin(w):
    Fd = I2 + w["prev"].grad
    Eg = 0.5 * (_mul(_T(Fd), Fd) - I2)
    S = w["lam"] * (Eg[0, 0] + Eg[1, 1]) * I2 + 2 * w["mu"] * Eg
    return Fd, Eg, S


@LinearForm
def _rint(v, w):
    Fd, _, S = _kin(w)
    return np.einsum("ij...,ij...->...", _mul(Fd, S), v.grad)


@BilinearForm
def _ktan(du, v, w):
    Fd, _, S = _kin(w)
    dE = 0.5 * (_mul(_T(Fd), du.grad) + _mul(_T(du.grad), Fd))
    dS = w["lam"] * (dE[0, 0] + dE[1, 1]) * I2 + 2 * w["mu"] * dE
    return np.einsum("ij...,ij...->...", _mul(du.grad, S) + _mul(Fd, dS), v.grad)


def nl_fields(model, u):
    """Cauchy von Mises sigma = F S F^T / J (J = in-plane det F; plane-stress thickness change
    ignored [A]) and max |principal Green-Lagrange strain| at quadrature points."""
    g = model.ib.interpolate(u).grad
    Fd = I2 + g
    Eg = 0.5 * (_mul(_T(Fd), Fd) - I2)
    S = model.lam_e[:, None] * (Eg[0, 0] + Eg[1, 1]) * I2 + 2 * model.mu_e[:, None] * Eg
    J = Fd[0, 0] * Fd[1, 1] - Fd[0, 1] * Fd[1, 0]
    sig = _mul(_mul(Fd, S), _T(Fd)) / J
    vm = vm2d(sig[0, 0], sig[1, 1], sig[0, 1])
    ep = principal_abs(Eg[0, 0], Eg[1, 1], Eg[0, 1])
    return vm, ep, float(J.min())


def newton(model, fext, u0, tol=1e-9, maxit=30):
    ib, fr = model.ib, model.free
    u = u0.copy()
    kw = dict(lam=model.lam_q, mu=model.mu_q)
    fn = max(np.linalg.norm(fext[fr]), 1e-12)
    for it in range(maxit):
        prev = ib.interpolate(u)
        R = asm(_rint, ib, prev=prev, **kw) * model.D - fext
        Kt = asm(_ktan, ib, prev=prev, **kw) * model.D
        du = np.zeros(ib.N)
        try:
            du[fr] = splu(Kt[fr][:, fr].tocsc()).solve(-R[fr])
        except RuntimeError:
            return False, u, it + 1
        if not np.all(np.isfinite(du)) or np.linalg.norm(du[fr]) > 1e3:
            return False, u, it + 1
        u += du
        if np.linalg.norm(du[fr]) <= tol * max(1.0, np.linalg.norm(u[fr])) or np.linalg.norm(R[fr]) <= 1e-11 * fn:
            return True, u, it + 1
    return False, u, maxit


def nonlinear(model, f_unit, F_max, dF0=0.5, dF_min=0.03, jump=4.0, max_newton=600):
    """Load control with step bisection.  A step is rejected when Newton fails or when it converges
    onto a remote branch (patch-displacement rate > `jump` x the previous accepted step's rate).
    Returns (history, info) with the bracket [last converged, smallest rejected] load."""
    u = np.zeros(model.ib.N)
    F, dF, rate_prev, n_it = 0.0, dF0, float(f_unit @ model.solve(f_unit)), 0
    hist, rejected = [], []
    while F < F_max - 1e-9 and n_it < max_newton:
        Ft = min(F + dF, F_max)
        ok, un, it = newton(model, f_unit * Ft, u)
        n_it += it
        reason = None if ok else "newton"
        if ok:
            rate = (float(f_unit @ un) - float(f_unit @ u)) / (Ft - F)
            if rate > jump * rate_prev:
                ok, reason = False, f"branch jump (rate {rate:.3g} vs {rate_prev:.3g} mm/N)"
        if ok:
            u, F, rate_prev = un, Ft, rate
            hist.append(dict(F_N=F, u=u.copy(), iters=it))
            dF = min(dF * 1.5, dF0)
        else:
            rejected.append(dict(F_N=Ft, reason=reason, patch_disp_mm=float(f_unit @ un)))
            dF /= 2
            if dF < dF_min:
                break
    fail = min([r["F_N"] for r in rejected if r["F_N"] > F], default=None)
    info = dict(last_converged_F_N=F, smallest_rejected_F_N=fail, reached_cap=bool(F >= F_max - 1e-9),
                rejected=rejected, newton_iterations=n_it, controller=f"dF0 {dF0}, bisection to {dF_min} N, jump x{jump}")
    return hist, info


# ------------------------------------------------------------------ finger helpers
def pla_parts(G, option):
    """PLA strips bonded on the pad face (outside, x in [xf, xf + t]); DESIGN-BASIS D7."""
    if option == "nail":
        t, ln = fb.INPUTS["nail"]["thickness_mm"], fb.INPUTS["nail"]["length_mm"]
        s0, s1 = G["L"] - ln, G["L"]
    elif option == "backing":
        t, ln = fb.INPUTS["fsr_backing"]["thickness_mm"], fb.INPUTS["fsr_backing"]["length_mm"]
        s1 = min(G["s_tip"] + ln / 2, G["L"])
        s0 = s1 - ln
    else:
        return None, 0.0, None
    y1, y0 = G["y0"] - s0, G["y0"] - s1
    return [[(G["xf"], y0), (G["xf"] + t, y0), (G["xf"] + t, y1), (G["xf"], y1)]], t, (s0, s1)


def finger_mesh(G, h, solid=False, option=None):
    outer, cells = fb.finger_profile(G)
    pla, _, _ = pla_parts(G, option)
    return gmsh_mesh(outer, [] if solid else cells, h, pla=pla)


def clamp_root(G):
    return lambda x: np.abs(x[1] - G["y0"]) < TOL


def pad_sel(G, s_c, length, x_face=None):
    xf = G["xf"] if x_face is None else x_face
    y_hi, y_lo = G["y0"] - (s_c - length / 2), G["y0"] - (s_c + length / 2)
    return lambda x: (np.abs(x[0] - xf) < TOL) & (x[1] <= y_hi + TOL) & (x[1] >= y_lo - TOL)


def tip_index(G, mesh):
    return int(np.argmin(np.hypot(mesh.p[0] - G["xf"], mesh.p[1] - (G["y0"] - G["L"]))))


def run_cases(G, h, E, nu, mode="stress", order=2, fields=False, solid=False, option=None, point=True):
    C = fb.INPUTS["contact"]
    mesh, mat = finger_mesh(G, h, solid=solid, option=option)
    M = Model(mesh, E, nu, G["D"], clamp_root(G), order=order, mode=mode, mat=mat)
    it = tip_index(G, mesh)
    _, tpla, span = pla_parts(G, option)
    dx = M.ib.dx
    area = float(dx.sum())
    area_pla = float(dx[mat == 1].sum()) if (mat == 1).any() else 0.0
    out = {"n_vertices": int(mesh.p.shape[1]), "n_elements": int(mesh.t.shape[1]), "dofs": int(M.ib.N),
           "area_mm2": area - area_pla, "area_pla_mm2": area_pla, "option": option,
           "mass_g": ((area - area_pla) * G["rho_tpu"] + area_pla * G["rho_pla"]) * G["D"] / 1000}
    keep = {}
    for name, s_c, length in (("mid", G["s_mid"], C["patch_mid_mm"]), ("tip", G["s_tip"], C["patch_tip_mm"])):
        on_pla = span is not None and span[0] - TOL <= s_c - length / 2 and s_c + length / 2 <= span[1] + TOL
        f, plen = M.patch_load(pad_sel(G, s_c, length, G["xf"] + tpla if on_pla else None), 1.0)
        u = M.solve(f)
        ux, uy = M.vertex_u(u)
        c = float(f @ u)
        st, vm = M.stress(u)
        out[name] = dict(s_mm=s_c, patch_len_mm=plen, on_pla=on_pla, compliance_mm_per_N=c, k_N_per_mm=1 / c,
                         tip_ux_per_N=float(ux[it]), tip_uy_per_N=float(uy[it]),
                         wrap_ratio=float(ux[it] / c), **{k + "_per_N": v for k, v in st.items()})
        keep[name] = (f, u, vm)
    if point:
        f, iload = M.point_load((G["xf"], G["y0"] - G["s_mid"]), 1.0)
        u = M.solve(f)
        ux, uy = M.vertex_u(u)
        st, vm = M.stress(u)
        out["point"] = dict(s_mm=G["s_mid"], load_ux_per_N=float(ux[iload]), k_at_node_N_per_mm=float(-1 / ux[iload]),
                            tip_ux_per_N=float(ux[it]), note="2D point load: displacement under the load is log-singular (mesh dependent)",
                            **{k + "_per_N": v for k, v in st.items()})
        keep["point"] = (f, u, vm)
    return (out, M, keep) if fields else (out, None, None)


# ------------------------------------------------------------------ validation
def validate(G, E, nu, quick):
    res = {"rect": [], "wedge": [], "finray": []}
    Lb, H, D = 60.0, 6.0, 20.0
    Gs = E / (2 * (1 + nu))
    Ib = D * H ** 3 / 12
    d_timo = Lb ** 3 / (3 * E * Ib) + Lb / (5 / 6 * Gs * D * H)
    d_eb = Lb ** 3 / (3 * E * Ib)
    rect = [(0, -H / 2), (Lb, -H / 2), (Lb, H / 2), (0, H / 2)]
    for h in ([3.0, 1.5, 0.75] if quick else [3.0, 1.5, 0.75, 0.375]):
        mesh, _ = gmsh_mesh(rect, [], h)
        for order in (1, 2):
            M = Model(mesh, E, nu, D, lambda x: np.abs(x[0]) < TOL, order=order)
            f, _ = M.patch_load(lambda x: np.abs(x[0] - Lb) < TOL, 1.0, direction=(0.0, -1.0))
            d = float(f @ M.solve(f))
            res["rect"].append(dict(h=h, order=order, dofs=int(M.ib.N), delta_mm=d, ratio_to_timoshenko=d / d_timo))
    res["rect_ref"] = dict(timoshenko_mm=d_timo, euler_bernoulli_mm=d_eb, E_MPa=E, nu=nu)
    a = G["s_mid"]
    dA, _ = fb.compliance(G, E, nu, a, "solid")
    for h in ([2.0, 1.0, 0.5] if quick else [2.0, 1.0, 0.5, 0.25]):
        mesh, _ = finger_mesh(G, h, solid=True)
        M = Model(mesh, E, nu, G["D"], clamp_root(G))
        f, _ = M.patch_load(pad_sel(G, a, 2.0), 1.0)
        c = float(f @ M.solve(f))
        res["wedge"].append(dict(h=h, dofs=int(M.ib.N), compliance=c, ratio_to_hand=c / dA))
    res["wedge_ref"] = dict(hand_compliance=dA, L_mm=G["L"], note="EB+Timoshenko tapered wedge, point load; FEA uses a 2 mm patch")
    for h in ([0.8, 0.5, 0.35] if quick else [0.8, 0.5, 0.35, 0.25, 0.18]):
        t0 = time.time()
        o, _, _ = run_cases(G, h, E, nu, point=False)
        res["finray"].append(dict(h=h, dofs=o["dofs"], secs=time.time() - t0,
                                  k_mid=o["mid"]["k_N_per_mm"], k_tip=o["tip"]["k_N_per_mm"],
                                  wrap_mid=o["mid"]["wrap_ratio"],
                                  vm_p99_mid=o["mid"]["vm_p99_per_N"], vm_max_mid=o["mid"]["vm_max_per_N"],
                                  vm_p99_tip=o["tip"]["vm_p99_per_N"], vm_max_tip=o["tip"]["vm_max_per_N"]))
    res["finray_geometry"] = f"L {G['L']:g}, wall {G['t']:g}, rib {G['tr']:g}, {G['n']} ribs at {G['beta']:g} deg"
    return res


# ------------------------------------------------------------------ export for three.js
def export_json(path, M, case, u, vm_qp, F_N, extra, ep_qp=None):
    """Fields at mesh vertices.  u and vm_qp are the actual fields (already at F_N)."""
    ux, uy = M.vertex_u(u)
    vm1 = np.clip(project_p1(M.ib, vm_qp), 0, None)
    p = M.mesh.p
    t = ccw(p, M.mesh.t)
    d = dict(units="mm, N, MPa", frame="finger-A local: pad face x = xf, root y = y0, tip at y0 - L; z = finger depth",
             case=case, F_N=F_N, E_MPa=M.E, nu=M.nu, depth_mm=M.D, winding="counter-clockwise (three.js FrontSide safe)",
             note="displacement and stress at mesh vertices (P2 solution sampled at P1 vertices; stress L2-projected)",
             nodes=np.round(p.T, 3).ravel().tolist(), elements=t.T.ravel().astype(int).tolist(),
             material=M.mat.astype(int).tolist() if (M.mat == 1).any() else None,
             displacement=[float(f"{v:.4g}") for v in np.column_stack([ux, uy]).ravel()],
             von_mises=[float(f"{v:.3g}") for v in vm1], **extra)
    if ep_qp is not None:
        d["green_lagrange_strain_max_principal"] = [float(f"{v:.3g}") for v in np.clip(project_p1(M.ib, ep_qp), 0, None)]
    return dump(path, d, compact=True)


# ------------------------------------------------------------------ sweep
def sweep_combos(base, quick):
    angles = [0, 15, 30, 45]
    ribs = [3, 5, 7, 9] if quick else [3, 4, 5, 6, 7, 9]
    walls = [0.8, 1.0, 1.2]
    ribt = [0.6, 0.8, 1.0]
    combos = [dict(rib_angle=a, ribs=n, wall=w, rib_thickness=r, tip_width=0.0)
              for a in angles for n in ribs for w in walls for r in ribt]
    combos += [dict(rib_angle=a, ribs=n, wall=w, rib_thickness=r, tip_width=tw)
               for tw in (2.0, 4.0) for a in (0, 30) for n in (4, 6) for w in walls for r in ribt]
    combos.append(dict(rib_angle=base["rib_angle"], ribs=base["ribs"], wall=base["wall"],
                       rib_thickness=base["rib_thickness"], tip_width=0.0))  # CAD section at L 45
    return combos


def h_nl_screen(G, quick):
    tm = min(G["t"], G["tr"])
    return min(0.6, tm / 1.2) if quick else min(0.5, tm / 1.5)


def h_sweep(G, quick):
    return min(0.5, min(G["t"], G["tr"]) / 2) if quick else min(0.35, min(G["t"], G["tr"]) / 2.5)


def sweep(P, E, nu, quick, limit=None):
    rows, seen = [], set()
    for c in sweep_combos(P["finger"], quick)[:limit]:
        key = tuple(sorted(c.items()))
        if key in seen:
            continue
        seen.add(key)
        G = fb.load_geometry(P, design=True, **c)
        h = h_sweep(G, quick)
        try:
            o, _, _ = run_cases(G, h, E, nu, point=False)
        except Exception as ex:  # record and continue
            rows.append(dict(**c, error=str(ex)))
            continue
        rows.append(row_from(c, h, o, E))
    return rows


def row_from(c, h, o, E, option=None):
    return dict(**c, option=option, h=h, E_solved_MPa=E, mass_g=o["mass_g"],
                k_mid=o["mid"]["k_N_per_mm"], k_tip=o["tip"]["k_N_per_mm"], wrap_mid=o["mid"]["wrap_ratio"],
                tip_ux_mid_per_N=o["mid"]["tip_ux_per_N"],
                vm_p99_mid=o["mid"]["vm_p99_per_N"], vm_max_mid=o["mid"]["vm_max_per_N"],
                vm_p99_tip=o["tip"]["vm_p99_per_N"], vm_max_tip=o["tip"]["vm_max_per_N"],
                strain_p99_mid=o["mid"]["strain_p99_per_N"], strain_p99_tip=o["tip"]["strain_p99_per_N"],
                pla_vm_max_tip=o["tip"].get("pla_vm_max_per_N"))


def assess(r, E_ref):
    """Criteria (TPU-only rows scale exactly with E: k ~ E, strain ~ 1/E, stress independent of E).
    window:  k_tip(E 56) >= k_min and k_tip(E 67) <= k_max       [DESIGN-BASIS R12, E band section 4]
    strain:  p99 principal strain at F_target, tip pad, E 56 <= 10 %  [DESIGN-BASIS LC1]
    stress:  p99 von Mises at F_cap, tip pad <= 4.5 MPa            [A, this lane]
    mid_*:   the same stress / strain checks on the mid-length patch (secondary: D2 contact is the tip pad).
    nl_cap:  nonlinear (TL-SVK) tip-pad limit load at E 56 >= F_cap 10 N [DESIGN-BASIS R15]; screened
             candidates only.  nl_trip: limit at E 56 >= the 8 N FSR over-force trip (DESIGN-BASIS
             section 8), i.e. >= 1.6 x F_target.  feasible = feasible_linear and nl_cap."""
    T, g = fb.INPUTS["TPU"], fb.INPUTS["grip"]
    El, Eh = T["E_low_MPa"], T["E_nominal_MPa"]
    r["k_tip_E56"] = r["k_tip"] * El / E_ref
    r["k_tip_E67"] = r["k_tip"] * Eh / E_ref
    r["k_mid_E67"] = r["k_mid"] * Eh / E_ref
    r["strain_LC1_tip_E56"] = r["strain_p99_tip"] * g["target_N"] * E_ref / El
    r["strain_LC1_mid_E56"] = r["strain_p99_mid"] * g["target_N"] * E_ref / El
    r["vm_cap_tip"] = r["vm_p99_tip"] * g["cap_N"]
    r["vm_cap_mid"] = r["vm_p99_mid"] * g["cap_N"]
    r["window_ok"] = bool(r["k_tip_E56"] >= g["k_tip_min_N_per_mm"] and r["k_tip_E67"] <= g["k_tip_max_N_per_mm"])
    r["strain_ok"] = bool(r["strain_LC1_tip_E56"] <= T["strain_limit_LC1"])
    r["stress_ok"] = bool(r["vm_cap_tip"] <= T["stress_allow_cap_MPa"])
    r["mid_ok"] = bool(r["vm_cap_mid"] <= T["stress_allow_cap_MPa"] and r["strain_LC1_mid_E56"] <= T["strain_limit_LC1"])
    r["feasible_linear"] = bool(r["window_ok"] and r["strain_ok"] and r["stress_ok"])
    r["feasible"] = r["feasible_linear"]  # provisional until the nonlinear screen (nl_screened)
    r["nl_screened"] = False
    r["feasible_design_basis_only"] = bool(r["window_ok"] and r["strain_ok"])
    r["k_log_dist_to_default"] = abs(math.log(math.sqrt(r["k_tip_E56"] * r["k_tip_E67"]) / g["k_tip_default_N_per_mm"]))
    return r


def recommend(rows):
    good = [r for r in rows if "error" not in r]
    feas = sorted([r for r in good if r["feasible_linear"]], key=lambda r: (not r["mid_ok"], round(r["mass_g"], 2), r["k_log_dist_to_default"]))
    win = [r for r in good if r["window_ok"]]
    counts = dict(runs=len(good), window_ok=len(win), strain_ok=len([r for r in good if r["strain_ok"]]),
                  stress_ok=len([r for r in good if r["stress_ok"]]), feasible_linear=len(feas),
                  feasible_and_mid_ok=len([r for r in feas if r["mid_ok"]]),
                  feasible_design_basis_only=len([r for r in good if r["feasible_design_basis_only"]]),
                  in_window_failing_stress=len([r for r in win if not r["stress_ok"]]),
                  in_window_failing_strain=len([r for r in win if not r["strain_ok"]]))
    if win:
        best_win = min(win, key=lambda r: r["vm_cap_tip"])
        governing = dict(lowest_cap_stress_in_window=dict(vm_cap_tip=best_win["vm_cap_tip"], design=_key(best_win)),
                         highest_k_E67_passing_stress=max([r["k_tip_E67"] for r in good if r["stress_ok"]], default=None))
    else:
        governing = dict(note="no design inside the window")
    near = sorted([r for r in win if not r["feasible_linear"]], key=lambda r: r["vm_cap_tip"])[:5]
    return feas, counts, governing, near


def screen_list(feas, n_light=5, n_stiff=5):
    """Candidates for the nonlinear screen: the lightest linear-feasible designs (mid_ok first) plus
    the stiffest linear-feasible ones (highest k_tip at E 56, which fold latest), de-duplicated."""
    out, seen = [], set()
    for r in feas[:n_light] + sorted(feas, key=lambda r: -r["k_tip_E56"])[:n_stiff]:
        k = tuple(sorted(_key(r).items()))
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def nl_limit(G, E, nu, h, F_max, option=None, dF0=1.0, dF_min=0.05):
    """Tip-pad nonlinear limit load (bisection bracket) for one design at modulus E."""
    mesh, mat = finger_mesh(G, h, option=option)
    M = Model(mesh, E, nu, G["D"], clamp_root(G), mat=mat)
    _, tpla, span = pla_parts(G, option)
    s_c, ln = G["s_tip"], fb.INPUTS["contact"]["patch_tip_mm"]
    on_pla = span is not None and span[0] - TOL <= s_c - ln / 2 and s_c + ln / 2 <= span[1] + TOL
    f, _ = M.patch_load(pad_sel(G, s_c, ln, G["xf"] + tpla if on_pla else None), 1.0)
    t0 = time.time()
    _, info = nonlinear(M, f, F_max, dF0=dF0, dF_min=dF_min)
    return dict(h=h, E_solved_MPa=E, last_converged_F_N=info["last_converged_F_N"],
                smallest_rejected_F_N=info["smallest_rejected_F_N"], reached=info["reached_cap"],
                newton_iterations=info["newton_iterations"], secs=time.time() - t0)


def _key(r):
    return {k: r[k] for k in ("rib_angle", "ribs", "wall", "rib_thickness", "tip_width") if k in r}


# ------------------------------------------------------------------ motion
def motion(G, kA, kB, nl_tip, E_ref_nl):
    """Jaw kinematics and pinch force vs commanded jaw (servo) angle, design geometry.
    kA, kB: {E_label: per-finger tip-pad stiffness N/mm}.  nl_tip: (F, d) nonlinear per-finger
    force vs patch displacement at E_ref_nl (SVK scales exactly with E at fixed nu)."""
    g, dr = fb.INPUTS["grip"], fb.INPUTS["drive"]
    th = np.round(np.linspace(g["theta_min_deg"], g["theta_open_max_deg"], int(round((g["theta_open_max_deg"] - g["theta_min_deg"]) * 10)) + 1), 3)

    def world_A(x, y, t):
        tr = math.radians(t)
        return (-G["a"] / 2 + x * math.cos(tr) + y * math.sin(tr), -x * math.sin(tr) + y * math.cos(tr))

    pts = {"tip": (G["xf"], G["y0"] - G["L"]), "tip_pad": (G["xf"], G["y0"] - G["s_tip"]),
           "mid": (G["xf"], G["y0"] - G["s_mid"]), "root_front": (G["xf"], G["y0"])}
    path = {k: np.array([world_A(*v, t) for t in th]) for k, v in pts.items()}
    opening = {k: (-2 * path[k][:, 0]) for k in pts}
    rc = G["rc_tip"]
    c_arm = fb.arm_compliance(G, G["s_tip"])
    c_mesh = fb.mesh_compliance(G, G["s_tip"])
    c_extra = 2 * c_arm + c_mesh
    ply = g["cloth_thickness_mm"]
    out = dict(geometry=f"L {G['L']:g} mm, r_c {rc:g} mm", theta_deg=th, opening_mm=opening,
               tip_path_A=np.round(path["tip"], 3), pad_face_tilt_deg=th,
               ejection_limit_deg=math.degrees(math.atan(g["mu_pad_cloth"])),
               theta_zero_convention=("theta 0 = rigid pads 1 mm apart after the R21 CALIBRATE state (backlash taken up in "
                                      "the closing direction, lag 0) [A]; 'centred' sensitivity uses lag jt/2 at the pitch circle"),
               series_compliance=dict(c_arm_each=c_arm, c_mesh_B=c_mesh))
    pinch = {}
    for lagc in ("calibrated", "centred"):
        lag = fb.backlash_lag_mm(G, rc, lagc)
        interf = np.clip(ply - (opening["tip_pad"] + lag), 0, None)
        cur, summ = {}, {}
        for en in kA:
            c_tot = 1 / kA[en] + 1 / kB[en] + c_extra
            F = interf / c_tot
            cur[f"linear_{en}"] = F
            summ[en] = dict(k_A=kA[en], k_B=kB[en], k_pair=1 / c_tot,
                            arm_plus_mesh_fraction=c_extra / c_tot,
                            theta_for_target_deg=fb.overtravel_deg(G, g["target_N"], 1 / c_tot, rc, lag),
                            theta_for_cap_deg=fb.overtravel_deg(G, g["cap_N"], 1 / c_tot, rc, lag),
                            F_at_theta_min_N=float(F[0]))
        if nl_tip is not None:
            Fn, dn = np.asarray(nl_tip[0]), np.asarray(nl_tip[1])
            for en, E in (("E56", fb.INPUTS["TPU"]["E_low_MPa"]), ("E67", fb.INPUTS["TPU"]["E_nominal_MPa"])):
                Fs = Fn * E / E_ref_nl
                Fg = np.linspace(0, Fs[-1], 300)
                tot = 2 * np.interp(Fg, Fs, dn) + c_extra * Fg
                cur[f"nonlinear_bare_{en}"] = np.where(interf <= tot[-1], np.interp(interf, tot, Fg), np.nan)
        contact = float(th[interf > 0].max()) if np.any(interf > 0) else None
        fold = {}
        for k, v in cur.items():
            if k.startswith("nonlinear"):
                ok = np.isfinite(v)
                fold[k] = dict(theta_last_converged_deg=float(th[ok].min()) if ok.any() else None,
                               F_last_N=float(np.nanmax(v)) if ok.any() else None)
        pinch[lagc] = dict(lag_mm=lag, contact_theta_deg=contact, F_N=cur, summary=summ, nonlinear_fold=fold)
    # R15 check: does theta_min cap the pinch at F_cap for this finger?
    cal = pinch["calibrated"]["summary"]
    band = [en for en in ("E56", "E67") if en in cal]
    th_cap = {en: cal[en]["theta_for_cap_deg"] for en in band}
    th_tgt = {en: cal[en]["theta_for_target_deg"] for en in band}
    th_rec = math.ceil(max(th_cap.values()) * 10) / 10  # least-negative cap angle, rounded toward 0
    out["R15_theta_min_check"] = dict(
        theta_min_design_basis_deg=g["theta_min_deg"], F_cap_N=g["cap_N"],
        F_at_theta_min_linear_N={en: cal[en]["F_at_theta_min_N"] for en in band},
        theta_for_cap_deg=th_cap, theta_for_target_deg=th_tgt,
        conflict=bool(any(cal[en]["F_at_theta_min_N"] > g["cap_N"] for en in band)),
        theta_min_recommended_deg=th_rec,
        target_margin_deg_at_E56=(th_tgt["E56"] - th_rec) if "E56" in th_tgt else None,
        note=("calibrated theta 0 (lag 0), one 0.3 mm ply at the tip pad, finger A + nail and finger B + FSR backing, "
              "linear FEA stiffness plus arm and mesh compliance. theta_min_recommended = the least-negative "
              "theta_for_cap over E 56-67; the E 67 finger reaches the cap first."))
    out["nonlinear_fold_check"] = pinch["calibrated"]["nonlinear_fold"]
    hf = dr["hold_fraction"]
    lims = {}
    for an, kgcm in fb.INPUTS["actuators"].items():
        T = kgcm * fb.KGCM_TO_NMM * hf
        lims[an] = dict(design_basis=fb.force_from_torque(T, rc, "design_basis"),
                        lane_less_conservative=fb.force_from_torque(T, rc, "lane"))
    out["pinch_one_ply_at_tip_pad"] = pinch
    out["hold_force_limit_N"] = dict(hold_fraction=hf, r_c_mm=rc, note="r_c invariant with jaw angle (DESIGN-BASIS D2)", servos=lims)
    out["servo_angle_note"] = "servo horn is on finger A's shaft: servo angle = jaw angle theta + horn offset (1:1)"
    return out


# ------------------------------------------------------------------ plots
def tri(M):
    import matplotlib.tri as mtri
    return mtri.Triangulation(M.mesh.p[0], M.mesh.p[1], ccw(M.mesh.p, M.mesh.t).T)


def plot_validation(val):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    for order, mk in ((1, "o-"), (2, "s-")):
        r = [x for x in val["rect"] if x["order"] == order]
        ax[0].semilogx([x["h"] for x in r], [x["ratio_to_timoshenko"] for x in r], mk, label=f"P{order}")
    ax[0].axhline(1, color="k", lw=0.8)
    ax[0].set_xlabel("element size h, mm")
    ax[0].set_ylabel("tip deflection / Timoshenko")
    ax[0].set_title("V1 rectangular cantilever 60x6, nu 0.45")
    ax[0].legend()
    ax[1].semilogx([x["h"] for x in val["wedge"]], [x["ratio_to_hand"] for x in val["wedge"]], "s-")
    ax[1].axhline(1, color="k", lw=0.8)
    ax[1].set_xlabel("element size h, mm")
    ax[1].set_ylabel("compliance / tapered EB+Timoshenko")
    ax[1].set_title(f"V2 solid wedge (L {val['wedge_ref']['L_mm']:g}), mid load")
    r = val["finray"]
    for key, mk, lab in (("k_mid", "s-", "k mid"), ("k_tip", "o-", "k tip"), ("vm_p99_tip", "^-", "vM p99 tip"),
                         ("vm_p99_mid", "<-", "vM p99 mid"), ("vm_max_mid", "v--", "vM max mid")):
        ax[2].semilogx([x["h"] for x in r], [x[key] / r[-1][key] for x in r], mk, label=lab)
    ax[2].axhline(1, color="k", lw=0.8)
    ax[2].set_xlabel("element size h, mm")
    ax[2].set_ylabel("value / finest mesh")
    ax[2].set_title(f"V3 Fin Ray convergence (P2), {val['finray_geometry']}", fontsize=9)
    ax[2].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGS / "fea_validation.png", dpi=130)
    plt.close(fig)


def plot_fields(G, M, keep, nl, label, Mn):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri
    g = fb.INPUTS["grip"]
    T0 = tri(M)
    tt = T0.triangles
    fig, ax = plt.subplots(1, 3, figsize=(12, 5.6))
    for a_, (name, (f, u, vm)) in zip(ax, keep.items()):
        ux, uy = M.vertex_u(u)
        F = g["target_N"]
        a_.triplot(T0, color="0.8", lw=0.3)
        a_.triplot(mtri.Triangulation(M.mesh.p[0] + F * ux, M.mesh.p[1] + F * uy, tt), color="#2a6f97", lw=0.3)
        if name in nl and nl[name].get("u_target") is not None:
            uxn, uyn = Mn.vertex_u(nl[name]["u_target"])
            a_.triplot(mtri.Triangulation(Mn.mesh.p[0] + uxn, Mn.mesh.p[1] + uyn, ccw(Mn.mesh.p, Mn.mesh.t).T), color="#c8553d", lw=0.3)
        it = tip_index(G, M.mesh)
        a_.set_title(f"{name}: F = {F:g} N, E {M.E:g}\ntip ux {F * ux[it]:+.2f} mm (+ = toward object)", fontsize=9)
        a_.set_aspect("equal")
        a_.set_xlabel("x, mm (object on +x side)")
    ax[0].set_ylabel("y, mm (root clamped at y0)")
    fig.suptitle(f"{label}. Deformed, true scale: grey undeformed, blue linear, red nonlinear (TL-SVK)", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGS / "fea_deformed.png", dpi=130)
    plt.close(fig)

    allow = fb.INPUTS["TPU"]["stress_allow_cap_MPa"]
    fig, ax = plt.subplots(1, 3, figsize=(13, 5.6))
    for a_, name in zip(ax[:2], ("mid", "tip")):
        f, u, vm = keep[name]
        vm1 = np.clip(project_p1(M.ib, vm), 0, None) * g["cap_N"]
        ux, uy = M.vertex_u(u)
        Td = mtri.Triangulation(M.mesh.p[0] + g["cap_N"] * ux, M.mesh.p[1] + g["cap_N"] * uy, tt)
        cs = a_.tripcolor(Td, vm1, shading="gouraud", cmap="viridis", vmin=0, vmax=max(allow, np.percentile(vm1, 99.5)))
        a_.set_aspect("equal")
        a_.set_title(f"{name}, F = cap {g['cap_N']:g} N, linear\nvon Mises MPa (allow {allow:g})", fontsize=9)
        fig.colorbar(cs, ax=a_, shrink=0.7)
    if "tip" in nl and nl["tip"].get("u_last") is not None:
        un = nl["tip"]["u_last"]
        uxn, uyn = Mn.vertex_u(un)
        v1 = np.clip(project_p1(Mn.ib, nl["tip"]["vm_cauchy_last"]), 0, None)
        cs = ax[2].tripcolor(mtri.Triangulation(Mn.mesh.p[0] + uxn, Mn.mesh.p[1] + uyn, ccw(Mn.mesh.p, Mn.mesh.t).T), v1, shading="gouraud", cmap="viridis",
                             vmin=0, vmax=max(allow, np.percentile(v1, 99.5)))
        ax[2].set_aspect("equal")
        ax[2].set_title(f"tip, nonlinear at {nl['tip']['F_last']:g} N\nCauchy von Mises MPa", fontsize=9)
        fig.colorbar(cs, ax=ax[2], shrink=0.7)
    fig.suptitle(label, fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGS / "fea_stress.png", dpi=130)
    plt.close(fig)


def plot_nonlinear(nlj, E):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4.6))
    cols = {"rec_tip": "#c8553d", "rec_mid": "#2a6f97", "cadL60_tip": "#6d597a", "rec_nailA_tip": "#e09f3e"}
    for name, v in nlj.items():
        c = cols.get(name, "k")
        ax.plot(v["patch_disp_mm"], v["F_N"], "-o", color=c, ms=2.5, label=f"{name} (E {v['E_MPa']:g})")
        ax.plot([0, v["F_N"][-1] * v["linear_compliance_mm_per_N"]], [0, v["F_N"][-1]], "--", color=c, lw=0.8)
        if v["smallest_rejected_F_N"] is not None:
            ax.axhspan(v["last_converged_F_N"], v["smallest_rejected_F_N"], color=c, alpha=0.15)
    ax.axhline(fb.INPUTS["grip"]["target_N"], color="k", lw=0.6, ls="--")
    ax.set_xlabel("patch displacement (work-conjugate), mm")
    ax.set_ylabel("contact force per finger, N")
    ax.set_title("TL-SVK, plane stress; dashed = linear; band = limit-load bracket", fontsize=9)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIGS / "fea_nonlinear.png", dpi=130)
    plt.close(fig)


def plot_sweep(rows, rec, G0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    g, T = fb.INPUTS["grip"], fb.INPUTS["TPU"]
    good = [r for r in rows if "error" not in r and r.get("option") is None]
    fig, ax = plt.subplots(2, 2, figsize=(12.5, 9))
    sub = [r for r in good if r["tip_width"] == 0 and r["wall"] == 1.0 and r["rib_thickness"] == 0.8]
    for n in sorted({r["ribs"] for r in sub}):
        rr = sorted([r for r in sub if r["ribs"] == n], key=lambda r: r["rib_angle"])
        ax[0, 0].plot([r["rib_angle"] for r in rr], [r["k_tip_E67"] for r in rr], "-o", ms=3, label=f"{n} ribs")
        ax[0, 1].plot([r["rib_angle"] for r in rr], [r["wrap_mid"] for r in rr], "-o", ms=3, label=f"{n} ribs")
    ax[0, 0].axhspan(g["k_tip_min_N_per_mm"] * T["E_nominal_MPa"] / T["E_low_MPa"], g["k_tip_max_N_per_mm"], color="#2a9d8f", alpha=0.2,
                     label="window over E 56-67")
    ax[0, 0].set_xlabel("rib angle, deg")
    ax[0, 0].set_ylabel("k tip pad at E 67, N/mm")
    ax[0, 0].set_title(f"L {G0['L']:g}: tip stiffness (wall 1.0, rib 0.8, sharp tip)")
    ax[0, 0].legend(fontsize=7, ncol=2)
    ax[0, 1].axhline(0, color="k", lw=0.8)
    ax[0, 1].set_xlabel("rib angle, deg")
    ax[0, 1].set_ylabel("wrap = tip ux / patch disp (+ = Fin Ray effect)")
    ax[0, 1].set_title("wrap-around sign, mid-length load")
    sc = ax[1, 0].scatter([r["k_tip_E67"] for r in good], [r["vm_cap_tip"] for r in good],
                          c=[r["strain_LC1_tip_E56"] * 100 for r in good], cmap="magma_r", s=14)
    fig.colorbar(sc, ax=ax[1, 0], label="p99 strain at 5 N, E 56, %")
    ax[1, 0].axvspan(g["k_tip_min_N_per_mm"] * T["E_nominal_MPa"] / T["E_low_MPa"], g["k_tip_max_N_per_mm"], color="#2a9d8f", alpha=0.2)
    ax[1, 0].axhline(T["stress_allow_cap_MPa"], color="r", ls="--", lw=0.8, label="stress allowable at cap")
    for r in rec[:3]:
        ax[1, 0].plot(r["k_tip_E67"], r["vm_cap_tip"], "o", mfc="none", mec="#2a9d8f", ms=11)
    ax[1, 0].set_xscale("log")
    ax[1, 0].set_xlabel("k tip pad at E 67, N/mm (band = window valid over E 56-67)")
    ax[1, 0].set_ylabel("p99 von Mises at 10 N, tip pad, MPa")
    ax[1, 0].set_title("feasible = inside band and below the red line (circled = recommended)")
    ax[1, 0].legend(fontsize=8)
    sc = ax[1, 1].scatter([r["mass_g"] for r in good], [r["k_tip_E67"] for r in good],
                          c=[r["rib_angle"] for r in good], cmap="viridis", s=14)
    fig.colorbar(sc, ax=ax[1, 1], label="rib angle, deg")
    ax[1, 1].axhspan(g["k_tip_min_N_per_mm"] * T["E_nominal_MPa"] / T["E_low_MPa"], g["k_tip_max_N_per_mm"], color="#2a9d8f", alpha=0.2)
    ax[1, 1].set_yscale("log")
    ax[1, 1].set_xlabel("finger mass, g")
    ax[1, 1].set_ylabel("k tip pad at E 67, N/mm")
    ax[1, 1].set_title("mass vs stiffness, all runs")
    fig.tight_layout()
    fig.savefig(FIGS / "fea_sweep.png", dpi=130)
    plt.close(fig)


def plot_motion(G, mot):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    g = fb.INPUTS["grip"]
    th = np.array(mot["theta_deg"])
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
    tp = np.array(mot["tip_path_A"])
    ax[0].plot(tp[:, 0], tp[:, 1], color="#c8553d", label="tip A")
    ax[0].plot(-tp[:, 0], tp[:, 1], color="#2a6f97", label="tip B")
    for tt in (g["theta_min_deg"], 0, g["theta_open_max_deg"]):
        i = int(np.argmin(abs(th - tt)))
        ax[0].plot([-G["a"] / 2, tp[i, 0]], [0, tp[i, 1]], "k-", lw=0.6)
        ax[0].plot([G["a"] / 2, -tp[i, 0]], [0, tp[i, 1]], "k-", lw=0.6)
    ax[0].set_aspect("equal")
    ax[0].set_title(f"fingertip paths, theta {g['theta_min_deg']:g}..{g['theta_open_max_deg']:g} deg ({mot['geometry']})", fontsize=9)
    ax[0].legend(fontsize=8)
    for k, ls in (("tip", "-"), ("tip_pad", "--"), ("mid", ":"), ("root_front", "-.")):
        ax[1].plot(th, mot["opening_mm"][k], ls, label=k)
    ax[1].axhline(0, color="k", lw=0.6)
    ax[1].set_xlabel("jaw angle theta, deg (= servo angle - offset)")
    ax[1].set_ylabel("rigid-finger jaw opening, mm")
    ax[1].legend(fontsize=7)
    ax[1].set_title("jaw opening vs angle")
    pc = mot["pinch_one_ply_at_tip_pad"]["calibrated"]
    for k, v in pc["F_N"].items():
        ax[2].plot(th, [np.nan if x is None else x for x in v], "--" if k.startswith("nonlinear") else "-", label=k)
    for k, v in mot["hold_force_limit_N"]["servos"].items():
        if "design point" in k:
            ax[2].axhline(v["design_basis"], color="0.3", ls=":", lw=1.2, label=f"hold limit {k.split(' (')[0]}")
    ax[2].axhline(g["target_N"], color="k", ls="--", lw=0.8)
    ax[2].axhline(g["cap_N"], color="k", ls=":", lw=0.8)
    ax[2].set_xlim(g["theta_min_deg"], 1)
    ax[2].set_ylim(0, 15)
    ax[2].set_xlabel("commanded jaw angle theta, deg")
    ax[2].set_ylabel("pinch force per finger, N")
    ax[2].set_title("one 0.3 mm ply at the tip pad (FEA stiffness, calibrated theta 0)", fontsize=9)
    ax[2].legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(FIGS / "finger_motion.png", dpi=130)
    plt.close(fig)


# ------------------------------------------------------------------ main
def self_intersections(M, u):
    """Count crossings between non-adjacent boundary edges in the deformed configuration
    (self-contact is not modelled, so a crossing would mean the state is unphysical)."""
    ux, uy = M.vertex_u(u)
    q = np.vstack([M.mesh.p[0] + ux, M.mesh.p[1] + uy])
    e = M.mesh.facets[:, M.mesh.boundary_facets()]
    A, B = q[:, e[0]].T, q[:, e[1]].T
    n, hits = len(A), 0
    for i0 in range(0, n, 256):
        a, b = A[i0:i0 + 256, None], B[i0:i0 + 256, None]
        c, d = A[None], B[None]
        def orient(p1, p2, p3):
            return (p2[..., 0] - p1[..., 0]) * (p3[..., 1] - p1[..., 1]) - (p2[..., 1] - p1[..., 1]) * (p3[..., 0] - p1[..., 0])
        o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
        x = (o1 * o2 < 0) & (o3 * o4 < 0)
        ei = e[:, i0:i0 + 256].T[:, None, :]
        share = (ei[..., 0:1] == e.T[None, :, :]).any(-1) | (ei[..., 1:2] == e.T[None, :, :]).any(-1)
        hits += int((x & ~share).sum())
    return hits // 2


def inc_mode(M, G, u_nl, u_lin_unit, F):
    """Incremental (nonlinear minus linear) displacement at the last converged load F: identifies
    the limit mechanism.  Back-flank bow = component along the back flank's outward normal (-x side),
    + = bowing outward (away from the lattice); pad-face component = ux (+ = toward the object)."""
    du = u_nl - F * u_lin_unit
    dux, duy = M.vertex_u(du)
    x, y = M.mesh.p
    xf, y0, L, W, tw = G["xf"], G["y0"], G["L"], G["W"], G.get("tip_width", 0.0)
    a0, a1 = np.array([xf - W, y0]), np.array([xf - tw, y0 - L])
    d = (a1 - a0) / np.linalg.norm(a1 - a0)
    nrm = np.array([d[1], -d[0]])  # outward normal (points to -x)
    if nrm[0] > 0:
        nrm = -nrm
    rel = np.column_stack([x - a0[0], y - a0[1]])
    dist = np.abs(rel @ np.array([-d[1], d[0]]))
    on_back = (dist < 1e-6) & (rel @ d > -1e-9)
    on_pad = np.abs(x - xf) < TOL
    s_back, s_pad = (y0 - y[on_back]), (y0 - y[on_pad])
    bow = dux[on_back] * nrm[0] + duy[on_back] * nrm[1]
    padx = dux[on_pad]
    ob, op = np.argsort(s_back), np.argsort(s_pad)
    it = tip_index(G, M.mesh)
    tip_inc = float(np.hypot(dux[it], duy[it]))
    interior = (s_back > 2.0) & (s_back < G["L"] - 8.0)
    bow_i = bow[interior]
    bmax = float(bow_i[np.argmax(np.abs(bow_i))]) if bow_i.size else 0.0
    s_bmax = float(s_back[interior][np.argmax(np.abs(bow_i))]) if bow_i.size else None
    ratio = abs(bmax) / tip_inc if tip_inc > 0 else None
    mech = ("distributed back-flank bow (compressed back flank buckles between rib nodes)" if ratio is not None and ratio >= 0.5
            else "local tip-wedge fold (incremental motion concentrated at the tip)")
    return dict(F_N=F, tip_incremental_mm=tip_inc, tip_incremental_ux_mm=float(dux[it]), back_bow_max_mm=bmax,
                back_bow_s_mm=s_bmax, back_bow_to_tip_ratio=ratio, mechanism=mech,
                classifier="back-flank bow over 2 < s < L-8 vs tip incremental |du|; ratio >= 0.5 -> back-flank buckling",
                _s_back=s_back[ob], _bow=bow[ob], _s_pad=s_pad[op], _padx=padx[op], _du=(dux, duy))


def plot_nl_mode(runs):
    """runs: list of (label, M, G, rec) with rec['u_last'] and rec['mode']."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri
    runs = [r for r in runs if r[3].get("mode")]
    fig, ax = plt.subplots(2, len(runs), figsize=(5.2 * len(runs), 9.5), squeeze=False)
    for j, (lab, M, G, rec) in enumerate(runs):
        md = rec["mode"]
        dux, duy = md["_du"]
        ux, uy = M.vertex_u(rec["u_last"])
        mag = np.hypot(dux, duy)
        T = mtri.Triangulation(M.mesh.p[0] + ux, M.mesh.p[1] + uy, ccw(M.mesh.p, M.mesh.t).T)
        a_ = ax[0, j]
        a_.triplot(mtri.Triangulation(M.mesh.p[0], M.mesh.p[1], ccw(M.mesh.p, M.mesh.t).T), color="0.85", lw=0.25)
        cs = a_.tripcolor(T, mag, shading="gouraud", cmap="magma_r")
        fig.colorbar(cs, ax=a_, shrink=0.7, label="|u_nl - F u_lin|, mm")
        step = max(1, M.mesh.p.shape[1] // 350)
        a_.quiver((M.mesh.p[0] + ux)[::step], (M.mesh.p[1] + uy)[::step], dux[::step], duy[::step],
                  angles="xy", scale_units="xy", scale=1.0, width=0.003, color="#2a6f97")
        a_.set_aspect("equal")
        a_.set_title(f"{lab}\nincremental mode at F = {md['F_N']:.2f} N (E {M.E:g}); arrows true scale", fontsize=9)
        b_ = ax[1, j]
        b_.plot(md["_s_back"], md["_bow"], "-", color="#c8553d", label="back flank, outward-normal component")
        b_.plot(md["_s_pad"], md["_padx"], "-", color="#2a6f97", label="pad face ux (+ = toward object)")
        b_.axhline(0, color="k", lw=0.6)
        b_.axvline(G["s_tip"], color="0.5", ls=":", lw=0.8, label="tip-pad centroid")
        b_.set_xlabel("s from the root, mm")
        b_.set_ylabel("incremental displacement, mm")
        b_.set_title(f"{md['mechanism']}\nbow/tip ratio {md['back_bow_to_tip_ratio']:.2f}", fontsize=8)
        b_.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIGS / "fea_nl_mode.png", dpi=130)
    plt.close(fig)


def nl_run(M, G, f, u_lin, cap, h, tag):
    t0 = time.time()
    hist, info = nonlinear(M, f, cap)
    it = tip_index(G, M.mesh)
    Fs = [0.0] + [x["F_N"] for x in hist]
    dp = [0.0] + [float(f @ x["u"]) for x in hist]
    tipx = [0.0] + [float(M.vertex_u(x["u"])[0][it]) for x in hist]
    tgt = fb.INPUTS["grip"]["target_N"]
    u_last = hist[-1]["u"] if hist else None
    rec = dict(u_target=None, u_last=u_last, F_last=Fs[-1])
    if hist:
        i_t = int(np.argmin([abs(x["F_N"] - tgt) for x in hist]))
        rec["u_target"] = hist[i_t]["u"] if hist[i_t]["F_N"] <= Fs[-1] else None
        vm, ep, Jmin = nl_fields(M, u_last)
        st = M.stats(vm, ep)
        st["boundary_self_intersections"] = self_intersections(M, u_last)
        rec["vm_cauchy_last"], rec["ep_gl_last"] = vm, ep
    else:
        st, Jmin = {}, None
    mode = inc_mode(M, G, u_last, u_lin, Fs[-1]) if hist else None
    rec["mode"] = mode
    js = dict(E_MPa=M.E, h_mm=h, option=None if (M.mat == 0).all() else "with PLA", F_N=Fs, patch_disp_mm=dp, tip_ux_mm=tipx,
              incremental_mode=None if mode is None else {k: v for k, v in mode.items() if not k.startswith("_")},
              iters=[x["iters"] for x in hist], linear_compliance_mm_per_N=float(f @ u_lin),
              secant_k_at_target=(tgt / float(np.interp(tgt, Fs, dp))) if Fs[-1] >= tgt else None,
              secant_k_at_last=(Fs[-1] / dp[-1]) if dp[-1] else None,
              at_last_converged=dict(F_N=Fs[-1], cauchy_vm_and_green_lagrange_strain=st, J_min=Jmin,
                                     note="Cauchy sigma = F S F^T / J; strain = max |principal Green-Lagrange|; TPU elements"),
              secs=time.time() - t0, **info)
    print(f"  nonlinear {tag}: converged to {info['last_converged_F_N']:.3f} N, smallest rejected {info['smallest_rejected_F_N']}, "
          f"{info['newton_iterations']} Newton its, {time.time() - t0:.0f} s", flush=True)
    return js, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="coarser validation and sweep")
    ap.add_argument("--h", type=float, default=None, help="production element size, mm")
    ap.add_argument("--limit", type=int, default=None, help="smoke test: first N sweep combos only")
    ap.add_argument("--motion-only", action="store_true", help="re-run the jaw sweep from saved fea_summary.json")
    args = ap.parse_args()
    if args.motion_only:
        return motion_only()
    t0 = time.time()
    P = fb.load_params()
    used = fb.apply_overrides(P)
    T = fb.INPUTS["TPU"]
    E, El, nu = T["E_nominal_MPa"], T["E_low_MPa"], T["nu"]
    cap = fb.INPUTS["grip"]["cap_N"]
    Gd = fb.load_geometry(P, design=True)   # L 45, CAD section
    Gc = fb.load_geometry(P, design=False)  # L 60 CAD reference
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    h = args.h or 0.25

    # 1. validation (at E 67, the design modulus)
    val = validate(Gd, E, nu, args.quick)
    plot_validation(val)
    print("validation done", round(time.time() - t0, 1), "s", flush=True)

    # 2. reference cases: CAD section at L 45, CAD L 60; plane-strain bound and P1 on L 45
    ref = {}
    for name, G in (("cad_section_L45", Gd), ("cad_L60", Gc)):
        o, _, _ = run_cases(G, h, E, nu)
        ref[name] = o
    ref["cad_section_L45_plane_strain"], _, _ = run_cases(Gd, h, E, nu, mode="strain", point=False)
    ref["cad_section_L45_P1"], _, _ = run_cases(Gd, h, E, nu, order=1, point=False)
    print("reference cases done", round(time.time() - t0, 1), "s", flush=True)

    # 3. sweep at L 45 (TPU only, E 67; exact E scaling to 56)
    rows = sweep(P, E, nu, args.quick, args.limit)
    for r in rows:
        if "error" not in r:
            assess(r, E)
    feas, counts, governing, near = recommend(rows)
    print("sweep done", len(rows), "runs", counts, round(time.time() - t0, 1), "s", flush=True)

    # 4a. nonlinear screen (tip-pad limit load, bare finger) on the candidates: part of feasibility
    g_ = fb.INPUTS["grip"]
    trip = float(fb._get(P, ("grip", "fsr", "overforce_trip_N")) or 8.0)  # [A] DESIGN-BASIS section 8
    F_nl = cap * E / El  # solving at E 67 to this load = F_cap at E 56 (exact SVK scaling)
    cands = (screen_list(feas, *((2, 1) if args.quick else (5, 5))) if feas else near[:4])
    for r in cands:
        G = fb.load_geometry(P, design=True, **_key(r))
        hs = h_nl_screen(G, args.quick)
        lim = nl_limit(G, E, nu, hs, F_nl)
        r["nl_screen"] = lim
        r["nl_limit_tip_E56"] = lim["last_converged_F_N"] * El / E
        r["nl_cap_ok"] = bool(lim["reached"])
        r["nl_trip_ok"] = bool(r["nl_limit_tip_E56"] >= trip)
        r["nl_screened"] = True
        r["feasible"] = bool(r["feasible_linear"] and r["nl_cap_ok"])
        print(f"  nl screen {_key(r)} m {r['mass_g']:.2f} g: limit {r['nl_limit_tip_E56']:.2f} N at E {El:g} "
              f"(h {hs:.3g}, {lim['secs']:.0f} s)", flush=True)
    counts["nl_screened"] = len(cands)
    counts["nl_cap_ok"] = len([r for r in cands if r["nl_cap_ok"]])
    counts["nl_trip_ok"] = len([r for r in cands if r["nl_trip_ok"]])
    counts["feasible_linear_and_nl_cap"] = len([r for r in cands if r["feasible"]])
    print("nonlinear screen done", round(time.time() - t0, 1), "s", flush=True)

    # 4b. D7 variants on the candidates: finger A + nail, finger B + FSR backing, solved at E 56 and E 67
    variants = []
    for r in cands:
        c = _key(r)
        G = fb.load_geometry(P, design=True, **c)
        hv = h_sweep(G, args.quick)
        for opt in ("nail", "backing"):
            for Ev in (El, E):
                o, _, _ = run_cases(G, hv, Ev, nu, option=opt, point=False)
                v = row_from(c, hv, o, Ev, option=opt)
                v["k_tip_at_E"] = v["k_tip"]
                v["vm_cap_tip_tpu"] = v["vm_p99_tip"] * cap
                v["strain_LC1_tip"] = v["strain_p99_tip"] * fb.INPUTS["grip"]["target_N"]
                v["pla_vm_cap_tip_max"] = (v["pla_vm_max_tip"] or 0) * cap
                variants.append(v)

    def variant_ok(c):
        vs = [v for v in variants if _key(v) == c]
        g = fb.INPUTS["grip"]
        chk = {}
        for opt in ("nail", "backing"):
            lo = next(v for v in vs if v["option"] == opt and v["E_solved_MPa"] == El)
            hi = next(v for v in vs if v["option"] == opt and v["E_solved_MPa"] == E)
            chk[opt] = dict(k_tip_E56=lo["k_tip"], k_tip_E67=hi["k_tip"], mass_g=hi["mass_g"],
                            window_ok=bool(lo["k_tip"] >= g["k_tip_min_N_per_mm"] and hi["k_tip"] <= g["k_tip_max_N_per_mm"]),
                            tpu_vm_cap=max(lo["vm_cap_tip_tpu"], hi["vm_cap_tip_tpu"]),
                            tpu_strain_LC1_E56=lo["strain_LC1_tip"],
                            pla_vm_cap_max=max(lo["pla_vm_cap_tip_max"], hi["pla_vm_cap_tip_max"]))
            chk[opt]["tpu_ok"] = bool(chk[opt]["tpu_vm_cap"] <= T["stress_allow_cap_MPa"] and chk[opt]["tpu_strain_LC1_E56"] <= T["strain_limit_LC1"])
            chk[opt]["pla_ok"] = bool(chk[opt]["pla_vm_cap_max"] <= fb.INPUTS["PLA"]["allow_LC2_MPa"])
        return chk

    for r in cands:
        r["D7_variants"] = variant_ok(_key(r))
        r["D7_ok"] = bool(all(v["window_ok"] and v["tpu_ok"] and v["pla_ok"] for v in r["D7_variants"].values()))
    order = lambda r: (not r["mid_ok"], round(r["mass_g"], 2), r["k_log_dist_to_default"])  # noqa: E731
    lin = sorted([r for r in cands if r["feasible_linear"]], key=order)
    pool = [r for r in lin if r["D7_ok"]] or lin
    d7 = "" if (pool and pool[0]["D7_ok"]) else "; a D7 variant fails a linear check (see D7_variants)"
    A_ = [r for r in pool if r["nl_cap_ok"]]
    B_ = [r for r in pool if r["nl_trip_ok"]]
    nl_check = dict(criterion=f"tip-pad nonlinear limit at E {El:g} >= F_cap {cap:g} N (fallback: >= FSR trip {trip:g} N)",
                    F_cap_N=cap, fsr_trip_N=trip, F_target_N=g_["target_N"])
    if A_:
        chosen = A_[0]
        verdict = f"FEASIBLE: linear window/stress/strain pass and the nonlinear tip limit >= {cap:g} N at E {El:g}{d7}"
        nl_check["passed"] = "cap"
    elif B_:
        chosen = B_[0]
        verdict = (f"CONDITIONAL: linear checks pass, but the nonlinear tip-pad limit is {chosen['nl_limit_tip_E56']:.1f} N at E {El:g}, "
                   f"above the {trip:g} N FSR trip and below the {cap:g} N cap: FAILS the R15 fold check; the cap relies on the FSR trip{d7}")
        nl_check["passed"] = "trip only"
    elif pool:
        chosen = max(pool, key=lambda r: r["nl_limit_tip_E56"])
        verdict = (f"FAILS: no screened design holds the {trip:g} N FSR trip without folding; highest limit "
                   f"{chosen['nl_limit_tip_E56']:.1f} N at E {El:g}{d7}")
        nl_check["passed"] = "none"
    else:
        chosen, verdict = (near[0] if near else None), "NO feasible set: nearest in-window design shown (fails the stress and/or strain limit)"
        nl_check["passed"] = "not screened"
    if chosen is not None and "nl_limit_tip_E56" in chosen:
        nl_check["chosen_limit_E56_N"] = chosen["nl_limit_tip_E56"]
    print("variants done;", verdict, round(time.time() - t0, 1), "s", flush=True)

    # 5. recommended finger: fields, exports, nonlinear
    c_rec = _key(chosen) if chosen else {k: P["finger"][k] for k in ("rib_angle", "ribs", "wall", "rib_thickness")}
    Gr = fb.load_geometry(P, design=True, **c_rec)
    rec_lin, M, keep = run_cases(Gr, h, E, nu, fields=True)
    label = (f"Recommended L {Gr['L']:g}: {Gr['n']} ribs at {Gr['beta']:g} deg, wall {Gr['t']:g}, rib {Gr['tr']:g}, "
             f"tip {Gr['tip_width']:g} mm; E {E:g}")
    hn = h_nl_screen(Gr, True) if args.quick else (0.35 if min(Gr["t"], Gr["tr"]) >= 0.875 else min(Gr["t"], Gr["tr"]) / 2.5)
    nlj, nlr = {}, {}
    mesh_n, mat_n = finger_mesh(Gr, hn)
    Mn = Model(mesh_n, E, nu, Gr["D"], clamp_root(Gr))
    for name, s_c, ln in (("tip", Gr["s_tip"], fb.INPUTS["contact"]["patch_tip_mm"]), ("mid", Gr["s_mid"], fb.INPUTS["contact"]["patch_mid_mm"])):
        f, _ = Mn.patch_load(pad_sel(Gr, s_c, ln), 1.0)
        nlj[f"rec_{name}"], nlr[name] = nl_run(Mn, Gr, f, Mn.solve(f), cap * E / El, hn, f"rec {name}")  # to the cap at E 56 (scaled)
    # CAD L 60 tip, for the limit-load bracket (compare with the reviewer's E 26 bracket 3.0-3.5 N by exact E scaling)
    mesh_c, _ = finger_mesh(Gc, 0.35)
    Mc = Model(mesh_c, E, nu, Gc["D"], clamp_root(Gc))
    f, _ = Mc.patch_load(pad_sel(Gc, Gc["s_tip"], fb.INPUTS["contact"]["patch_tip_mm"]), 1.0)
    nlj["cadL60_tip"], rec_c = nl_run(Mc, Gc, f, Mc.solve(f), cap * E / El, 0.35, "CAD L60 tip")
    # finger A with the D7 PLA nail, solved directly at E 56 (PLA does not scale with the TPU modulus)
    mesh_a, mat_a = finger_mesh(Gr, hn, option="nail")
    Ma = Model(mesh_a, El, nu, Gr["D"], clamp_root(Gr), mat=mat_a)
    _, tpla, _ = pla_parts(Gr, "nail")
    f, _ = Ma.patch_load(pad_sel(Gr, Gr["s_tip"], fb.INPUTS["contact"]["patch_tip_mm"], Gr["xf"] + tpla), 1.0)
    nlj["rec_nailA_tip"], rec_a = nl_run(Ma, Gr, f, Ma.solve(f), cap, hn, "rec + nail (A) tip, E 56")
    if chosen is not None and "nl_screen" in chosen:
        nl_check["screen_vs_fine"] = dict(screen_h=chosen["nl_screen"]["h"], screen_limit_E56_N=chosen["nl_limit_tip_E56"],
                                          fine_h=hn, fine_limit_E56_N=nlj["rec_tip"]["last_converged_F_N"] * El / E,
                                          fine_reached_cap=nlj["rec_tip"]["reached_cap"])
    nl_check["rec_bare_tip_limit_E56_N"] = nlj["rec_tip"]["last_converged_F_N"] * El / E
    nl_check["rec_bare_tip_bracket_E56_N"] = [nlj["rec_tip"]["last_converged_F_N"] * El / E,
                                              (nlj["rec_tip"]["smallest_rejected_F_N"] or float("nan")) * El / E]
    nl_check["rec_nailA_tip_limit_E56_N"] = nlj["rec_nailA_tip"]["last_converged_F_N"]
    nl_check["cadL60_tip_limit_E56_N"] = nlj["cadL60_tip"]["last_converged_F_N"] * El / E
    nl_check["mechanism_rec_tip"] = (nlr["tip"].get("mode") or {}).get("mechanism")
    nl_check["mechanism_rec_nailA_tip"] = (rec_a.get("mode") or {}).get("mechanism")
    nl_check["mechanism_cadL60_tip"] = (rec_c.get("mode") or {}).get("mechanism")
    nl_check["hand_back_flank_buckling_rec_E56"] = fb.back_flank_buckling(Gr, El, Gr["s_tip"])
    plot_nl_mode([("recommended, bare, tip pad", Mn, Gr, nlr["tip"]), ("recommended + PLA nail (finger A), tip pad", Ma, Gr, rec_a),
                  ("CAD section L 60, tip pad", Mc, Gc, rec_c)])
    for k in ("rec_tip", "rec_mid", "cadL60_tip"):
        v = nlj[k]
        v["scaled_to_E"] = {f"{Ex:g}": dict(last_converged_F_N=v["last_converged_F_N"] * Ex / E,
                                            smallest_rejected_F_N=(v["smallest_rejected_F_N"] * Ex / E) if v["smallest_rejected_F_N"] else None)
                            for Ex in (El, 26.0, 9.8)}
        v["scaling_note"] = "SVK internal force is linear in E at fixed nu, so load at a given displacement scales exactly with E"
    print("nonlinear done", round(time.time() - t0, 1), "s", flush=True)

    sizes = {}
    for name in ("mid", "tip", "point"):
        f, u, vm = keep[name]
        sizes[f"fea_{name}.json"] = export_json(RESULTS / f"fea_{name}.json", M, name, u, vm, 1.0,
                                                dict(linear=True, geometry=label,
                                                     scale_note="linear fields per 1 N at E 67; displacement x F x 67/E, stress x F"))
    for name in ("mid", "tip"):
        r_ = nlr[name]
        if r_["u_last"] is not None:
            sizes[f"fea_{name}_nl_cap.json"] = export_json(
                RESULTS / f"fea_{name}_nl_cap.json", Mn, name, r_["u_last"], r_["vm_cauchy_last"], r_["F_last"],
                dict(linear=False, geometry=label, F_N_equivalent_at_E56=r_["F_last"] * El / E,
                     stress_measure="Cauchy von Mises (F S F^T / J)", strain_measure="max |principal Green-Lagrange|",
                     scale_note="last converged TL-SVK state at F_N (E 67); the same displacement field is the E 56 state at F_N x 56/67; do not scale linearly"),
                ep_qp=r_["ep_gl_last"])

    # 6. motion (design geometry, recommended finger with the D7 parts)
    kA, kB = {}, {}
    if chosen and "D7_variants" in chosen:
        dv = chosen["D7_variants"]
        kA = {"E56": dv["nail"]["k_tip_E56"], "E67": dv["nail"]["k_tip_E67"]}
        kB = {"E56": dv["backing"]["k_tip_E56"], "E67": dv["backing"]["k_tip_E67"]}
    else:
        kA = {"E56": rec_lin["tip"]["k_N_per_mm"] * El / E, "E67": rec_lin["tip"]["k_N_per_mm"]}
        kB = dict(kA)
    for Ex in T["E_sensitivity_MPa"].values():
        kA[f"E{Ex:g}_scaled"] = kA["E67"] * Ex / E
        kB[f"E{Ex:g}_scaled"] = kB["E67"] * Ex / E
    mot = motion(Gr, kA, kB, (nlj["rec_tip"]["F_N"], nlj["rec_tip"]["patch_disp_mm"]), E)
    mot["finger"] = label
    dump(RESULTS / "finger_motion.json", mot)
    plot_motion(Gr, mot)

    # 7. write sweep, summary, plots
    dump(RESULTS / "fea_sweep.json", dict(
        geometry=f"L {Gd['L']:g} mm, tip pad s {Gd['s_tip']:g} mm (r_c {Gd['rc_tip']:g}), mid s {Gd['s_mid']:g}",
        E_solved_MPa=E, E_band_MPa=[El, E], nu=nu, cap_N=cap, target_N=fb.INPUTS["grip"]["target_N"],
        criteria=assess.__doc__, counts=counts, governing=governing, verdict=verdict, nonlinear_check=nl_check,
        screened=cands,
        recommended=chosen, feasible=feas[:15], nearest_in_window=near, D7_variants=variants, rows=rows))
    plot_sweep(rows, [chosen] if chosen else [], Gd)
    plot_fields(Gr, M, keep, nlr, label, Mn)
    plot_nonlinear(nlj, E)
    summary = dict(inputs_overridden_from_params=used, E_MPa=E, E_low_MPa=El, nu=nu, h_mm=h, validation=val,
                   reference=ref, recommended=dict(set=c_rec, label=label, verdict=verdict, nonlinear_check=nl_check, linear=rec_lin),
                   nonlinear=nlj, export_sizes_bytes=sizes, export_total_bytes=sum(sizes.values()), runtime_s=time.time() - t0)
    dump(RESULTS / "fea_summary.json", summary)
    brief = dict(
        ref={k: dict(k_tip=v["tip"]["k_N_per_mm"], k_mid=v["mid"]["k_N_per_mm"], vm_p99_tip_per_N=v["tip"]["vm_p99_per_N"],
                     wrap_mid=v["mid"]["wrap_ratio"], mass_g=v["mass_g"]) for k, v in ref.items()},
        counts=counts, governing=governing, verdict=verdict, nonlinear_check=nl_check,
        screened=[dict(**_key(r), mass_g=r["mass_g"], k_tip_E56=r["k_tip_E56"], k_tip_E67=r["k_tip_E67"],
                       feasible_linear=r["feasible_linear"], D7_ok=r.get("D7_ok"), nl_limit_E56=r.get("nl_limit_tip_E56")) for r in cands],
        R15=mot["R15_theta_min_check"], nl_fold=mot["nonlinear_fold_check"], recommended=chosen,
        rec_lin_tip=rec_lin["tip"], nonlinear={k: dict(last=v["last_converged_F_N"], rej=v["smallest_rejected_F_N"],
                                                     at_last=v["at_last_converged"], scaled=v.get("scaled_to_E")) for k, v in nlj.items()},
        motion={k: v["summary"] | {"contact": v["contact_theta_deg"]} for k, v in mot["pinch_one_ply_at_tip_pad"].items()},
        sizes=sizes, total=sum(sizes.values()), runtime_s=round(time.time() - t0, 1))
    print(json.dumps(clean(brief), indent=1))


def motion_only():
    """Re-run step 6 from the saved fea_summary.json / fea_sweep.json (no re-solve)."""
    P = fb.load_params()
    fb.apply_overrides(P)
    T = fb.INPUTS["TPU"]
    S = json.loads((RESULTS / "fea_summary.json").read_text(encoding="utf-8"))
    W = json.loads((RESULTS / "fea_sweep.json").read_text(encoding="utf-8"))
    Gr = fb.load_geometry(P, design=True, **S["recommended"]["set"])
    ch = W["recommended"]
    E, El = T["E_nominal_MPa"], T["E_low_MPa"]
    if ch and "D7_variants" in ch:
        dv = ch["D7_variants"]
        kA = {"E56": dv["nail"]["k_tip_E56"], "E67": dv["nail"]["k_tip_E67"]}
        kB = {"E56": dv["backing"]["k_tip_E56"], "E67": dv["backing"]["k_tip_E67"]}
    else:
        k = S["recommended"]["linear"]["tip"]["k_N_per_mm"]
        kA = kB = {"E56": k * El / E, "E67": k}
    for Ex in T["E_sensitivity_MPa"].values():
        kA[f"E{Ex:g}_scaled"] = kA["E67"] * Ex / E
        kB[f"E{Ex:g}_scaled"] = kB["E67"] * Ex / E
    nt = S["nonlinear"]["rec_tip"]
    mot = motion(Gr, kA, kB, (nt["F_N"], nt["patch_disp_mm"]), E)
    mot["finger"] = S["recommended"]["label"]
    dump(RESULTS / "finger_motion.json", mot)
    plot_motion(Gr, mot)
    print(json.dumps(clean(dict(pinch={k: v["summary"] | {"contact": v["contact_theta_deg"]} for k, v in mot["pinch_one_ply_at_tip_pad"].items()},
                                R15=mot["R15_theta_min_check"], nl_fold=mot["nonlinear_fold_check"])), indent=1))


if __name__ == "__main__":
    main()
