% --------------------------------------------------------------------------
% Settings for gait1018_exo (i.e. 2D model with exoskeleton)
% --------------------------------------------------------------------------
S.subject.name = 'gait1018_exo';

% This model has no arms
S.subject.base_joints_arms = []; 

% Achilles tendon stiffness
S.subject.tendon_stiff_scale = {{'soleus','gastroc'},0.5};