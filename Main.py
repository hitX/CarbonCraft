import math
import threading
import pubchempy as pcp
from ursina import *
from rdkit import Chem
from rdkit.Chem import AllChem

# ==========================================
# APP & STUDIO LIGHTING
# ==========================================
app = Ursina(title='Interactive MolBuilder 3D', size=(1600, 900))
window.color = color.hex('#5A5A5A') # Mid-grey studio background

# Matte lighting to create soft, realistic plastic shadows
AmbientLight(color=color.rgba(255, 255, 255, 130))
DirectionalLight(y=3, z=-3, shadows=True, rotation=(30, -30, 0), color=color.rgba(255,255,255, 180))
DirectionalLight(y=-3, z=3, shadows=False, rotation=(-30, 30, 0), color=color.rgba(255,255,255, 60))

def make_z_aligned_cylinder(segments=32):
    """Extrudes a flawless cylinder along the Z-axis for perfect bond rendering"""
    verts, tris = [],[]
    for i in range(segments):
        a0 = 2 * math.pi * i / segments
        a1 = 2 * math.pi * ((i + 1) % segments) / segments
        c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
        base = len(verts)
        # Built along Z from -0.5 to 0.5
        verts +=[Vec3(c0, s0, -0.5), Vec3(c1, s1, -0.5), Vec3(c1, s1, 0.5), Vec3(c0, s0, 0.5)]
        tris +=[(base, base+1, base+2), (base, base+2, base+3)]
    return Mesh(vertices=verts, triangles=tris)

cylinder_mesh = make_z_aligned_cylinder()

# Real CPK Colors (Verified Hex Codes)
ATOM_COLORS = {
    'C': color.hex('#2E343B'),  # Carbon: Dark Slate Grey
    'H': color.hex('#FFFFFF'),  # Hydrogen: Pure White
    'O': color.hex('#FF0D0D'),  # Oxygen: Red
    'N': color.hex('#2233FF'),  # Nitrogen: Blue
    'S': color.hex('#E6E600'),  # Sulfur: Yellow
    'P': color.hex('#FF8000'),  # Phosphorus: Orange
    'F': color.hex('#00FFEE'),  # Fluorine: Cyan
    'Cl': color.hex('#1FF01F'), # Chlorine: Green
    'Br': color.hex('#A62929'), # Bromine: Dark Red
    'I':  color.hex('#9400D3'), # Iodine: Purple
}

# Physically Accurate Relative Sizes (Based on Van der Waals radii)
ATOM_RADII = {
    'H': 0.40, 'F': 0.50, 'O': 0.58, 'N': 0.60, 
    'C': 0.65, 'Cl': 0.68, 'S': 0.70, 'P': 0.70, 
    'Br': 0.72, 'I': 0.78
}

BOND_THICKNESS = 0.22      # Makes bonds thick and visible
BOND_LENGTH_MULT = 1.75    # Forces bonds to stretch longer (taller)

# ==========================================
# CHEMISTRY STATE
# ==========================================
current_rwmol = Chem.RWMol()
current_entities =[]
molecule_pivot = Entity()

# ==========================================
# USER INTERFACE
# ==========================================
Entity(parent=camera.ui, model='quad', scale=(2, 0.12), position=(0, 0.44), color=color.rgba(0,0,0,0.8))
iupac_text = Text(text=" IUPAC: Loading...", position=(-0.85, 0.48), scale=1.5, color=color.lime)
smiles_text = Text(text="SMILES: ", position=(-0.85, 0.43), scale=1, color=color.light_gray)

error_msg = Text(text="", position=(0, 0.2), origin=(0, 0), scale=2.5, color=color.clear)
action_msg = Text(text="", position=(0, -0.2), origin=(0, 0), scale=2, color=color.clear)

# Bottom Dock
Entity(parent=camera.ui, model='quad', scale=(2, 0.2), position=(0, -0.4), color=color.rgba(0,0,0,0.8))
Text(text="Drag Elements to Build:", position=(-0.85, -0.32), scale=1.2, color=color.white)

