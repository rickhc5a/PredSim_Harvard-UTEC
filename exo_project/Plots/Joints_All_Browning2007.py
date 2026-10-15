"""
Joints_All_Browning2007.py
--------------------------
Grafica TODAS las coordenadas articulares de los .mot de PredSim para las
condiciones de carga de Browning et al. (2007), una comparacion por ubicacion
de la carga (sin exoesqueleto):

    Foot  : sin carga vs 2 kg/pierna vs 4 kg/pierna
    Shank : sin carga vs 2 kg/pierna vs 4 kg/pierna
    Thigh : sin carga vs 4 kg/pierna vs 8 kg/pierna
    Waist : sin carga vs 4 kg vs 8 kg vs 16 kg (total)

Genera un PDF multipagina por ubicacion (Joints_Browning2007_<Ubicacion>.pdf)
con el mismo estilo que Joints_All_Baseline_vs_Exo.py: coordenadas agrupadas
por region, 8 graficos por pagina, eje X normalizado al ciclo (%), marca de
Toe-Off.

Espera los resultados de run_browning2007_batch.m en:
    <ROOT>\<condicion>\*.mot     (none, foot2, foot4, shank2, ... waist16)
Si una condicion no tiene .mot, se omite con un aviso.

Requiere: numpy, pandas, matplotlib (no necesita opensim).
Uso:  python Joints_All_Browning2007.py
"""

import os
import glob
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# ============================================================
# CONFIGURACION
# ============================================================
ROOT = r'C:\PredSim\exo_project\PredSimResults\Browning2007'

BASELINE = ('No load', 'none', '#000000', '--')

# ubicacion -> lista de (leyenda, subcarpeta, color, estilo)
SETS = {
    'Foot': [BASELINE,
             ('2 kg/leg', 'foot2', '#1f77b4', '-'),
             ('4 kg/leg', 'foot4', '#d62728', '-')],
    'Shank': [BASELINE,
              ('2 kg/leg', 'shank2', '#1f77b4', '-'),
              ('4 kg/leg', 'shank4', '#d62728', '-')],
    'Thigh': [BASELINE,
              ('4 kg/leg', 'thigh4', '#1f77b4', '-'),
              ('8 kg/leg', 'thigh8', '#d62728', '-')],
    'Waist': [BASELINE,
              ('4 kg', 'waist4', '#2ca02c', '-'),
              ('8 kg', 'waist8', '#ff7f0e', '-'),
              ('16 kg', 'waist16', '#d62728', '-')],
}

EXCLUDE = []            # p. ej. ['mtp_angle_r', 'mtp_angle_l']

# Limites fijos opcionales (min, max). Si no esta la coordenada -> autoescala.
Y_LIMITS = {
    # 'pelvis_ty':     (0.87, 0.95),
    # 'knee_angle_r':  (0, 80),
}

FLIP_KNEE    = True     # invierte el signo de knee_angle (igual que en tu script anterior)
TOE_OFF_PCT  = 60.0     # marca fija de referencia (varia algo entre condiciones)
MAX_PER_PAGE = 8        # 4 filas x 2 columnas
COLS         = 2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
plt.rcParams['pdf.fonttype'] = 42   # texto editable en el PDF

PREFERRED = [
    'pelvis_tilt', 'pelvis_list', 'pelvis_rotation', 'pelvis_tx', 'pelvis_ty', 'pelvis_tz',
    'lumbar_extension', 'lumbar_bending', 'lumbar_rotation',
    'hip_flexion', 'hip_adduction', 'hip_rotation',
    'knee_angle', 'ankle_angle', 'subtalar_angle', 'mtp_angle',
]
GROUP_ORDER = ['Pelvis', 'Trunk (lumbar)', 'Right side', 'Left side', 'Other']


# ============================================================
# LECTURA DE .mot
# ============================================================
def read_mot(path):
    """Devuelve (DataFrame, in_degrees). Respeta 'inDegrees=no' del header."""
    in_deg = True
    n_header = 0
    with open(path, 'r') as f:
        for line in f:
            n_header += 1
            if 'indegrees=no' in line.lower():
                in_deg = False
            if line.strip().lower() == 'endheader':
                break
        else:
            raise ValueError(f'No se encontro "endheader" en {path}')
    df = pd.read_csv(path, sep=r'\s+', skiprows=n_header)
    return df, in_deg


def latest_mot(folder):
    files = glob.glob(os.path.join(folder, '*.mot'))
    return max(files, key=os.path.getmtime) if files else None


def load_conditions(conditions):
    data = []
    for label, sub, color, style in conditions:
        folder = os.path.join(ROOT, sub)
        f = latest_mot(folder)
        if f is None:
            print(f'[AVISO] Sin .mot en {folder} -> se omite "{label}"')
            continue
        print(f'{label} -> {f}')
        df, in_deg = read_mot(f)
        t = df['time'].to_numpy()
        pct = (t - t[0]) / (t[-1] - t[0]) * 100
        data.append(dict(label=label, df=df, in_deg=in_deg, pct=pct,
                         color=color, style=style))
    return data


# ============================================================
# AGRUPACION DE COORDENADAS
# ============================================================
def group_of(c):
    if c.startswith('pelvis_'):
        return 'Pelvis'
    if c.startswith('lumbar_'):
        return 'Trunk (lumbar)'
    if c.endswith('_r'):
        return 'Right side'
    if c.endswith('_l'):
        return 'Left side'
    return 'Other'


