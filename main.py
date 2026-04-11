import math
import threading
import pubchempy as pcp
from ursina import *
from ursina.shaders import lit_with_shadows_shader
from rdkit import Chem
from rdkit.Chem import AllChem

# APP & STUDIO LIGHTING
app = Ursina(title='CarbonCraft', size=(1600, 900), borderless=False, vsync=True)
window.color = color.black 
window.icon = r"textures/ursina.ico"

def make_z_aligned_cylinder(segments=64):
    """Extrudes a flawless cylinder along the Z-axis with correct 3D normals"""
    verts = []
    tris = []
    # Build shared vertex rings for smooth normals
    for i in range(segments):
        a = 2 * math.pi * i / segments
        c, s = math.cos(a), math.sin(a)
        verts.append(Vec3(c, s, -0.5))
        verts.append(Vec3(c, s, 0.5))

    for i in range(segments):
        next_i = (i + 1) % segments
        v0 = i * 2
        v1 = i * 2 + 1
        v2 = next_i * 2
        v3 = next_i * 2 + 1
        tris.extend([
            v0, v1, v2,
            v1, v3, v2
        ])

    m = Mesh(vertices=verts, triangles=tris)
    m.generate_normals(smooth=True)
    return m

cylinder_mesh = make_z_aligned_cylinder()

# High-poly procedural sphere for atoms (precompute mesh and smooth normals)
def make_high_poly_sphere(latitude_bands=32, longitude_bands=32):
    verts, tris = [], []
    for lat_number in range(latitude_bands + 1):
        theta = lat_number * math.pi / latitude_bands
        sin_theta, cos_theta = math.sin(theta), math.cos(theta)

        for long_number in range(longitude_bands + 1):
            phi = long_number * 2 * math.pi / longitude_bands
            sin_phi, cos_phi = math.sin(phi), math.cos(phi)
            x, y, z = cos_phi * sin_theta, cos_theta, sin_phi * sin_theta
            verts.append(Vec3(x, y, z) * 0.5)

    for lat_number in range(latitude_bands):
        for long_number in range(longitude_bands):
            first = (lat_number * (longitude_bands + 1)) + long_number
            second = first + longitude_bands + 1
            if lat_number != 0:
                tris.extend([first, second, first + 1])
            if lat_number != (latitude_bands - 1):
                tris.extend([first + 1, second, second + 1])

    m = Mesh(vertices=verts, triangles=tris)
    # normals from positions give a smooth, perfect sphere
    m.normals = [v.normalized() for v in verts]
    return m

sphere_mesh = make_high_poly_sphere()

# Real CPK Colors 
ATOM_COLORS = {
    'C': color.hex('#282828'),      # Dark grey, almost black
    'H': color.hex('#E6E6E6'),      # Pure white/light grey
    'O': color.hex('#D20000'),      # Deep saturated red
    'N': color.hex('#3250C8'),      # Deep blue
    'S': color.hex('#C8C800'),      # Yellow
    'P': color.hex('#C86400'),      # Orange
    'F': color.hex('#00C896'),      # Greenish cyan
    'Cl': color.hex('#00C800'),     # Green
    'Br': color.hex('#961E1E'),     # Dark red-brown
    'I':  color.hex('#780096'),     # Purple
}


# Physically Accurate Relative Sizes (Based on Van der Waals radii)
ATOM_RADII = {
    'H': 0.40, 'F': 0.50, 'O': 0.58, 'N': 0.60, 
    'C': 0.65, 'Cl': 0.68, 'S': 0.70, 'P': 0.70, 
    'Br': 0.72, 'I': 0.78
}

BOND_THICKNESS = 0.22      
BOND_LENGTH_MULT = 1.75    

# CHEMISTRY STATE
current_rwmol = Chem.RWMol()
current_entities =[]
molecule_pivot = Entity()

