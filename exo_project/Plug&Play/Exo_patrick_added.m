clear
close all
clc

%% ===== CONFIGURACIÓN: EXOESQUELETO FÍSICO + TORQUE ASISTIVO (SO4) =====
subject = 'gait1018_exo';
cond    = 'SO4';

%% Rutas
% Forzamos la ruta base de PredSim
pathRepo = 'C:\PredSim'; 
addpath(fullfile(pathRepo,'DefaultSettings'))
addpath(pathRepo)

% Ruta de la función de torque del paper de Zhang
zhang_path = 'C:\Users\rickh\Downloads\aal5054_zhang_sm_data_s2';   

%% Inicializar S
[S] = initializeSettings(subject);

%% Settings Generales y de Sujeto
S.subject.name = subject;

% FORZAMOS LOS SETTINGS DEL MODELO 2D AQUÍ (por si el archivo settings.m falla)
S.subject.base_joints_arms = []; 
S.subject.tendon_stiff_scale = {{'soleus','gastroc'},0.5};

% Rutas correctas apuntando a tu carpeta exo_project
S.misc.save_folder = fullfile(pathRepo,'exo_project','PredSimResults',cond);
osim_path = fullfile(pathRepo,'exo_project','Subjects',subject,[subject '.osim']);

%% Initial Guess (Semilla)
so1_mot = fullfile(pathRepo,'exo_project','PredSimResults','gait1018','gait1018_v1.mot');

% Usar el resultado del humano base acelera enormemente la convergencia.
if exist(so1_mot, 'file')
    S.solver.IG_selection = so1_mot;
    S.solver.IG_selection_gaitCyclePercent = 100;
    disp('Archivo SO1 encontrado. Usando como Initial Guess.');
else
    S.solver.IG_selection = 'quasi-random';
    disp('Archivo SO1 no encontrado. Usando "quasi-random" (tardará más).');
end

%% Exoesqueleto (Torque ideal, Poggensee & Collins)
mass_human = 62.0; % kg, masa del sujeto base SIN exoesqueleto

exo1.function_name     = 'ankleExoZhang2017';
exo1.dependencies_path = zhang_path;
exo1.peak_torque       = 0.68 * mass_human;     % [Nm]  Mp = 0.68 Nm/kg  (≈ 42.16 Nm)
exo1.peak_time         = 54.1;                  % [%]   tp
exo1.rise_time         = 27.9;                  % [%]   tr
exo1.fall_time         = 9.6;                   % [%]   tf

% Aplicar asistencia a la pierna derecha
exo1.left_right = 'r';
S.orthosis.settings{1} = exo1;

% Aplicar asistencia a la pierna izquierda
exo1.left_right = 'l';
S.orthosis.settings{2} = exo1;

%% Ejecutar simulación predictiva
disp(['Iniciando PredSim para la condición: ' cond ' (Masa Exo + Torque)...']);
disp(['Usando modelo desde: ' osim_path]);
[savename] = runPredSim(S, osim_path);