clear
close all
clc

%% ===== CONFIGURACIÓN GLOBAL: EXOESQUELETO FÍSICO + TORQUE ASISTIVO (SO4) =====
subject    = 'gait1018_exo';
cond       = 'SO4';
mass_human = 62.0; % [kg] Masa del sujeto base SIN exoesqueleto

% Vector de torques pico normalizados [Nm/kg]
Mp_list = [0; 0.17; 0.34; 0.68];

%% Rutas Globales
pathRepo = 'C:\PredSim'; 
addpath(fullfile(pathRepo,'DefaultSettings'))
addpath(pathRepo)

% Ruta de la función de torque del paper de Zhang
zhang_path = 'C:\Users\rickh\Downloads\aal5054_zhang_sm_data_s2';   
osim_path  = fullfile(pathRepo,'exo_project','Subjects',subject,[subject '.osim']);
so1_mot    = fullfile(pathRepo,'exo_project','PredSimResults','gait1018','gait1018_v1.mot');

%% ===== BUCLE BATCH PARA CADA NIVEL DE TORQUE =====
for i = 1:length(Mp_list)
    Mp = Mp_list(i);

    % Formatear etiqueta para subcarpeta (ej. 'Mp_0_17') evitando puntos en nombres de carpeta
    mp_str = strrep(sprintf('Mp_%.2f', Mp), '.', '_');

    fprintf('\n======================================================\n');
    fprintf('  Iniciando simulación %d/%d: Mp = %.2f Nm/kg (%.2f Nm)\n', ...
        i, length(Mp_list), Mp, Mp * mass_human);
    fprintf('======================================================\n');

    %% 1. Inicializar S limpio en cada iteración
    [S] = initializeSettings(subject);

    %% 2. Settings Generales y de Sujeto
    S.subject.name = subject;
    S.subject.base_joints_arms = []; 
    S.subject.tendon_stiff_scale = {{'soleus','gastroc'},0.5};

    % Guardar cada corrida en su propia subcarpeta dentro de SO4
    S.misc.save_folder = fullfile(pathRepo,'exo_project','PredSimResults',cond,mp_str);
    if ~exist(S.misc.save_folder, 'dir')
        mkdir(S.misc.save_folder);
    end

    %% 3. Initial Guess (Semilla)
    if exist(so1_mot, 'file')
        S.solver.IG_selection = so1_mot;
        S.solver.IG_selection_gaitCyclePercent = 100;
        if i == 1
            disp('Archivo SO1 encontrado. Usando como Initial Guess.');
        end
    else
        S.solver.IG_selection = 'quasi-random';
        if i == 1
            disp('Archivo SO1 no encontrado. Usando "quasi-random" (tardará más).');
        end
    end

    %% 4. Exoesqueleto (Torque ideal ajustado al Toe-Off de gait1018)
    exo1 = struct(); % Reiniciar estructura limpia
    exo1.function_name         = 'ankleExoZhang2017';
    exo1.dependencies_path     = zhang_path;
    exo1.peak_torque           = Mp * mass_human;   % [Nm] Actualizado dinámicamente

    % Compensando el offset de +26% de PredSim para que en el .mot actúe de 22% a 57.6% (Pico en 48%):
    exo1.peak_time = 22.0;   % En el .mot caerá en 22 + 26 = 48.0% (pleno Push-Off!)
    exo1.rise_time = 21.0;   % En el .mot iniciará en 1 + 26 = 27.0%
    exo1.fall_time = 9.6;    % En el .mot terminará en 31.6 + 26 = 57.6% (Toe-Off!)

    % Graficar en MATLAB el perfil aplicado a ambas piernas
    exo1.plotAssistanceProfile = true;              

    % Aplicar asistencia a la pierna derecha
    exo1.left_right = 'r';
    S.orthosis.settings{1} = exo1;

    % Aplicar asistencia a la pierna izquierda
    exo1.left_right = 'l';
    S.orthosis.settings{2} = exo1;

    %% 5. Ejecutar simulación predictiva
    disp(['Ejecutando PredSim para: ' cond ' - ' mp_str '...']);
    try
        [savename] = runPredSim(S, osim_path);
        fprintf('Simulación completada con éxito: %s\n', savename);
    catch ME
        fprintf(2, 'ERROR en Mp = %.2f: %s\n', Mp, ME.message);
        disp('Continuando con el siguiente valor del batch...');
    end
end
disp('¡Proceso batch finalizado!');