def show_msg(msg, is_error=False):
    target = error_msg if is_error else action_msg
    target.text = msg
    target.color = color.red if is_error else color.cyan
    target.animate_color(color.clear, duration=2.5, delay=0.5)

def fetch_iupac(smiles):
    try:
        compounds = pcp.get_compounds(smiles, 'smiles')
        name = compounds[0].iupac_name if compounds else "Unknown Compound"
        iupac_text.text = f" IUPAC: {name}"
    except:
        iupac_text.text = " IUPAC: Offline/Unknown"

def try_update(success_msg=""):
    global current_rwmol
    try:
        Chem.SanitizeMol(current_rwmol)
        render_molecule()
        
        smiles = Chem.MolToSmiles(current_rwmol)
        smiles_text.text = f"SMILES: {smiles}"
        iupac_text.text = " IUPAC: Computing..."
        threading.Thread(target=fetch_iupac, args=(smiles,), daemon=True).start()
        
        if success_msg: show_msg(success_msg)
        return True
    except Exception as e:
        show_msg("INVALID VALENCY! (Blocked)", is_error=True)
        return False

# ==========================================
# INFINITE DRAG & DROP (DISPENSER SYSTEM)
# ==========================================
class DragClone(Entity):
    def __init__(self, symbol, color_code, start_pos):
        super().__init__(parent=camera.ui, model='circle', scale=(0.06, 0.06), position=(start_pos.x, start_pos.y), color=color_code)
        self.symbol = symbol
        self.dragging = True

    def update(self):
        if self.dragging: self.position = mouse.position 

    def input(self, key):
        if key == 'left mouse up' and self.dragging:
            self.dragging = False
            self.drop()

    def drop(self):
        closest_atom_idx = None
        min_dist = math.inf
        
        for ent in current_entities:
            if hasattr(ent, 'atom_idx'):
                dist = (ent.screen_position - mouse.position).length()
                if dist < 0.08 and dist < min_dist:
                    min_dist = dist
                    closest_atom_idx = ent.atom_idx
                        
        if closest_atom_idx is not None:
            add_group_to_atom(closest_atom_idx, self.symbol)
        else:
            show_msg("Drop directly onto an atom!", is_error=True)
            
        destroy(self) 

class ElementDispenser(Entity):
    def __init__(self, symbol, label, color_code, x_pos):
        super().__init__(parent=camera.ui, model='circle', scale=(0.06, 0.06), position=(x_pos, -0.42), color=color_code, collider='sphere')
        self.symbol = symbol
        self.color_code = color_code
        Text(parent=self, text=label, origin=(0,0), scale=12, color=color.white if symbol not in ['H', 'S'] else color.black)
        self.tooltip = Tooltip(f"Drag onto a 3D atom to add {label}")

    def input(self, key):
        if self.hovered and key == 'left mouse down':
            DragClone(self.symbol, self.color_code, mouse.position)

def add_group_to_atom(target_idx, group):
    global current_rwmol
    backup = Chem.RWMol(current_rwmol)
    try:
        if group in['C', 'O', 'N', 'S', 'P', 'F', 'Cl', 'Br', 'I']:
            atomic_num = Chem.GetPeriodicTable().GetAtomicNumber(group)
            new_idx = current_rwmol.AddAtom(Chem.Atom(atomic_num))
            current_rwmol.AddBond(target_idx, new_idx, Chem.BondType.SINGLE)
        elif group == 'OH':
            idx_o = current_rwmol.AddAtom(Chem.Atom(8))
            current_rwmol.AddBond(target_idx, idx_o, Chem.BondType.SINGLE)

        if not try_update(f"Added {group}!"):
            current_rwmol = backup
    except:
        current_rwmol = backup

