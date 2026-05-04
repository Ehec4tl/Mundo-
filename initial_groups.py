"""
initial_groups.py - Datos iniciales de los 24 grupos
Cada grupo tiene: id, raza, subraza, x, y, poblacion, poder_promedio, traits
"""

from typing import List, Dict, Any
from models import Group, StateType

# Mapeo de coordenadas iniciales para cada subraza
# Distribuidas equitativamente en el mapa 40x30, evitando bordes extremos
INITIAL_POSITIONS = {
    # Humanos (posiciones zona central-norte)
    "Humano_Nevado": (10, 8),
    "Humano_Desértico": (15, 8),
    "Humano_Ciudad": (20, 8),
    
    # Elfos (zona oeste)
    "Elfo_Oscuro": (5, 15),
    "Elfo_Alto": (8, 16),
    "Elfo_Silvano": (12, 14),
    
    # Enanos (zona este)
    "Enano_De_piedra": (30, 15),
    "Enano_Del_metal": (33, 16),
    "Enano_Oscuro": (28, 18),
    
    # Gigantes (zonas montañosas - norte y sur)
    "Gigante_Montaña": (18, 22),
    "Gigante_Nieve": (22, 23),
    "Gigante_Bosque": (25, 25),
    
    # Orcoides (zona sur)
    "Orcoide_Goblin": (15, 27),
    "Orcoide_Orco": (20, 28),
    "Orcoide_Alto_orco": (25, 26),
    
    # Hombres Bestia (zonas costeras - este y oeste)
    "Hombre_Bestia_Tribu_lagarto": (35, 10),
    "Hombre_Bestia_Tribu_perruna": (35, 20),
    "Hombre_Bestia_Tribu_gatuna": (35, 25),
    
    # Constructos (zonas centrales)
    "Constructo_Gólem_de_Roca": (8, 25),
    "Constructo_Autómata": (12, 20),
    "Constructo_Centinela_Arcano": (28, 8),
    
    # Medianos (zonas centrales bajas)
    "Mediano_Pies_Ligeros": (18, 18),
    "Mediano_Fornido": (22, 15),
    "Mediano_Peloso": (25, 12),
}

# Rasgos por subraza (según manual)
RACE_TRAITS = {
    # Humanos
    "Humano_Nevado": {"La caza helada", "Nómada". "Navegante"},
    "Humano_Desértico": {"Acosador", "Nómada", "Navegante"},
    "Humano_Ciudad": {"Metrópolis", "Expansionista"},
    
    # Elfos
    "Elfo_Oscuro": {"Como una sombra", "Navegante"},
    "Elfo_Alto": {"Solo lo mejor", "Navegante"},
    "Elfo_Silvano": {"Uno con la vida", "Nómada", "Navegante"},
    
    # Enanos
    "Enano_De_piedra": {"Como una joya", "Expansionista"},
    "Enano_Del_metal": {"Herreros Legendarios"},
    "Enano_Oscuro": {"Runa de guerra", "Asediadores"},
    
    # Gigantes
    "Gigante_Montaña": {"Como las leyendas"},
    "Gigante_Nieve": {"Congelar", "Crecimiento Exponencial"},
    "Gigante_Bosque": {"Guardián de la Naturaleza"},
    
    # Orcoides
    "Orcoide_Goblin": {"El más débil"},
    "Orcoide_Orco": {"Buscapleitos", "Crecimiento Exponencial", "Asediadores"},
    "Orcoide_Alto_orco": {"El miedo no está en el músculo", "Expansionista"},
    
    # Hombres Bestia
    "Hombre_Bestia_Tribu_lagarto": {"Anfibio", "Navegante"},
    "Hombre_Bestia_Tribu_perruna": {"Manada"},
    "Hombre_Bestia_Tribu_gatuna": {"Reflejos Felinos"},
    
    # Constructos
    "Constructo_Gólem_de_Roca": {"De piedra"},
    "Constructo_Autómata": {"Precisos"},
    "Constructo_Centinela_Arcano": {"Guardián del Orden"},
    
    # Medianos
    "Mediano_Pies_Ligeros": {"Pies ligeros", "Nómada"},
    "Mediano_Fornido": {"Duros"},
    "Mediano_Peloso": {"Amigos distantes"},
}

# Población inicial estándar
BASE_POPULATION = 1000
BASE_POWER_AVG = 350.0

# Poblaciones especiales (ajustes de balance)
SPECIAL_POPULATIONS = {
    "Orcoide_Goblin": 1500,  # Goblin más numeroso
    "Constructo_Gólem_de_Roca": 500,  # Gólem menos numeroso
    "Constructo_Autómata": 500,
    "Gigante_Montaña": 300,  # Gigantes menos numerosos
    "Gigante_Nieve": 300,
    "Gigante_Bosque": 300,
}


def create_initial_groups(next_id: int = 1) -> List[Group]:
    """
    Crea la lista de grupos iniciales.
    
    Args:
        next_id: ID inicial (normalmente 1)
        
    Returns:
        Lista de objetos Group
    """
    groups = []
    current_id = next_id
    
    for subrace_key, (x, y) in INITIAL_POSITIONS.items():
        # Extraer raza y subraza
        parts = subrace_key.split("_")
        if len(parts) >= 2:
            # Caso especial: "Hombre_Bestia_Tribu_xxx"
            if subrace_key.startswith("Hombre_Bestia"):
                raza = "Hombre Bestia"
                subraza = subrace_key.replace("Hombre_Bestia_", "").replace("_", " ")
            else:
                raza = parts[0]
                subraza = " ".join(parts[1:])
        else:
            raza = parts[0]
            subraza = ""
        
        # Población (con special si aplica)
        population = SPECIAL_POPULATIONS.get(subrace_key, BASE_POPULATION)
        
        # Poder promedio (con special si aplica)
        power_avg = BASE_POWER_AVG
        
        # Rasgos
        traits = RACE_TRAITS.get(subrace_key, set())
        
        # Crear grupo
        group = Group(
            id=current_id,
            raza=raza,
            subraza=subraza,
            x=x,
            y=y,
            poblacion=population,
            poder_promedio=power_avg,
            estados={},
            asentamiento_id=None,
            grupo_original_id=None,
            reputacion={},
            acted_this_round=False,
            created_in_round=0,
            last_action_was_grow=False,
            traits=traits
        )
        
        groups.append(group)
        current_id += 1
    
    return groups


def get_group_count() -> int:
    """Retorna el número de grupos iniciales."""
    return len(INITIAL_POSITIONS)


def print_groups_summary(groups: List[Group]) -> None:
    """Imprime un resumen de los grupos creados."""
    print("\n" + "=" * 80)
    print("GRUPOS INICIALES CREADOS")
    print("=" * 80)
    
    for group in groups:
        traits_str = ", ".join(group.traits) if group.traits else "Ninguno"
        print(f"ID:{group.id:2d} | {group.raza:12s} | {group.subraza:25s} | "
              f"Pos:({group.x:2d},{group.y:2d}) | Pop:{group.poblacion:4d} | "
              f"Poder:{group.poder_promedio:.0f} | Rasgos:[{traits_str}]")
    
    print("=" * 80)
    print(f"Total grupos: {len(groups)}")
    print("=" * 80)


# Prueba rápida
if __name__ == "__main__":
    groups = create_initial_groups()
    print_groups_summary(groups)