#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Genera TODOS los modelos del protocolo de Browning et al. (2007), uno por
carpeta, listos para PredSim:

    <out_root>/gait1018_foot2/gait1018_foot2.osim  (+ Geometry/)
    <out_root>/gait1018_foot4/...
    ...
    <out_root>/gait1018_waist16/...

Requiere add_mass_load.py en la misma carpeta.

Uso:
    python make_all_conditions.py --src C:\\PredSim\\exo_project\\Subjects\\gait1018\\gait1018.osim ^
                                  --out_root C:\\PredSim\\exo_project\\Subjects\\gait1018_pesas_2007
    (opcional)  --only shank2 shank4      para generar solo algunos
"""
import os
import argparse
import opensim as osim
from add_mass_load import CONDITIONS, apply_loads


def build(src, out_root, cond, visual="mesh", axis="y"):
    name = "gait1018_" + cond
    out_dir = os.path.join(out_root, name)
    os.makedirs(out_dir, exist_ok=True)
    geom_dir = os.path.join(out_dir, "Geometry")

    model = osim.Model(src)                      # modelo limpio para cada condicion
    apply_loads(model, CONDITIONS[cond], geometry_dir=geom_dir, long_axis=axis,
                add_visual=(visual != "none"),
                visual=("mesh" if visual == "none" else visual))
    model.setName(name)
    model.finalizeConnections()
    state = model.initSystem()
    total = model.getTotalMass(state)

    dst = os.path.join(out_dir, name + ".osim")
    model.printToXML(dst)
    added = sum(L["mass"] for L in CONDITIONS[cond])
    return dst, added, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="gait1018.osim original")
    ap.add_argument("--out_root", required=True, help="carpeta donde crear una subcarpeta por condicion")
    ap.add_argument("--only", nargs="*", default=None, help="condiciones a generar (default: todas)")
    ap.add_argument("--visual", default="mesh", choices=["mesh", "cylinder", "none"])
    ap.add_argument("--axis", default="y")
    args = ap.parse_args()

    conds = args.only if args.only else list(CONDITIONS.keys())
    print("%-10s %12s %14s  %s" % ("condicion", "agregada[kg]", "masa total[kg]", "archivo"))
    for c in conds:
        dst, added, total = build(args.src, args.out_root, c, args.visual, args.axis)
        print("%-10s %12.2f %14.3f  %s" % (c, added, total, dst))


if __name__ == "__main__":
    main()