# Generate Infinite Dispensers
ElementDispenser('C', 'C', ATOM_COLORS['C'], -0.65)
ElementDispenser('O', 'O', ATOM_COLORS['O'], -0.52)
ElementDispenser('N', 'N', ATOM_COLORS['N'], -0.39)
ElementDispenser('S', 'S', ATOM_COLORS['S'], -0.26)  
ElementDispenser('P', 'P', ATOM_COLORS['P'], -0.13)  
ElementDispenser('F', 'F', ATOM_COLORS['F'], 0.00)
ElementDispenser('Cl', 'Cl', ATOM_COLORS['Cl'], 0.13)
ElementDispenser('Br', 'Br', ATOM_COLORS['Br'], 0.26)
ElementDispenser('I', 'I', ATOM_COLORS['I'], 0.39)   
ElementDispenser('OH', '-OH', color.hex('#B32424'), 0.54)

# ==========================================
# INTERACTIVE BOND SYSTEM
# ==========================================
class InteractiveBond(Entity):
    def __init__(self, idx1, idx2, current_order, **kwargs):
        super().__init__(**kwargs)
        self.idx1 = idx1
        self.idx2 = idx2
        self.order = current_order
        next_order = "Double" if current_order == 1 else "Triple" if current_order == 2 else "Single"
        self.tooltip = Tooltip(f"Click → Make {next_order} Bond")

    def on_click(self):
        global current_rwmol
        backup = Chem.RWMol(current_rwmol)
        bond = current_rwmol.GetBondBetweenAtoms(self.idx1, self.idx2)
        
        new_t = Chem.BondType.DOUBLE if self.order == 1 else Chem.BondType.TRIPLE if self.order == 2 else Chem.BondType.SINGLE
        bond.SetBondType(new_t)
        
        name = "Double" if self.order == 1 else "Triple" if self.order == 2 else "Single"
        if not try_update(f"Bond changed to {name}!"):
            current_rwmol = backup 

def get_bond_offsets(p1, p2, order):
    if order == 1: return [Vec3(0,0,0)]
    direction = (p2 - p1).normalized()
    up = Vec3(0, 1, 0)
    if abs(direction.dot(up)) > 0.99: up = Vec3(1, 0, 0)
    perp = direction.cross(up).normalized()
    
    gap = 0.40 # Gap width for multiple cylinders
    if order == 2: return[perp * (gap/2), -perp * (gap/2)]
    return [Vec3(0,0,0), perp * gap, -perp * gap]

