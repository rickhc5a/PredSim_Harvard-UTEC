"""
Joints_Baseline_vs_Exo.py
-------------------------
Compara la cinematica articular de PredSim (.mot): Baseline vs Exo.
Mismo estilo que Joints.py (spines solo left/bottom, marca de Toe-Off, 300 dpi),
con el eje X normalizado al ciclo de marcha (%).

Para cambiar condiciones: edita CONDITIONS.
Para cambiar coordenadas: edita COORDS_TO_PLOT.
Para fijar limites del eje Y: edita Y_LIMITS (si una coordenada no esta, usa autoescala).

Requiere: numpy, pandas, matplotlib (no necesita opensim).
Uso:
    python Joints_Baseline_vs_Exo.py
Guarda PNG (300 dpi), PDF y SVG junto al script.
"""

import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================
# CONFIGURACION
# ============================================================
ROOT = r'C:\PredSim\exo_project\PredSimResults'

# (leyenda, subcarpeta con el .mot, color, estilo de linea)
CONDITIONS = [
    ('baseline',              'gait1018', '#000000', '--'),   # Baseline (SO1)
    ('exoPatrickMassInercia', 'SO4',      '#d95319', '-'),    # Exo con masa/inercia y torque ideal
]

COORDS_TO_PLOT = [
    'pelvis_ty', 'pelvis_tilt', 'hip_flexion_r',
    'knee_angle_r', 'ankle_angle_r', 'lumbar_extension',
]

Y_LABELS = {
    'pelvis_ty':        'Position (m)',
    'pelvis_tilt':      'Angle (deg)',
    'hip_flexion_r':    'Angle (deg)',
    'knee_angle_r':     'Angle (deg)',
    'ankle_angle_r':    'Angle (deg)',
    'lumbar_extension': 'Angle (deg)',
}

# Limites fijos opcionales (min, max). Si no esta la coordenada -> autoescala.
Y_LIMITS = {
    # 'pelvis_ty':     (0.87, 0.95),
    # 'knee_angle_r':  (0, 80),
    # 'ankle_angle_r': (-30, 15),
    # 'hip_flexion_r': (-20, 50),
}

FLIP_KNEE   = True    # el signo de la rodilla se invierte (igual que en tu MATLAB y Joints.py)
TOE_OFF_PCT = 60.0

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_BASE   = os.path.join(SCRIPT_DIR, 'Joints_Baseline_vs_ExoPatrick')

plt.rcParams['pdf.fonttype'] = 42   # texto editable en el PDF (Illustrator, etc.)
plt.rcParams['svg.fonttype'] = 'none'


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
    if not files:
        return None
    return max(files, key=os.path.getmtime)


data = []   # lista de dicts por condicion
for label, sub, color, style in CONDITIONS:
    folder = os.path.join(ROOT, sub)
    f = latest_mot(folder)
    if f is None:
        print(f'[AVISO] Sin .mot en {folder}')
        continue
    print(f'{label} -> {f}')
    df, in_deg = read_mot(f)
    t = df['time'].to_numpy()
    pct = (t - t[0]) / (t[-1] - t[0]) * 100
    data.append(dict(label=label, df=df, in_deg=in_deg, pct=pct, color=color, style=style))

if not data:
    raise SystemExit('No se cargo ninguna condicion. Revisa ROOT y CONDITIONS.')


# ============================================================
# VISUALIZACION - estilo publicacion
# ============================================================
num_plots = len(COORDS_TO_PLOT)
cols = 2
rows = (num_plots + 1) // cols

fig, axes = plt.subplots(rows, cols, figsize=(15, 4 * rows))
axes = np.atleast_1d(axes).flatten()

for i, coord in enumerate(COORDS_TO_PLOT):
    ax = axes[i]

    # Spines: solo left + bottom
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(1.2)
    ax.spines['bottom'].set_linewidth(1.2)

    # Linea horizontal en y=0 (punteada, sutil)
    ax.axhline(0, color='gray', linestyle='--', linewidth=0.8, alpha=0.5, zorder=0)

    plotted = False
    for d in data:
        df = d['df']
        if coord not in df.columns:
            print(f'[AVISO] {coord} no esta en {d["label"]}')
            continue

        y = df[coord].to_numpy()
        is_trans = coord.endswith(('_tx', '_ty', '_tz'))
        if not is_trans and not d['in_deg']:
            y = np.rad2deg(y)
        if FLIP_KNEE and 'knee_angle' in coord:
            y = -y

        ax.plot(d['pct'], y, label=d['label'], color=d['color'],
                linestyle=d['style'], linewidth=2.0 if d['style'] == '-' else 1.8,
                zorder=5 if d['style'] == '--' else 4)
        plotted = True

    if not plotted:
        ax.set_title(f'{coord} (no encontrado)')
        continue

    # ---- EJE X: 0, 50, 100 + marca de Toe-Off ----
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 50, 100])
    ax.set_xticklabels(['0', '50', '100'])
    ax.tick_params(axis='x', length=5, direction='out')

    trans = ax.get_xaxis_transform()   # x = datos, y = ejes
    for dx in (-0.5, 0.5):
        ax.plot([TOE_OFF_PCT + dx, TOE_OFF_PCT + dx], [-0.05, 0.05],
                transform=trans, color='black', linewidth=0.7, clip_on=False)
    ax.text(TOE_OFF_PCT, -0.08, 'Toe-Off', transform=trans,
            ha='center', va='top', fontsize=9)

    # ---- EJE Y ----
    if coord in Y_LIMITS:
        ymin, ymax = Y_LIMITS[coord]
        pad = 0.02 if coord.endswith(('_tx', '_ty', '_tz')) else 2
        ax.set_ylim(ymin - pad, ymax + pad)
        ax.set_yticks([ymin, 0, ymax] if ymin < 0 < ymax else [ymin, ymax])
    ax.tick_params(axis='y', length=5, direction='out')

    ax.grid(False)

    # ---- LABELS ----
    ax.set_title(coord, fontweight='bold', fontsize=12)
    ax.set_xlabel('Gait Cycle (%)', labelpad=18)
    ax.set_ylabel(Y_LABELS.get(coord, 'Value'))

    if i == 0:
        ax.legend(fontsize=9, frameon=False)

# Quitar subplots vacios
for j in range(num_plots, len(axes)):
    fig.delaxes(axes[j])

plt.tight_layout(rect=[0, 0.02, 1, 0.96])
plt.suptitle('Kinematics: Baseline vs Exo Patrick', fontsize=16, fontweight='bold', y=0.98)

# ============================================================
# GUARDAR: PNG + PDF + SVG
# ============================================================
for ext, kw in (('png', dict(dpi=300)), ('pdf', {}), ('svg', {})):
    path = f'{OUT_BASE}.{ext}'
    plt.savefig(path, bbox_inches='tight', **kw)
    print(f'Guardado: {path}')

plt.show()