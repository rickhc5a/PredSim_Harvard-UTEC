import sys
import opensim as osim

path = sys.argv[1]
print("Cargando:", path)
model = osim.Model(path)
state = model.initSystem()

print("\nMasa total del modelo: %.3f kg" % model.getTotalMass(state))

print("\nFrames de carga encontrados:")
n = 0
for pof in model.getComponentsList():
    if pof.getConcreteClassName() == "PhysicalOffsetFrame" and pof.getName().startswith("load_"):
        n += 1
        print("  -", pof.getAbsolutePathString())
print("Total: %d" % n)

print("\nSi arriba NO aparecieron mensajes [error] ni [warning] sobre 'Mesh' o"
      " 'Couldn't find file', las mallas estan bien conectadas.")