import org.opensim.modeling.*
%% ---------------- Rutas ----------------
src      = 'C:\PredSim\Subjects\gait1018\gait1018.osim';
dst_dir  = 'C:\PredSim\exo_project\Subjects\gait1018_exo';
dst      = fullfile(dst_dir,'gait1018_exo.osim');
geom_dir = fullfile(dst_dir,'Geometry');
if ~exist(dst_dir,'dir'), mkdir(dst_dir); endco
    model = Model(src);

    %% ---------------- Datos de Geometría (ACTUALIZADO A STL) ----------------
    % Nombres exactos exportados por Python
    ank.mesh  = 'exo_tobillo.stl';     
    foot.mesh = 'exo_ankle.stl';      

    % Escala del mesh (1 cm CAD = 0.01 m OpenSim)
    ank.scale  = 0.01;
    foot.scale = 0.01;

    %% ---------------- Posicion y orientacion ----------------
    % loc = origen de la pieza respecto al hueso
    cfg(1) = mk('exo_shank_r', 'tibia_r', [0 0 0], [0 0 0], ank,  1);
    cfg(2) = mk('exo_foot_r',  'calcn_r', [0 0 0], [0 0 0], foot, 1);

    %% ---------------- Montaje Seguro ----------------
    for k = 1:numel(cfg)
        c = cfg(k);
        parent = model.getBodySet().get(c.parent);

        % MASA E INERCIA DUMMY (Evita que Simbody explote y deforme las piezas)
        dummy_mass    = 0.1;
        dummy_com     = Vec3(0, 0, 0);
        dummy_inertia = Inertia(0.001, 0.001, 0.001, 0, 0, 0); 

        % Crear Body con valores seguros
        body = Body(c.name, dummy_mass, dummy_com, dummy_inertia);

        % Preparar Mesh
        mesh = Mesh(c.part.mesh);
        s = c.part.scale;

        % Aplicar escala
        mesh.set_scale_factors(Vec3(s, s, c.side*s));
        mesh.upd_Appearance().set_color(Vec3(1, 0.5, 0)); % Color naranja para distinguirlos
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
    model.initSystem(); % Si esto falla, te avisará en consola
    model.print(dst);
    disp('Modelo generado exitosamente. Revisa la carpeta en OpenSim.');

    %% ---------------- Funciones ----------------
    function c = mk(name,parent,loc,rot,part,side)
    c.name = name; c.parent = parent; c.loc = loc; c.rot = rot; c.part = part; c.side = side;
    end