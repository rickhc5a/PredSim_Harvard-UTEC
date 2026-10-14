import org.opensim.modeling.*
%% ---------------- Rutas ----------------
src      = 'C:\PredSim\Subjects\gait1018\gait1018.osim';
dst_dir  = 'C:\PredSim\exo_project\Subjects\gait1018_exo';
dst      = fullfile(dst_dir,'gait1018_exo.osim');
geom_dir = fullfile(dst_dir,'Geometry');

if ~exist(dst_dir,'dir'), mkdir(dst_dir); end 

model = Model(src);

%% ---------------- Conversion de unidades (Inventor -> OpenSim) ----------------
oz = 0.028349523125;     % ounce mass -> kg
in = 0.0254;             % in -> m
Ik = oz * in^2;          % oz*in^2 -> kg*m^2

%% ---------------- Datos de Geometría, Masa e Inercia ----------------
% Pantorrilla (ank)
ank.mesh  = 'exo_tobillo.stl';     
ank.scale = 0.001;
ank.mass  = 94.796 * oz;
ank.com   = [3.337, 9.357, 4.251] * in;
ank.I     = [673.371, 528.887, 722.592, -128.36, 15.777, -1.713] * Ik;

% Pie (foot)
foot.mesh  = 'exo_ankle.stl';      
foot.scale = 0.001;
foot.mass  = 10.797 * oz;
foot.com   = [1.13, -0.079, 4.186] * in;
foot.I     = [63.199, 121.547, 80.398, -20.142, -0.045, 0.041] * Ik;

%% ---------------- Posicion y orientacion ----------------
% loc = [X Y Z] coordenadas finales
% rot = [X Y Z] rotación (pi = 180 grados en Y)
cfg(1) = mk('exo_shank_r', 'tibia_r', [0.045 -0.375 0.117], [0 pi 0], ank,  1);
cfg(2) = mk('exo_foot_r',  'calcn_r', [0.09   0.08   0.11], [0 pi 0], foot, 1);

%% ---------------- Montaje Físico ----------------
for k = 1:numel(cfg)
    c = cfg(k);
    parent = model.getBodySet().get(c.parent);

    % Extraer masa e inercia real del struct
    com = c.part.com;  
    I   = c.part.I;     

    real_mass    = c.part.mass;
    real_com     = Vec3(com(1), com(2), com(3));
    real_inertia = Inertia(I(1), I(2), I(3), I(4), I(5), I(6));

    % Crear Body con los valores físicos reales para PredSim
    body = Body(c.name, real_mass, real_com, real_inertia);

    % Preparar Mesh
    mesh = Mesh(c.part.mesh);
    s = c.part.scale;

    % Aplicar escala
    mesh.set_scale_factors(Vec3(s, s, c.side*s));
    mesh.upd_Appearance().set_color(Vec3(1, 0.5, 0)); 
    body.attachGeometry(mesh);

    % Unir pieza al hueso padre
    weld = WeldJoint(['weld_' c.name], parent, ...
        Vec3(c.loc(1),c.loc(2),c.loc(3)), Vec3(c.rot(1),c.rot(2),c.rot(3)), ...
        body, Vec3(0,0,0), Vec3(0,0,0));
    model.addBody(body);
    model.addJoint(weld);
end

% Finalizar y guardar
model.setName('gait1018_exo');
model.finalizeConnections();
model.initSystem(); 
model.print(dst);
disp('Modelo físico generado exitosamente. Listo para simulaciones.');

%% ---------------- Funciones ----------------
function c = mk(name,parent,loc,rot,part,side)
c.name = name; c.parent = parent; c.loc = loc; c.rot = rot; c.part = part; c.side = side;
end