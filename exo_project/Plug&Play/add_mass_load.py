#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
add_mass_load.py
================
Agrega carga de masa (cilindro hueco) a segmentos de un modelo OpenSim,
siguiendo las condiciones de Browning et al. (2007), y genera la malla
(.stl / .vtp) del cilindro para verificarla visualmente.

Modelo fisico
-------------
La masa agregada se modela como un cilindro hueco (radio interno r1 = radio de
la extremidad, radio externo r2, altura h) centrado EXACTAMENTE en el centro de
masa (CoM) del segmento  ->  d = 0, el CoM del segmento no se mueve y el
teorema de ejes paralelos no agrega terminos.

    m_nuevo = m_original + m_agregada
    I_long  = 0.5 * m * (r1^2 + r2^2)                    (eje del cilindro)
    I_trans = (1/12) * m * (3*(r1^2 + r2^2) + h^2)       (ejes perpendiculares)

Nota OpenSim: el tensor de inercia de un Body esta expresado en el marco del
cuerpo y calculado respecto a su centro de masa, por eso se suma directamente.
El eje largo del cilindro se alinea con el eje largo del segmento (Y en
gait1018 / gait2392 para pelvis, femur y tibia).

Uso rapido
----------
    python add_mass_load.py --src gait1018_exo.osim --dst gait1018_exo_load.osim \
                            --condition shank4
