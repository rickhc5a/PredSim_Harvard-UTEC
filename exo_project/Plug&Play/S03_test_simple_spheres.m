clear
close all
clc

%% ===== ELEGIR CONDICIÓN =====
cond = 'SO4';    % 'SO1' | 'SO2' | 'SO3' | 'SO4'

% SO1: gait1018,     sin torque   (no-exo)
% SO2: gait1018,     con torque   (ideal, P&C)
% SO3: gait1018_exo, sin torque   (exo-off)
% SO4: gait1018_exo, con torque   (P&C sobre el modelo con masa)

%% Rutas (este script está en C:\PredSim\exo_project)
[pathRepo,~,~] = fileparts(fileparts(mfilename('fullpath')));   % C:\PredSim
addpath(fullfile(pathRepo,'DefaultSettings'))
addpath(pathRepo)

zhang_path = 'C:\Users\rickh\Downloads\aal5054_zhang_sm_data_s2';   % función del paper de Zhang
so1_mot    = fullfile(pathRepo,'exo_project','PredSimResults','gait1018','gait1018_v1.mot');

%% Modelo y torque según la condición
switch cond
    case 'SO1', subject = 'gait1018';     use_exo = false;
    case 'SO2', subject = 'gait1018';     use_exo = true;
    case 'SO3', subject = 'gait1018_exo'; use_exo = false;
    case 'SO4', subject = 'gait1018_exo'; use_exo = true;
end

%% Initialize S
[S] = initializeSettings(subject);

%% Settings
S.subject.name     = subject;
S.misc.save_folder = fullfile(pathRepo,'exo_project','PredSimResults',cond);

% initial guess: SO1 desde cero, el resto parte del resultado de SO1
if strcmp(cond,'SO1')
    S.solver.IG_selection = 'quasi-random';
else
    S.solver.IG_selection = so1_mot;
    S.solver.IG_selection_gaitCyclePercent = 100;
end

osim_path = fullfile(pathRepo,'Subjects',S.subject.name,[S.subject.name '.osim']);

%% Exoesqueleto (torque ideal, Poggensee & Collins)
if use_exo
    mass_human = 62.0;                        % kg, suma de masas de gait1018.osim SIN exo

    exo1.function_name       = 'ankleExoZhang2017';
    exo1.dependencies_path   = zhang_path;
    exo1.peak_torque = 0.68 * mass_human;     % [Nm]  Mp = 0.68 Nm/kg  (≈ 42.2 Nm)
    exo1.peak_time   = 54.1;                  % [%]   tp
    exo1.rise_time   = 27.9;                  % [%]   tr
    exo1.fall_time   = 9.6;                   % [%]   tf

    exo1.left_right = 'r';
    S.orthosis.settings{1} = exo1;
    exo1.left_right = 'l';
    S.orthosis.settings{2} = exo1;
end

%% Run predictive simulation
[savename] = runPredSim(S, osim_path);