# USER INTERFACE
Entity(parent=camera.ui, model='quad', scale=(2, 0.12), position=(0, 0.44, 0.2), color=color.rgba(0,0,0,0.8))
iupac_text = Text(text=" IUPAC: Loading...", position=(-0.85, 0.48), scale=1.5, color=color.lime)
smiles_text = Text(text="SMILES: ", position=(-0.85, 0.43), scale=1, color=color.light_gray)
functional_groups_text = Text(text="Functional Groups: None", position=(-0.85, 0.38), scale=0.9, color=color.white)

error_msg = Text(text="", position=(0, 0.2), origin=(0, 0), scale=2.5, color=color.clear)
action_msg = Text(text="", position=(0, -0.2), origin=(0, 0), scale=2, color=color.clear)

# Bottom Dock
Entity(parent=camera.ui, model='quad', scale=(2, 0.2), position=(0, -0.4, 0.2), color=color.rgba(0,0,0,0.8))
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
        functional_groups_text.text = format_functional_groups(detect_functional_groups(current_rwmol.GetMol()))
        iupac_text.text = " IUPAC: Computing..."
        threading.Thread(target=fetch_iupac, args=(smiles,), daemon=True).start()
        
        if success_msg: show_msg(success_msg)
        return True
    except Exception as e:
        show_msg("INVALID VALENCY! (Blocked)", is_error=True)
        return False

def get_contrast_text_color(bg_color):
    luminance = (0.299 * bg_color.r) + (0.587 * bg_color.g) + (0.114 * bg_color.b)
    return color.black if luminance > 0.55 else color.white

FUNCTIONAL_GROUP_PATTERNS = [
    ("Carboxylic acid", "C(=O)[OX2H1]"),
    ("Ester", "C(=O)O[#6]"),
    ("Amide", "C(=O)N"),
    ("Aldehyde", "[CX3H1](=O)[#6]"),
    ("Ketone", "[#6][CX3](=O)[#6]"),
    ("Alcohol", "[OX2H][CX4]"),
    ("Phenol", "c[OX2H]"),
    ("Amine", "[NX3;H2,H1,H0;!$(NC=O)]"),
    ("Nitrile", "C#N"),
    ("Sulfide", "C[S]C"),
    ("Thiol", "CS"),
    ("Ether", "C[OX2]C"),
    ("Alkane", "C"),
    ("Alkene", "C=C"),
    ("Alkyne", "C#C"),
    ("Halide", "[F,Cl,Br,I]"),
]

def detect_functional_groups(mol):
    found_groups = []

    # Only report Alkane when no Alkene or Alkyne are present.
    alkane_smarts = None
    for name, smarts in FUNCTIONAL_GROUP_PATTERNS:
        if name == 'Alkane':
            alkane_smarts = smarts
            continue
        pattern = Chem.MolFromSmarts(smarts)
        if pattern is not None and mol.HasSubstructMatch(pattern):
            found_groups.append(name)

    # If neither Alkene nor Alkyne were found, check for Alkane
    if alkane_smarts is not None and 'Alkene' not in found_groups and 'Alkyne' not in found_groups:
        alkane_pat = Chem.MolFromSmarts(alkane_smarts)
        if alkane_pat is not None and mol.HasSubstructMatch(alkane_pat):
            found_groups.append('Alkane')

    return found_groups

def format_functional_groups(groups):
    if not groups:
        return "Functional Groups: None detected"
    return "Functional Groups: " + ", ".join(groups)

# INFINITE DRAG & DROP (DISPENSER SYSTEM)
class DragClone(Entity):
    def __init__(self, symbol, color_code, start_pos):
        super().__init__(parent=camera.ui, model='circle', scale=(0.06, 0.06), position=(start_pos.x, start_pos.y, -0.02), color=color_code)
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
        super().__init__(parent=camera.ui, model='circle', scale=(0.06, 0.06), position=(x_pos, -0.42, -0.01), color=color_code, collider='sphere')
        self.symbol = symbol
        self.color_code = color_code
        Text(parent=self, text=label, origin=(0,0), scale=16, color=get_contrast_text_color(color_code))
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

