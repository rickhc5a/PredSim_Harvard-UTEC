clear
close all
clc
[pathRepo,~,~] = fileparts(mfilename('fullpath'));
[pathRepoFolder,~,~] = fileparts(pathRepo);
addpath(fullfile(pathRepo,'DefaultSettings'))
%% Initialize S
[S] = initializeSettings('gait1018');
%% Settings
S.subject.name = 'gait1018';
S.misc.save_folder = fullfile(pathRepoFolder,'PredSimResults',S.subject.name);
S.solver.IG_selection = 'quasi-random';
osim_path = fullfile(pathRepo,'Subjects',S.subject.name,[S.subject.name '.osim']);
%% Run predictive simulations
[savename] = runPredSim(S, osim_path);