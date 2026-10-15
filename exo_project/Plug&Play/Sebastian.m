clear
close all
clc
%% ===== BATCH PREDSIM: CONDICIONES DE CARGA DE BROWNING ET AL. (2007) =====
% Modelos generados con make_all_conditions.py (una carpeta por condicion).
% Sin exoesqueleto: solo masa agregada (cilindros huecos) por segmento.
%   foot2/foot4, shank2/shank4, thigh4/thigh8 -> kg POR PIERNA
%   waist4/waist8/waist16                      -> kg TOTAL (pelvis)
conds = {'none','foot2','foot4','shank2','shank4','thigh4','thigh8', ...
    'waist4','waist8','waist16'};
added_kg = [0, 4, 8, 4, 8, 8, 16, 4, 8, 16];   % kg totales agregados (informativo)
v_walk        = 1.25;    % [m/s] velocidad del paper (treadmill)
skip_existing = true;    % true: salta condiciones que ya tienen un .mot en su carpeta
%% Rutas Globales
pathRepo   = 'C:\PredSim';
addpath(fullfile(pathRepo,'DefaultSettings'))
addpath(pathRepo)
models_dir = fullfile(pathRepo,'exo_project','Subjects','gait1018_pesas_2007');
res_root   = fullfile(pathRepo,'exo_project','PredSimResults','Browning2007');
so1_mot    = fullfile(pathRepo,'exo_project','PredSimResults','gait1018','gait1018_v1.mot');
%% ===== BUCLE BATCH =====
status  = strings(numel(conds),1);
elapsed = zeros(numel(conds),1);
for i = 1:numel(conds)
    cond    = conds{i};
    subject = ['gait1018_' cond];
    osim_path = fullfile(models_dir, subject, [subject '.osim']);
    save_folder = fullfile(res_root, cond);
    fprintf('\n======================================================\n');
    fprintf('  Simulacion %d/%d: %s  (+%d kg)\n', i, numel(conds), cond, added_kg(i));
    fprintf('======================================================\n');
    if ~isfile(osim_path)
        fprintf(2, 'No existe el modelo: %s\n', osim_path);
        status(i) = "SIN MODELO";
        continue
    end
    if ~exist(save_folder, 'dir'), mkdir(save_folder); end
    if skip_existing && ~isempty(dir(fullfile(save_folder,'*.mot')))
        disp('Ya tiene resultados (.mot). Saltando.');
        status(i) = "SALTADA";
        continue
    end
    %% 1. Settings limpios en cada iteracion
    [S] = initializeSettings(subject);
    S.subject.name = subject;
    S.subject.base_joints_arms = [];
    S.subject.tendon_stiff_scale = {{'soleus','gastroc'},0.5};
    S.misc.save_folder = save_folder;
    %% 2. Velocidad de marcha del paper (VERIFICAR nombre del campo en tu PredSim)
    S.misc.v_pelvis_x_trgt = v_walk;
    %% 3. Initial Guess
    if exist(so1_mot, 'file')
        S.solver.IG_selection = so1_mot;
        S.solver.IG_selection_gaitCyclePercent = 100;
    else
        S.solver.IG_selection = 'quasi-random';
    end
    %% 4. Ejecutar simulacion predictiva (sin ortesis: solo masa agregada)
    tic
    try
        [savename] = runPredSim(S, osim_path);
        fprintf('Completada: %s\n', savename);
        status(i) = "OK";
    catch ME
        fprintf(2, 'ERROR en %s: %s\n', cond, ME.message);
        disp('Continuando con la siguiente condicion...');
        status(i) = "ERROR";
    end
    elapsed(i) = toc;
end
%% ===== RESUMEN =====
fprintf('\n=========== RESUMEN ===========\n');
for i = 1:numel(conds)
    fprintf('%-8s  %-11s  %6.1f min\n', conds{i}, status(i), elapsed(i)/60);
end
disp('¡Proceso batch finalizado!');