"""

import os
import argparse
import numpy as np
import opensim as osim


# ----------------------------------------------------------------------------
# 1. Inercia analitica del cilindro hueco
# ----------------------------------------------------------------------------
def hollow_cylinder_inertia(m, r1, r2, h, long_axis="y"):
    """Devuelve (Ixx, Iyy, Izz) del cilindro hueco respecto a su propio CoM,
    expresado en el marco del cuerpo (eje del cilindro = long_axis)."""
    I_long = 0.5 * m * (r1 ** 2 + r2 ** 2)
    I_trans = (1.0 / 12.0) * m * (3.0 * (r1 ** 2 + r2 ** 2) + h ** 2)
    diag = {"x": (I_long, I_trans, I_trans),
            "y": (I_trans, I_long, I_trans),
            "z": (I_trans, I_trans, I_long)}
    return diag[long_axis.lower()]


# ----------------------------------------------------------------------------
# 2. Malla del cilindro hueco (STL ascii + VTP ascii, sin dependencia de VTK)
# ----------------------------------------------------------------------------
def hollow_cylinder_mesh(r1, r2, h, n=64, long_axis="y"):
    """Vertices (N,3) y triangulos (M,3) de un cilindro hueco centrado en el
    origen, con normales hacia afuera. Unidades: metros."""
    th = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    cs, sn = np.cos(th), np.sin(th)
    hh = h / 2.0
    ot = np.c_[r2 * cs, np.full(n, hh), r2 * sn]      # exterior arriba
    ob = np.c_[r2 * cs, np.full(n, -hh), r2 * sn]     # exterior abajo
    it = np.c_[r1 * cs, np.full(n, hh), r1 * sn]      # interior arriba
    ib = np.c_[r1 * cs, np.full(n, -hh), r1 * sn]     # interior abajo
    V = np.vstack([ot, ob, it, ib])
    OT, OB, IT, IB = 0, n, 2 * n, 3 * n

    tris = []

    def add(a, b, c, kind):
        pa, pb, pc = V[a], V[b], V[c]
        nrm = np.cross(pb - pa, pc - pa)
        cen = (pa + pb + pc) / 3.0
        radial = np.array([cen[0], 0.0, cen[2]])
        expected = {"out": radial, "in": -radial,
                    "top": np.array([0.0, 1.0, 0.0]),
                    "bot": np.array([0.0, -1.0, 0.0])}[kind]
        if np.dot(nrm, expected) < 0:
            b, c = c, b
        tris.append((a, b, c))

    for i in range(n):
        j = (i + 1) % n
        add(OT + i, OB + i, OB + j, "out"); add(OT + i, OB + j, OT + j, "out")
        add(IT + i, IB + i, IB + j, "in");  add(IT + i, IB + j, IT + j, "in")
        add(OT + i, OT + j, IT + j, "top"); add(OT + i, IT + j, IT + i, "top")
        add(OB + i, OB + j, IB + j, "bot"); add(OB + i, IB + j, IB + i, "bot")

    # Permutaciones ciclicas: preservan la orientacion de las caras
    ax = long_axis.lower()
    if ax == "x":
        V = V[:, [1, 2, 0]]
    elif ax == "z":
        V = V[:, [2, 0, 1]]
    return V, np.array(tris, dtype=int)


def _register_geometry_dir(folder):
    """Le dice a OpenSim donde buscar las mallas MIENTRAS se arma el modelo
    (el modelo se carga desde otra carpeta que el .osim de salida)."""
    try:
        osim.ModelVisualizer.addDirToGeometrySearchPaths(os.path.abspath(folder))
    except Exception:
        pass


def write_stl(path, V, T, name="hollow_cylinder"):
    _register_geometry_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "w") as f:
        f.write("solid %s\n" % name)
        for a, b, c in T:
            nrm = np.cross(V[b] - V[a], V[c] - V[a])
            nn = np.linalg.norm(nrm)
            nrm = nrm / nn if nn > 0 else nrm
            f.write("  facet normal %.6e %.6e %.6e\n    outer loop\n" % tuple(nrm))
            for k in (a, b, c):
                f.write("      vertex %.6e %.6e %.6e\n" % tuple(V[k]))
            f.write("    endloop\n  endfacet\n")
        f.write("endsolid %s\n" % name)


def write_vtp(path, V, T):
    _register_geometry_dir(os.path.dirname(os.path.abspath(path)))
    npts, ntri = len(V), len(T)
    with open(path, "w") as f:
        f.write('<?xml version="1.0"?>\n')
        f.write('<VTKFile type="PolyData" version="0.1" byte_order="LittleEndian">\n')
        f.write(' <PolyData>\n')
        f.write('  <Piece NumberOfPoints="%d" NumberOfVerts="0" NumberOfLines="0" '
                'NumberOfStrips="0" NumberOfPolys="%d">\n' % (npts, ntri))
        f.write('   <Points>\n    <DataArray type="Float32" NumberOfComponents="3" format="ascii">\n')
        for p in V:
            f.write("     %.7e %.7e %.7e\n" % tuple(p))
        f.write('    </DataArray>\n   </Points>\n   <Polys>\n')
        f.write('    <DataArray type="Int32" Name="connectivity" format="ascii">\n')
        for t in T:
            f.write("     %d %d %d\n" % tuple(t))
        f.write('    </DataArray>\n')
        f.write('    <DataArray type="Int32" Name="offsets" format="ascii">\n     ')
        f.write(" ".join(str(3 * (i + 1)) for i in range(ntri)))
        f.write('\n    </DataArray>\n   </Polys>\n  </Piece>\n </PolyData>\n</VTKFile>\n')


# ----------------------------------------------------------------------------
# 3. Funcion principal: agregar masa a un cuerpo
# ----------------------------------------------------------------------------
def add_hollow_cylinder_mass(model, body_name, added_mass, r_inner, r_outer,
                             height, long_axis="y", add_visual=True,
                             visual="mesh", geometry_dir=None, mesh_format="vtp",
                             opacity=0.35, color=(1.0, 0.4, 0.0), n_seg=64,
                             tag=None):
    """
    Modifica IN PLACE el Body `body_name` del Model.

    Parametros
    ----------
    added_mass : kg a agregar (ej. 4 pantorrilla, 8 muslo)
    r_inner    : radio interno [m] (radio aprox. de la extremidad)
    r_outer    : radio externo [m]
    height     : altura del cilindro [m] (a lo largo del eje largo)
    long_axis  : eje del segmento en el marco del cuerpo ('y' en gait1018)
    visual     : 'mesh' (cilindro HUECO, .vtp/.stl generado) o
                 'cylinder' (primitiva solida de OpenSim, translucida)
    geometry_dir : carpeta donde se guarda la malla (junto al .osim: .../Geometry)
    """
    if added_mass <= 0:
        return None
    if r_outer <= r_inner:
        raise ValueError("r_outer debe ser mayor que r_inner")

    body = model.updBodySet().get(body_name)

    # --- estado original ---------------------------------------------------
    m0 = body.get_mass()
    com = body.get_mass_center()
    com = osim.Vec3(com.get(0), com.get(1), com.get(2))      # copia
    I0 = body.get_inertia()                                  # Vec6
    I0 = [I0.get(i) for i in range(6)]                       # Ixx Iyy Izz Ixy Ixz Iyz

    # --- inercia del cilindro (d = 0 -> sin termino de ejes paralelos) -----
    Ixx, Iyy, Izz = hollow_cylinder_inertia(added_mass, r_inner, r_outer,
                                            height, long_axis)

    # --- actualizacion de parametros ----------------------------------------
    m_new = m0 + added_mass
    I_new = [I0[0] + Ixx, I0[1] + Iyy, I0[2] + Izz, I0[3], I0[4], I0[5]]
    body.set_mass(m_new)
    body.set_inertia(osim.Vec6(*I_new))
    # mass_center NO se toca: el cilindro esta centrado en el CoM (d = 0)

    # --- visualizacion -------------------------------------------------------
    mesh_file = None
    if add_visual:
        tag = tag or ("load_%s" % body_name)
        pof = osim.PhysicalOffsetFrame(tag + "_frame", body, osim.Transform(com))

        if visual == "mesh":
            V, T = hollow_cylinder_mesh(r_inner, r_outer, height, n_seg, long_axis)
            geometry_dir = geometry_dir or "."
            os.makedirs(geometry_dir, exist_ok=True)
            mesh_file = tag + "." + mesh_format
            full = os.path.join(geometry_dir, mesh_file)
            (write_vtp if mesh_format == "vtp" else write_stl)(full, V, T)
            # copia en el otro formato por comodidad (para abrir en MeshLab, etc.)
            other = "stl" if mesh_format == "vtp" else "vtp"
            (write_stl if other == "stl" else write_vtp)(
                os.path.join(geometry_dir, tag + "." + other), V, T)
            geom = osim.Mesh(mesh_file)
        else:
            geom = osim.Cylinder(r_outer, height / 2.0)       # eje Y, solido
            if long_axis.lower() == "x":
                pof.set_orientation(osim.Vec3(0, 0, -np.pi / 2))
            elif long_axis.lower() == "z":
                pof.set_orientation(osim.Vec3(np.pi / 2, 0, 0))

        geom.upd_Appearance().set_color(osim.Vec3(*color))
        geom.upd_Appearance().set_opacity(opacity)
        pof.attachGeometry(geom)           # solo visual: no afecta la dinamica
        model.addComponent(pof)

    return dict(body=body_name, m_old=m0, m_new=m_new, com=(com.get(0), com.get(1), com.get(2)),
                I_old=I0, I_new=I_new, I_long=0.5 * added_mass * (r_inner**2 + r_outer**2),
                mesh=mesh_file)


def apply_loads(model, loads, geometry_dir=None, **kwargs):
    """loads: lista de dicts con claves body, mass, r_inner, r_outer, height."""
    out = []
    for L in loads:
        if "d" in L:    # carga dividida (pie: talon + dorso)
            kw = {k: v for k, v in kwargs.items()
                  if k in ("add_visual", "mesh_format", "opacity", "color", "n_seg")}
            out.append(add_split_hollow_mass(
                model, L["body"], L["mass"], L["d"], L["r_inner"], L["r_outer"],
                L["height"], geometry_dir=geometry_dir, tag=L.get("tag"), **kw))
        else:
            out.append(add_hollow_cylinder_mass(
                model, L["body"], L["mass"], L["r_inner"], L["r_outer"], L["height"],
                geometry_dir=geometry_dir, tag=L.get("tag"), **kwargs))
    return out


def add_split_hollow_mass(model, body_name, total_mass, d, r_inner, r_outer,
                          height, offset_axis="x", long_axis="y",
                          add_visual=True, geometry_dir=None, mesh_format="vtp",
                          opacity=0.35, color=(1.0, 0.4, 0.0), n_seg=64, tag=None):
    """
    Dos cargas iguales (total_mass/2 c/u) a +d y -d del CoM a lo largo de
    `offset_axis` (carga de pie de Browning 2007: talon detras y dorso delante,
    equidistantes del CoM). El CoM del segmento NO cambia, pero SI hay termino
    de ejes paralelos:  I += 2 * m_lump * d^2  en los ejes perpendiculares a
    offset_axis (los productos de inercia se anulan por simetria).
    Cada carga se aproxima como un anillo hueco (r_inner, r_outer, height).
    """
    body = model.updBodySet().get(body_name)
    m_lump = total_mass / 2.0
    m0 = body.get_mass()
    com = body.get_mass_center()
    com = osim.Vec3(com.get(0), com.get(1), com.get(2))
    I0 = body.get_inertia()
    I0 = [I0.get(i) for i in range(6)]

    Ixx, Iyy, Izz = hollow_cylinder_inertia(m_lump, r_inner, r_outer, height, long_axis)
    d2 = d ** 2
    par = {"x": (0.0, d2, d2), "y": (d2, 0.0, d2), "z": (d2, d2, 0.0)}[offset_axis.lower()]
    own = (Ixx, Iyy, Izz)
    I_new = [I0[i] + 2.0 * (own[i] + m_lump * par[i]) for i in range(3)] + I0[3:]

    body.set_mass(m0 + total_mass)
    body.set_inertia(osim.Vec6(*I_new))

    mesh_file = None
    if add_visual:
        tag = tag or ("load_%s" % body_name)
        V, T = hollow_cylinder_mesh(r_inner, r_outer, height, n_seg, long_axis)
        geometry_dir = geometry_dir or "."
        os.makedirs(geometry_dir, exist_ok=True)
        mesh_file = tag + "." + mesh_format
        write_vtp(os.path.join(geometry_dir, tag + ".vtp"), V, T)
        write_stl(os.path.join(geometry_dir, tag + ".stl"), V, T)
        idx = {"x": 0, "y": 1, "z": 2}[offset_axis.lower()]
        for sgn, nm in ((+1, "front"), (-1, "back")):
            p = [com.get(0), com.get(1), com.get(2)]
            p[idx] += sgn * d
            pof = osim.PhysicalOffsetFrame("%s_%s_frame" % (tag, nm), body,
                                           osim.Transform(osim.Vec3(*p)))
            geom = osim.Mesh(mesh_file)
            geom.upd_Appearance().set_color(osim.Vec3(*color))
            geom.upd_Appearance().set_opacity(opacity)
            pof.attachGeometry(geom)
            model.addComponent(pof)

    return dict(body=body_name, m_old=m0, m_new=m0 + total_mass,
                com=(com.get(0), com.get(1), com.get(2)),
                I_old=I0, I_new=I_new, mesh=mesh_file)


# ----------------------------------------------------------------------------
# 4. Condiciones del protocolo de Browning et al. (2007)
#    Piernas: masa POR EXTREMIDAD (foot/shank 2 y 4 kg, thigh 4 y 8 kg).
#    Cintura: masa TOTAL (4, 8 y 16 kg).
#    Radios, alturas y d son ESTIMACIONES: ajustalos a tu sujeto/modelo.
# ----------------------------------------------------------------------------
RHO_LEAD = 11340.0   # kg/m^3 (plomo)


def r_outer_from_mass(mass, r_inner, height, rho=RHO_LEAD):
    """r_outer tal que el cilindro hueco (r_inner, r_outer, height) tenga el
    volumen de `mass` kg de plomo: V = pi*h*(r2^2 - r1^2).
    (r_outer - r_inner) / 3.175 mm ~ numero de capas de lamina de 0.125 in."""
    return float(np.sqrt(r_inner ** 2 + mass / (rho * np.pi * height)))


def _L(body, mass, r_inner, height, **extra):
    return dict(body=body, mass=mass, r_inner=r_inner, height=height,
                r_outer=r_outer_from_mass(extra.pop("lump", mass), r_inner, height),
                **extra)


CONDITIONS = {"none": []}
for _m in (2.0, 4.0):                                  # foot y shank, por pierna
    CONDITIONS["shank%d" % _m] = [_L(b, _m, 0.057, 0.15) for b in ("tibia_r", "tibia_l")]
    # pie: talon + dorso equidistantes del CoM (d estimado = 0.06 m), _m/2 c/u
    CONDITIONS["foot%d" % _m] = [_L(b, _m, 0.04, 0.05, d=0.06, lump=_m / 2.0)
                                 for b in ("calcn_r", "calcn_l")]
for _m in (4.0, 8.0):                                  # muslo, por pierna
    CONDITIONS["thigh%d" % _m] = [_L(b, _m, 0.088, 0.15) for b in ("femur_r", "femur_l")]
for _m in (4.0, 8.0, 16.0):                            # cintura, total
    CONDITIONS["waist%d" % _m] = [_L("pelvis", _m, 0.135, 0.10)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help=".osim de entrada")
    ap.add_argument("--dst", required=True, help=".osim de salida")
    ap.add_argument("--condition", default="shank4", choices=CONDITIONS.keys())
    ap.add_argument("--visual", default="mesh", choices=["mesh", "cylinder", "none"])
    ap.add_argument("--axis", default="y")
    args = ap.parse_args()

    model = osim.Model(args.src)
    total0 = sum(model.getBodySet().get(i).get_mass()
                 for i in range(model.getBodySet().getSize()))

    geom_dir = os.path.join(os.path.dirname(os.path.abspath(args.dst)), "Geometry")
    res = apply_loads(model, CONDITIONS[args.condition], geometry_dir=geom_dir,
                      long_axis=args.axis, add_visual=(args.visual != "none"),
                      visual=("mesh" if args.visual == "none" else args.visual))

    for r in res:
        if r:
            print("%-9s  m: %.3f -> %.3f kg | Ixx,Iyy,Izz: %.5f %.5f %.5f -> %.5f %.5f %.5f"
                  % (r["body"], r["m_old"], r["m_new"], *r["I_old"][:3], *r["I_new"][:3]))

    model.setName(model.getName() + "_" + args.condition)
    model.finalizeConnections()
    state = model.initSystem()
    total1 = model.getTotalMass(state)
    added = sum(L["mass"] for L in CONDITIONS[args.condition])
    print("Masa total (suma de bodies) antes: %.3f kg | modelo ahora: %.3f kg | agregada: %.3f kg"
          % (total0, total1, added))
    model.printToXML(args.dst)
    print("Guardado:", args.dst)


if __name__ == "__main__":
    main()