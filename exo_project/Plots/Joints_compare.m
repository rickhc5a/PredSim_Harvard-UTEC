%% Comparación cinemática: SO1 vs SO3 vs SO4 (.mot de PredSim)
clear; close all; clc

root = 'C:\PredSim\exo_project\PredSimResults';

% carpeta con el .mot de cada condición (toma el .mot más reciente de la carpeta)
folders = {fullfile(root,'gait1018'), ...   % SO1 (tu resultado actual; cámbialo a 'SO1' si repites la corrida)
    fullfile(root,'SO3'), ...
    fullfile(root,'SO4')};
labels  = {'SO1 no-exo','SO3 exo-off','SO4 exo + torque'};
colors  = {[0 0 0],[0 0.447 0.741],[0.85 0.325 0.098]};
styles  = {'--','-','-'};

coords_to_plot = {'pelvis_ty','pelvis_tilt','hip_flexion_r', ...
    'knee_angle_r','ankle_angle_r','lumbar_extension'};
y_labels = {'Position (m)','Angle (deg)','Angle (deg)', ...
    'Angle (deg)','Angle (deg)','Angle (deg)'};

flip_knee   = true;    % pone la flexión de rodilla en positivo (como en tu script de Python)
TOE_OFF_PCT = 60;      % aproximado; cámbialo o pon [] para no dibujar la línea

%% Leer los .mot
data = cell(1,numel(folders));
for k = 1:numel(folders)
    d = dir(fullfile(folders{k},'*.mot'));
    if isempty(d), warning('Sin .mot en %s',folders{k}); continue; end
    [~,idx] = max([d.datenum]);
    f = fullfile(d(idx).folder,d(idx).name);
    fprintf('%s -> %s\n',labels{k},f);
    [T,inDeg] = read_mot(f);
    data{k}.T = T; data{k}.inDeg = inDeg;
    data{k}.pct = (T.time - T.time(1)) / (T.time(end) - T.time(1)) * 100;
end

%% Gráficos
fig = figure('Color','w','Position',[100 100 1300 650]);
for i = 1:numel(coords_to_plot)
    coord = coords_to_plot{i};
    ax = subplot(2,3,i); hold(ax,'on'); box(ax,'off')
    for k = 1:numel(data)
        if isempty(data{k}), continue; end
        T = data{k}.T;
        if ~ismember(coord,T.Properties.VariableNames)
            warning('%s no está en %s',coord,labels{k}); continue
        end
        y = T.(coord);
        isTrans = ~isempty(regexp(coord,'_t[xyz]$','once'));
        if ~isTrans && ~data{k}.inDeg, y = rad2deg(y); end
        if flip_knee && contains(coord,'knee_angle'), y = -y; end
        plot(ax,data{k}.pct,y,styles{k},'Color',colors{k},'LineWidth',1.8, ...
            'DisplayName',labels{k});
    end
    if ~isempty(TOE_OFF_PCT), xline(ax,TOE_OFF_PCT,':k','HandleVisibility','off'); end
    xlim(ax,[0 100]); xticks(ax,[0 50 100])
    title(ax,coord,'Interpreter','none','FontWeight','bold')
    xlabel(ax,'Gait Cycle (%)'); ylabel(ax,y_labels{i})
    if i == 1, legend(ax,'Location','best','Box','off'); end
end
sgtitle('Kinematics: SO1 vs SO3 vs SO4','FontWeight','bold')
exportgraphics(fig,fullfile(fileparts(mfilename('fullpath')),'Joints_SO1_SO3_SO4.png'),'Resolution',300)

%% Función local: lee un .mot de OpenSim
function [T,inDeg] = read_mot(f)
fid = fopen(f); n = 0; inDeg = true;
while true
    l = fgetl(fid); n = n + 1;
    if ~ischar(l), fclose(fid); error('No se encontró endheader en %s',f); end
    if contains(lower(l),'indegrees=no'), inDeg = false; end
    if strcmpi(strtrim(l),'endheader'), break; end
end
fclose(fid);
T = readtable(f,'FileType','text','NumHeaderLines',n, ...
    'Delimiter',{'\t',' '},'MultipleDelimsAsOne',true, ...
    'VariableNamingRule','preserve');
end