# INTERACTIVE BOND SYSTEM
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
    if order <= 1: return [Vec3(0,0,0)]
    direction = (p2 - p1).normalized()
    perp = direction.cross(Vec3(0, 0, 1)).normalized()
    if perp.length() < 0.1: perp = direction.cross(Vec3(0, 1, 0)).normalized()
    gap = 0.22 # 

    if order == 2: return[perp * (gap*0.9), -perp * (gap*0.9)]
    if order == 3: return [Vec3(0,0,0), perp * (gap*1.5), -perp * (gap*1.5)]
    return [Vec3(0,0,0)]


# FLAWLESS 3D RENDERING ENGINE
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
        
        ent = Entity(model=copy(sphere_mesh), shader=lit_with_shadows_shader, color=ATOM_COLORS.get(sym, color.gray), parent=molecule_pivot, position=pos)
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

        visual_thickness = BOND_THICKNESS if order == 1 else BOND_THICKNESS * 0.6

        offsets = get_bond_offsets(p1, p2, order)
        for offset in offsets:
            start_offset = p1 + offset
            end_offset = p2 + offset
            mid_offset = (start_offset + end_offset) * 0.5

            start, end = p1 + offset, p2 + offset
            mid = (start + end) * 0.5
            for seg_start, seg_end, col in[(start_offset, mid_offset, c1), (mid_offset, end_offset, c2)]:
                dist = (seg_end - seg_start).length()
                
                # Z-Aligned Visual Cylinder (use lit shader for glossy/plastic look)
                b_vis = Entity(model=copy(cylinder_mesh), shader=lit_with_shadows_shader, color=col, parent=molecule_pivot, double_sided=True)
                b_vis.position = (seg_start + seg_end) * 0.5
                b_vis.scale = Vec3(visual_thickness, visual_thickness, dist) # Scaled on Z
                b_vis.look_at(seg_end)
                current_entities.append(b_vis)

                # Z-Aligned Hitbox
                b_hit = InteractiveBond(idx1, idx2, order, parent=molecule_pivot, collider='box', color=color.clear)
                b_hit.position = (p1 + p2) * 0.5
                b_hit.scale = Vec3(0.5, 0.5, (p2 - p1).length() * 1.1)
                b_hit.look_at(p2)
                current_entities.append(b_hit)

    # 3. Render Hydrogens
    for i in range(current_rwmol.GetNumAtoms(), mol_3d.GetNumAtoms()):
        pos = Vec3(*conf.GetAtomPosition(i)) * BOND_LENGTH_MULT
        ent = Entity(model=copy(sphere_mesh), shader=lit_with_shadows_shader, color=ATOM_COLORS['H'], position=pos, parent=molecule_pivot, scale=ATOM_RADII['H']*2)
        current_entities.append(ent)

        neighbor_idx = mol_3d.GetAtomWithIdx(i).GetNeighbors()[0].GetIdx()
        p_neighbor = Vec3(*conf.GetAtomPosition(neighbor_idx)) * BOND_LENGTH_MULT
        c_heavy = ATOM_COLORS.get(mol_3d.GetAtomWithIdx(neighbor_idx).GetSymbol())
        mid = (pos + p_neighbor) * 0.5
        b1 = Entity(model=copy(cylinder_mesh), shader=lit_with_shadows_shader, color=ATOM_COLORS['H'], parent=molecule_pivot, position=(pos+mid)*0.5, scale=(BOND_THICKNESS, BOND_THICKNESS, (mid-pos).length()), double_sided=True)
        b1.look_at(mid)
        b2 = Entity(model=copy(cylinder_mesh), shader=lit_with_shadows_shader, color=c_heavy, parent=molecule_pivot, position=(mid+p_neighbor)*0.5, scale=(BOND_THICKNESS, BOND_THICKNESS, (p_neighbor-mid).length()), double_sided=True)
        b2.look_at(p_neighbor)
        current_entities.extend([b1, b2])

# CONTROLS & ANIMATION
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
