"""
JointAlllBaseLineVpatrick.py
----------------------------
Grafica TODAS las coordenadas articulares y estados que existan en los .mot
de PredSim (Baseline vs Batch de Exo) y las guarda en un PDF multipagina.

Correcciones incluidas:
1. Recorta automaticamente los .mot de 2 zancadas a 1 solo ciclo de marcha (0-100%).
2. Distingue angulos (deg), traslaciones (m) y activaciones musculares (0-1).
3. Sombrea la ventana real del exoesqueleto en pierna derecha (_r) e izquierda (_l, +50%).
4. Incluye pagina final con el perfil exacto de Zhang (con rampa de pretension) y potencia.
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
ROOT = r'C:\PredSim\exo_project\PredSimResults'

# Parametros del sujeto y del exoesqueleto (posicion real en el .mot)
MASS_HUMAN = 62.0   # [kg]
EXO_TP     = 48.0   # [%] (22.0 de MATLAB + 26.0 de offset del .mot)
EXO_TR     = 21.0   # [%] Duracion de la subida (inicia en 48 - 21 = 27%)
EXO_TF     = 9.6    # [%] Duracion de la bajada (termina en 48 + 9.6 = 57.6%)

# Si PredSim guarda 2 ciclos completos en el .mot (tipico: ~200 filas), recortar al primero
TRIM_TWO_STRIDES = True

# Sombrear ventana de actuacion del exo: 'all' (todos), 'ankle' (solo tobillo), None
SHADE_EXO_WINDOW = 'all'

# (leyenda, subcarpeta relativa a ROOT, color, estilo de linea, Mp [Nm/kg])
CONDITIONS = [
    ('Baseline (No Exo)',   'gait1018',     '#000000', '--', 0.00),
    ('Exo Mp = 0.00 Nm/kg', r'SO4\Mp_0_00', '#7f7f7f', '-',  0.00),
    ('Exo Mp = 0.17 Nm/kg', r'SO4\Mp_0_17', '#0072bd', '-',  0.17),
    ('Exo Mp = 0.34 Nm/kg', r'SO4\Mp_0_34', '#edb120', '-',  0.34),
    ('Exo Mp = 0.68 Nm/kg', r'SO4\Mp_0_68', '#d95319', '-',  0.68),
]

EXCLUDE = []            # p. ej. ['mtp_angle_r', 'mtp_angle_l']

# Limites fijos opcionales (min, max). Si no esta la coordenada -> autoescala.
Y_LIMITS = {
    # 'pelvis_ty':     (0.87, 0.95),
    # 'knee_angle_r':  (0, 80),
}

FLIP_KNEE    = True     # invierte el signo de knee_angle
TOE_OFF_PCT  = 54.0     # Toe-off real en gait1018 (~54%)
MAX_PER_PAGE = 8        # 4 filas x 2 columnas
COLS         = 2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PDF    = os.path.join(SCRIPT_DIR, 'Joints_All_Baseline_vs_ExoPatrick.pdf')
TITLE      = 'Kinematics & Activations: Baseline vs Exo Batch'

plt.rcParams['pdf.fonttype'] = 42   # texto editable en el PDF (Illustrator, etc.)

# Orden preferido dentro de cada grupo (se compara sin el sufijo _r / _l)
PREFERRED = [
    'pelvis_tilt', 'pelvis_list', 'pelvis_rotation', 'pelvis_tx', 'pelvis_ty', 'pelvis_tz',
    'lumbar_extension', 'lumbar_bending', 'lumbar_rotation',
    'hip_flexion', 'hip_adduction', 'hip_rotation',
    'knee_angle', 'ankle_angle', 'subtalar_angle', 'mtp_angle',
]


# ============================================================
# PERFIL DE TORQUE EXACTO DE ZHANG (CON PRE-TENSION DE 2 Nm)
# ============================================================
def zhang_torque_profile(pct_vec, peak_torque, tp=EXO_TP, tr=EXO_TR, tf=EXO_TF):
    """
    Reproduce exactamente desired_torque_generator.m de Zhang et al. (2017),
    incluyendo la rampa lineal inicial hasta 2 Nm (pre-tension) y la bajada a 0 en 65%.
    """
    tau = np.zeros_like(pct_vec, dtype=float)
    if peak_torque <= 0:
        return tau

    t_on  = tp - tr
    t_off = tp + tf
    t_zero = 65.0  # En desired_torque_generator.m el cable llega a 0 Nm en el 65%
    tau_pre = min(2.0, peak_torque * 0.2)  # 2 Nm de pretension en el paper de Zhang

    # 1. Rampa lineal de pretension: [0, t_on] -> 0 a 2 Nm
    m1 = (pct_vec >= 0) & (pct_vec < t_on)
    if t_on > 0:
        tau[m1] = (tau_pre / t_on) * pct_vec[m1]

    # 2. Subida cubica (spline con pendiente 0 en t_on y tp): [t_on, tp] -> 2 Nm a peak_torque
    m2 = (pct_vec >= t_on) & (pct_vec <= tp)
    u2 = (pct_vec[m2] - t_on) / tr
    tau[m2] = tau_pre + (peak_torque - tau_pre) * (3.0 * u2**2 - 2.0 * u2**3)

    # 3. Bajada cubica: (tp, t_off] -> peak_torque a 2 Nm
    m3 = (pct_vec > tp) & (pct_vec <= t_off)
    u3 = (pct_vec[m3] - tp) / tf
    tau[m3] = tau_pre + (peak_torque - tau_pre) * (2.0 * u3**3 - 3.0 * u3**2 + 1.0)

    # 4. Cola lineal de destensado: (t_off, 65%] -> 2 Nm a 0 Nm
    if t_zero > t_off:
        m4 = (pct_vec > t_off) & (pct_vec <= t_zero)
        tau[m4] = tau_pre * (1.0 - (pct_vec[m4] - t_off) / (t_zero - t_off))

    return tau


# ============================================================
# LECTURA DE .mot Y RECORTE A 1 CICLO
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


data = []   # un dict por condicion
for label, sub, color, style, mp in CONDITIONS:
    folder = os.path.join(ROOT, sub)
    f = latest_mot(folder)
    if f is None:
        print(f'[AVISO] Sin .mot en {folder}')
        continue
    print(f'{label} -> {f}')
    df, in_deg = read_mot(f)

    # Recortar si el archivo .mot contiene 2 ciclos concatenados (ej. ~200 filas)
    if TRIM_TWO_STRIDES and len(df) > 120:
        n_half = len(df) // 2 + 1
        df = df.iloc[:n_half].reset_index(drop=True)

    t = df['time'].to_numpy()
    pct = (t - t[0]) / (t[-1] - t[0]) * 100.0
    data.append(dict(label=label, df=df, in_deg=in_deg, t=t, pct=pct,
                     color=color, style=style, mp=mp))

if not data:
    raise SystemExit('No se cargo ninguna condicion. Revisa ROOT y CONDITIONS.')


# ============================================================
# COORDENADAS A GRAFICAR (union de todas las condiciones)
# ============================================================
coords = []
for d in data:
    for c in d['df'].columns:
        if c == 'time' or c in EXCLUDE or c in coords:
            continue
        if not pd.api.types.is_numeric_dtype(d['df'][c]):
            continue
        coords.append(c)


def group_of(c):
    if c.startswith('pelvis_'):
        return 'Pelvis'
    if c.startswith('lumbar_'):
        return 'Trunk (lumbar)'
    if c.endswith('_r') or '_r/' in c:
        return 'Right side'
    if c.endswith('_l') or '_l/' in c:
        return 'Left side'
    return 'Other'


def sort_key(c):
    base = c[:-2] if c.endswith(('_r', '_l')) else c
    return (PREFERRED.index(base) if base in PREFERRED else 999, c)


GROUP_ORDER = ['Pelvis', 'Trunk (lumbar)', 'Right side', 'Left side', 'Other']
groups = {g: sorted([c for c in coords if group_of(c) == g], key=sort_key) for g in GROUP_ORDER}

# Paginas: (titulo, [coordenadas])
pages = []
for g in GROUP_ORDER:
    cs = groups[g]
    n_pages = math.ceil(len(cs) / MAX_PER_PAGE)
    for p in range(n_pages):
        chunk = cs[p * MAX_PER_PAGE:(p + 1) * MAX_PER_PAGE]
        suffix = f' ({p + 1}/{n_pages})' if n_pages > 1 else ''
        pages.append((g + suffix, chunk))

print(f'{len(coords)} coordenadas en {len(pages)} paginas (+ 1 pagina de Torque/Potencia).')


# ============================================================
# FORMATO Y DIBUJO DE SUBPLOTS
# ============================================================
def format_gait_axis(ax, toe_off=TOE_OFF_PCT):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(1.2)
    ax.spines['bottom'].set_linewidth(1.2)

    ax.set_xlim(0, 100)
    ax.set_xticks([0, 50, 100])
    ax.set_xticklabels(['0', '50', '100'])
    ax.tick_params(axis='x', length=5, direction='out')
    ax.tick_params(axis='y', length=5, direction='out')
    ax.grid(False)

    trans = ax.get_xaxis_transform()
    for dx in (-0.5, 0.5):
        ax.plot([toe_off + dx, toe_off + dx], [-0.05, 0.05],
                transform=trans, color='black', linewidth=0.7, clip_on=False)
    ax.text(toe_off, -0.08, 'Toe-Off', transform=trans,
            ha='center', va='top', fontsize=9)


def shade_exo_actuation(ax, is_left=False, show_labels=False):
    """
    Sombrea la ventana principal de actuacion [tp-tr, tp+tf].
    Si es pierna izquierda (is_left=True), desfasa +50% del ciclo con wrap-around.
    """
    shift = 50.0 if is_left else 0.0
    t_on  = (EXO_TP - EXO_TR + shift) % 100.0
    t_pk  = (EXO_TP + shift) % 100.0
    t_off = (EXO_TP + EXO_TF + shift) % 100.0

    if t_on < t_off:
        ax.axvspan(t_on, t_off, color='#edb120', alpha=0.12, zorder=0)
    else:
        # Si cruza el 100% (tipico en pierna izquierda)
        ax.axvspan(t_on, 100.0, color='#edb120', alpha=0.12, zorder=0)
        ax.axvspan(0.0, t_off, color='#edb120', alpha=0.12, zorder=0)

    ax.axvline(t_pk, color='#d95319', linestyle=':', linewidth=0.9, alpha=0.65, zorder=1)

    if show_labels:
        trans = ax.get_xaxis_transform()
        ax.text(t_on, 1.01, f'{t_on:.1f}%', transform=trans,
                ha='center', va='bottom', fontsize=7.5, color='#666666')
        ax.text(t_pk, 1.01, f'Peak ({t_pk:.1f}%)', transform=trans,
                ha='center', va='bottom', fontsize=7.5, fontweight='bold', color='#d95319')
        ax.text(t_off, 1.01, f'{t_off:.1f}%', transform=trans,
                ha='center', va='bottom', fontsize=7.5, color='#666666')


def draw_coord(ax, coord, show_legend):
    is_trans = coord.endswith(('_tx', '_ty', '_tz'))
    is_act   = 'activation' in coord.lower()
    is_NonAng = is_trans or is_act or ('force' in coord.lower()) or ('length' in coord.lower())
    is_left  = coord.endswith('_l') or ('_l/' in coord)

    # Sombreado de la ventana activa
    if SHADE_EXO_WINDOW == 'all' or (SHADE_EXO_WINDOW == 'ankle' and 'ankle_angle' in coord):
        shade_exo_actuation(ax, is_left=is_left, show_labels=('ankle_angle' in coord))

    ys = []
    for d in data:
        df = d['df']
        if coord not in df.columns:
            print(f'[AVISO] {coord} no esta en {d["label"]}')
            continue
        y = df[coord].to_numpy().astype(float)
        # Solo convertir rad -> deg si es realmente un angulo articular
        if not is_NonAng and not d['in_deg']:
            y = np.rad2deg(y)
        if FLIP_KNEE and 'knee_angle' in coord:
            y = -y
        ys.append(y)
        ax.plot(d['pct'], y, label=d['label'], color=d['color'],
                linestyle=d['style'], linewidth=2.0 if d['style'] == '--' else 1.8,
                zorder=6 if d['style'] == '--' else 4)

    # Eje Y: limites fijos o autoescala
    if coord in Y_LIMITS:
        ymin, ymax = Y_LIMITS[coord]
        pad = 0.02 if is_NonAng else 2
        ax.set_ylim(ymin - pad, ymax + pad)
        ax.set_yticks([ymin, 0, ymax] if ymin < 0 < ymax else [ymin, ymax])
    elif ys:
        lo = min(np.nanmin(y) for y in ys)
        hi = max(np.nanmax(y) for y in ys)
        tol = 1e-4 if is_NonAng else 1e-2
        if hi - lo < tol:
            c, p = (lo + hi) / 2, (0.01 if is_NonAng else 1.0)
            ax.set_ylim(c - p, c + p)

    # Linea y=0 solo si el cero cae dentro del rango
    lo, hi = ax.get_ylim()
    if lo < 0 < hi:
        ax.axhline(0, color='gray', linestyle='--', linewidth=0.8, alpha=0.5, zorder=0)

    # En la pierna izquierda el Toe-Off ocurre desfasado +50% (alrededor de 4% del ciclo derecho)
    toe_off_plot = (TOE_OFF_PCT + 50.0) % 100.0 if is_left else TOE_OFF_PCT
    format_gait_axis(ax, toe_off=toe_off_plot)

    ax.set_title(coord, fontweight='bold', fontsize=12, pad=10 if 'ankle_angle' in coord else 6)
    ax.set_xlabel('Gait Cycle (%)', labelpad=18)

    if is_trans:
        ax.set_ylabel('Position (m)')
    elif is_act:
        ax.set_ylabel('Activation (0 - 1)')
    else:
        ax.set_ylabel('Angle (deg)')

    if show_legend:
        ax.legend(fontsize=8.5, frameon=False, loc='best')


def create_exo_actuation_page():
    """Pagina resumen 2x2: Torque Derecha/Izquierda, Torque Normalizado, Vel. Angular y Potencia."""
    fig, axes = plt.subplots(2, 2, figsize=(15, 8.2))
    axes = axes.flatten()
    pct_dense = np.linspace(0, 100, 1000)

    # 1. Perfil de Torque Absoluto (Pierna Derecha: 0-100%, más línea punteada de Izquierda)
    ax = axes[0]
    shade_exo_actuation(ax, is_left=False, show_labels=True)
    for label, _, color, style, mp in CONDITIONS:
        if style == '--':
            continue
        tau_peak = mp * MASS_HUMAN
        tau_r = zhang_torque_profile(pct_dense, tau_peak)
        ax.plot(pct_dense, tau_r, label=f'{label} ({tau_peak:.1f} Nm)',
                color=color, linestyle='-', linewidth=2.0)
    format_gait_axis(ax)
    ax.set_title('Right Ankle Assistive Torque Profile (Zhang et al., 2017)', fontweight='bold', fontsize=12, pad=12)
    ax.set_xlabel('Gait Cycle (%)', labelpad=18)
    ax.set_ylabel('Plantarflexion Torque (Nm)')
    ax.legend(fontsize=8.5, frameon=False, loc='upper left')

    # 2. Comparacion de Fase: Pierna Derecha (0-50% Stance) vs Pierna Izquierda (+50% Shift)
    ax = axes[1]
    max_mp = max(c[4] for c in CONDITIONS)
    tau_r_max = zhang_torque_profile(pct_dense, max_mp * MASS_HUMAN)
    pct_l = (pct_dense + 50.0) % 100.0
    tau_l_max = zhang_torque_profile(pct_l, max_mp * MASS_HUMAN)
    ax.plot(pct_dense, tau_r_max, color='#0072bd', linewidth=2.2, label=f'Right Leg (Mp={max_mp})')
    ax.plot(pct_dense, tau_l_max, color='#d95319', linestyle='--', linewidth=2.0, label=f'Left Leg (+50% shift)')
    ax.axvline(50.0, color='black', linestyle=':', linewidth=1.0, label='Half Stride (50%)')
    format_gait_axis(ax)
    ax.set_title('Right vs. Left Leg Torque Timing Across Full Stride', fontweight='bold', fontsize=12)
    ax.set_xlabel('Gait Cycle (%)', labelpad=18)
    ax.set_ylabel('Plantarflexion Torque (Nm)')
    ax.legend(fontsize=8.5, frameon=False, loc='upper right')

    # 3. Velocidad Angular del Tobillo Derecho (rad/s)
    ax = axes[2]
    shade_exo_actuation(ax, is_left=False, show_labels=False)
    for d in data:
        if 'ankle_angle_r' not in d['df'].columns:
            continue
        ang = d['df']['ankle_angle_r'].to_numpy().astype(float)
        ang_rad = np.deg2rad(ang) if d['in_deg'] else ang
        omega_r = np.gradient(ang_rad, d['t'])
        ax.plot(d['pct'], omega_r, label=d['label'], color=d['color'],
                linestyle=d['style'], linewidth=1.8, zorder=6 if d['style'] == '--' else 4)
    ax.axhline(0, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)
    format_gait_axis(ax)
    ax.set_title('Right Ankle Angular Velocity (ankle_angle_r)', fontweight='bold', fontsize=12)
    ax.set_xlabel('Gait Cycle (%)', labelpad=18)
    ax.set_ylabel('Angular Velocity (rad/s)')

    # 4. Potencia Mecanica del Exoesqueleto (W) en Tobillo Derecho
    ax = axes[3]
    shade_exo_actuation(ax, is_left=False, show_labels=False)
    for d in data:
        if 'ankle_angle_r' not in d['df'].columns or d['style'] == '--':
            continue
        ang = d['df']['ankle_angle_r'].to_numpy().astype(float)
        ang_rad = np.deg2rad(ang) if d['in_deg'] else ang
        omega_r = np.gradient(ang_rad, d['t'])
        tau_r   = zhang_torque_profile(d['pct'], d['mp'] * MASS_HUMAN)
        power_r = tau_r * (-omega_r)  # (+) Generacion plantarflexora, (-) Absorcion
        ax.plot(d['pct'], power_r, label=d['label'], color=d['color'],
                linestyle=d['style'], linewidth=1.8)
    ax.axhline(0, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)
    format_gait_axis(ax)
    ax.set_title('Exoskeleton Mechanical Power (Right Ankle)', fontweight='bold', fontsize=12)
    ax.set_xlabel('Gait Cycle (%)', labelpad=18)
    ax.set_ylabel('Mechanical Power (W)')

    fig.tight_layout(rect=[0, 0.02, 1, 0.94])
    fig.suptitle(f'{TITLE}  -  Exoskeleton Actuation & Power',
                 fontsize=16, fontweight='bold', y=0.985)
    return fig


# ============================================================
# PDF MULTIPAGINA
# ============================================================
with PdfPages(OUT_PDF) as pdf:
    for title, cs in pages:
        rows = math.ceil(len(cs) / COLS)
        fig, axes = plt.subplots(rows, COLS, figsize=(15, 3.6 * rows + 0.8))
        axes = np.atleast_1d(axes).flatten()

        for i, coord in enumerate(cs):
            draw_coord(axes[i], coord, show_legend=(i == 0))
        for j in range(len(cs), len(axes)):
            fig.delaxes(axes[j])

        fig.tight_layout(rect=[0, 0.02, 1, 0.95])
        fig.suptitle(f'{TITLE}  -  {title}', fontsize=16, fontweight='bold', y=0.985)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

    fig_exo = create_exo_actuation_page()
    pdf.savefig(fig_exo, bbox_inches='tight')
    plt.close(fig_exo)

print(f'Guardado exitosamente: {OUT_PDF}')