# ==========================================
# FLAWLESS 3D RENDERING ENGINE
# ==========================================
def render_molecule():
    for e in current_entities: destroy(e)
    current_entities.clear()

    mol_3d = Chem.AddHs(current_rwmol.GetMol())
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    if AllChem.EmbedMolecule(mol_3d, params) == -1:
        AllChem.Compute2DCoords(mol_3d) 
    try: 
        AllChem.MMFFOptimizeMolecule(mol_3d, maxIters=500, nonBondedThresh=100.0)
    except: pass
        
    conf = mol_3d.GetConformer()

    # 1. Render Atoms
    for i in range(current_rwmol.GetNumAtoms()):
        sym = current_rwmol.GetAtomWithIdx(i).GetSymbol()
        # Scale the coordinates so bonds become taller/longer
        pos = Vec3(*conf.GetAtomPosition(i)) * BOND_LENGTH_MULT
        rad = ATOM_RADII.get(sym, 0.5)
        
        ent = Entity(model='sphere', color=ATOM_COLORS.get(sym, color.gray), parent=molecule_pivot, position=pos)
        ent.atom_idx = i 
        ent.scale = 0 
        ent.animate_scale(rad * 2, duration=0.3, curve=curve.out_back)
        current_entities.append(ent)

    # 2. Render Half-Colored Z-Cylinders for Bonds
    for bond in current_rwmol.GetBonds():
        idx1, idx2 = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        p1 = Vec3(*conf.GetAtomPosition(idx1)) * BOND_LENGTH_MULT
        p2 = Vec3(*conf.GetAtomPosition(idx2)) * BOND_LENGTH_MULT
        order = int(bond.GetBondTypeAsDouble())
        c1, c2 = ATOM_COLORS.get(current_rwmol.GetAtomWithIdx(idx1).GetSymbol()), ATOM_COLORS.get(current_rwmol.GetAtomWithIdx(idx2).GetSymbol())

        offsets = get_bond_offsets(p1, p2, order)
        for offset in offsets:
            mid = (p1 + p2) * 0.5
            for start, end, col in[(p1, mid, c1), (mid, p2, c2)]:
                dist = (end - start).length()
                
                # Z-Aligned Visual Cylinder
                b_vis = Entity(model=copy(cylinder_mesh), color=col, parent=molecule_pivot)
                b_vis.position = (start + end + offset * 2) * 0.5
                b_vis.scale = Vec3(BOND_THICKNESS, BOND_THICKNESS, dist) # Scaled on Z
                b_vis.look_at(end + offset)
                current_entities.append(b_vis)

                # Z-Aligned Hitbox
                b_hit = InteractiveBond(idx1, idx2, order, parent=molecule_pivot, collider='box', color=color.clear)
                b_hit.position = b_vis.position
                b_hit.scale = Vec3(0.5, 0.5, dist) 
                b_hit.look_at(end + offset)
                current_entities.append(b_hit)

    # 3. Render Hydrogens
    for i in range(current_rwmol.GetNumAtoms(), mol_3d.GetNumAtoms()):
        pos = Vec3(*conf.GetAtomPosition(i)) * BOND_LENGTH_MULT
        ent = Entity(model='sphere', color=ATOM_COLORS['H'], position=pos, parent=molecule_pivot, scale=ATOM_RADII['H']*2)
        current_entities.append(ent)
        
        neighbor_idx = mol_3d.GetAtomWithIdx(i).GetNeighbors()[0].GetIdx()
        p_neighbor = Vec3(*conf.GetAtomPosition(neighbor_idx)) * BOND_LENGTH_MULT
        c_heavy = ATOM_COLORS.get(mol_3d.GetAtomWithIdx(neighbor_idx).GetSymbol())
        mid = (pos + p_neighbor) * 0.5
        
        b1 = Entity(model=copy(cylinder_mesh), color=ATOM_COLORS['H'], parent=molecule_pivot, position=(pos+mid)*0.5, scale=(BOND_THICKNESS, BOND_THICKNESS, (mid-pos).length()))
        b1.look_at(mid)
        b2 = Entity(model=copy(cylinder_mesh), color=c_heavy, parent=molecule_pivot, position=(mid+p_neighbor)*0.5, scale=(BOND_THICKNESS, BOND_THICKNESS, (p_neighbor-mid).length()))
        b2.look_at(p_neighbor)
        current_entities.extend([b1, b2])

# ==========================================
# CONTROLS & ANIMATION
# ==========================================
def reset_mol():
    global current_rwmol
    current_rwmol = Chem.RWMol()
    current_rwmol.AddAtom(Chem.Atom(6)) # Start with Carbon (Methane)
    try_update()

Button(text='Reset Molecule', color=color.orange, position=(0.75, -0.42), scale=(0.2, 0.05), on_click=reset_mol)

camera.z = -15
orbit_speed = 100

def update():
    if mouse.right:
        molecule_pivot.rotation_y += mouse.velocity[0] * orbit_speed
        molecule_pivot.rotation_x -= mouse.velocity[1] * orbit_speed
    if held_keys['left arrow'] or held_keys['a']: molecule_pivot.rotation_y += orbit_speed * time.dt
    if held_keys['right arrow'] or held_keys['d']: molecule_pivot.rotation_y -= orbit_speed * time.dt
    if held_keys['up arrow'] or held_keys['w']: molecule_pivot.rotation_x += orbit_speed * time.dt
    if held_keys['down arrow'] or held_keys['s']: molecule_pivot.rotation_x -= orbit_speed * time.dt

    t = time.time() * 25
    molecule_pivot.position = Vec3(
        math.sin(t) * 0.012, 
        math.cos(t * 1.3) * 0.012, 
        math.sin(t * 0.8) * 0.012
    )

def input(key):
    if key == 'scroll up': camera.z = min(camera.z + 1, -5)
    if key == 'scroll down': camera.z = max(camera.z - 1, -40)

reset_mol()
app.run()