def sort_key(c):
    base = c[:-2] if c.endswith(('_r', '_l')) else c
    return (PREFERRED.index(base) if base in PREFERRED else 999, c)


def build_pages(data):
    coords = []
    for d in data:
        for c in d['df'].columns:
            if c == 'time' or c in EXCLUDE or c in coords:
                continue
            if not pd.api.types.is_numeric_dtype(d['df'][c]):
                continue
            coords.append(c)
    groups = {g: sorted([c for c in coords if group_of(c) == g], key=sort_key)
              for g in GROUP_ORDER}
    pages = []
    for g in GROUP_ORDER:
        cs = groups[g]
        n_pages = math.ceil(len(cs) / MAX_PER_PAGE)
        for p in range(n_pages):
            chunk = cs[p * MAX_PER_PAGE:(p + 1) * MAX_PER_PAGE]
            suffix = f' ({p + 1}/{n_pages})' if n_pages > 1 else ''
            pages.append((g + suffix, chunk))
    return coords, pages


# ============================================================
# DIBUJO DE UN SUBPLOT
# ============================================================
def draw_coord(ax, coord, data, show_legend):
    is_trans = coord.endswith(('_tx', '_ty', '_tz'))

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(1.2)
    ax.spines['bottom'].set_linewidth(1.2)

    ys = []
    for d in data:
        df = d['df']
        if coord not in df.columns:
            print(f'[AVISO] {coord} no esta en {d["label"]}')
            continue
        y = df[coord].to_numpy().astype(float)
        if not is_trans and not d['in_deg']:
            y = np.rad2deg(y)
        if FLIP_KNEE and 'knee_angle' in coord:
            y = -y
        ys.append(y)
        ax.plot(d['pct'], y, label=d['label'], color=d['color'],
                linestyle=d['style'], linewidth=2.0 if d['style'] == '-' else 1.8,
                zorder=5 if d['style'] == '--' else 4)

    if coord in Y_LIMITS:
        ymin, ymax = Y_LIMITS[coord]
        pad = 0.02 if is_trans else 2
        ax.set_ylim(ymin - pad, ymax + pad)
        ax.set_yticks([ymin, 0, ymax] if ymin < 0 < ymax else [ymin, ymax])
    elif ys:
        lo = min(np.nanmin(y) for y in ys)
        hi = max(np.nanmax(y) for y in ys)
        tol = 1e-4 if is_trans else 1e-2
        if hi - lo < tol:
            c, p = (lo + hi) / 2, (0.01 if is_trans else 1.0)
            ax.set_ylim(c - p, c + p)

    lo, hi = ax.get_ylim()
    if lo < 0 < hi:
        ax.axhline(0, color='gray', linestyle='--', linewidth=0.8, alpha=0.5, zorder=0)

    ax.set_xlim(0, 100)
    ax.set_xticks([0, 50, 100])
    ax.set_xticklabels(['0', '50', '100'])
    ax.tick_params(axis='x', length=5, direction='out')
    trans = ax.get_xaxis_transform()
    for dx in (-0.5, 0.5):
        ax.plot([TOE_OFF_PCT + dx, TOE_OFF_PCT + dx], [-0.05, 0.05],
                transform=trans, color='black', linewidth=0.7, clip_on=False)
    ax.text(TOE_OFF_PCT, -0.08, 'Toe-Off', transform=trans,
            ha='center', va='top', fontsize=9)

    ax.tick_params(axis='y', length=5, direction='out')
    ax.grid(False)
    ax.set_title(coord, fontweight='bold', fontsize=12)
    ax.set_xlabel('Gait Cycle (%)', labelpad=18)
    ax.set_ylabel('Position (m)' if is_trans else 'Angle (deg)')
    if show_legend:
        ax.legend(fontsize=9, frameon=False)


# ============================================================
# PDF POR UBICACION
# ============================================================
for set_name, conditions in SETS.items():
    print(f'\n=== {set_name} ===')
    data = load_conditions(conditions)
    if len(data) < 2:
        print(f'[AVISO] {set_name}: menos de 2 condiciones con datos, se omite.')
        continue

    coords, pages = build_pages(data)
    out_pdf = os.path.join(SCRIPT_DIR, f'Joints_Browning2007_{set_name}.pdf')
    title = f'Kinematics: {set_name} loading (Browning et al. 2007)'
    print(f'{len(coords)} coordenadas en {len(pages)} paginas.')

    with PdfPages(out_pdf) as pdf:
        for page_title, cs in pages:
            rows = math.ceil(len(cs) / COLS)
            fig, axes = plt.subplots(rows, COLS, figsize=(15, 3.6 * rows + 0.8))
            axes = np.atleast_1d(axes).flatten()
            for i, coord in enumerate(cs):
                draw_coord(axes[i], coord, data, show_legend=(i == 0))
            for j in range(len(cs), len(axes)):
                fig.delaxes(axes[j])
            fig.tight_layout(rect=[0, 0.02, 1, 0.95])
            fig.suptitle(f'{title}  -  {page_title}', fontsize=16,
                         fontweight='bold', y=0.985)
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
    print(f'Guardado: {out_pdf}')
