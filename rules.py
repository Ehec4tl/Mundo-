"""
rules.py - Reglas de movimiento, reputación e interacciones entre grupos
TODAS las funciones son PURAS (no modifican estado, no llaman a logger)
"""

import math
import random
from copy import deepcopy
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any, Set
from models import Group, TerrainType, Settlement, StructureType, CityUpgrade, Structure, StateType


# ============================================================================
# Sistema de Construcción (Regla 11) - FUNCIONES PURAS
# ============================================================================

@dataclass
class BuildResult:
    """Resultado de una acción Construir"""
    success: bool
    event_type: str
    details: Dict[str, Any]
    structure: Optional['Structure'] = None
    settlement_updates: Optional[Dict[int, 'Settlement']] = None
    converted_tile: Optional[Tuple[int, int, 'TerrainType']] = None


def can_build_empalizada(group: 'Group', world: 'World') -> Tuple[bool, str]:
    """Verifica si se puede construir Empalizada."""
    tile = world.get_tile(group.x, group.y)
    
    if not tile:
        return False, "invalid_tile"
    
    if tile.has_structure:
        return False, "tile_already_has_structure"
    
    if tile.has_settlement:
        settlement = world.get_settlement(tile.settlement_id)
        if settlement and not settlement.ruinas:
            return False, "cannot_build_on_city"
    
    return True, ""


def can_build_bastion(group: 'Group', world: 'World') -> Tuple[bool, str]:
    """Verifica si se puede construir Bastión."""
    tile = world.get_tile(group.x, group.y)
    
    if not tile:
        return False, "invalid_tile"
    
    if tile.has_structure:
        return False, "tile_already_has_structure"
    
    if tile.has_settlement:
        settlement = world.get_settlement(tile.settlement_id)
        if settlement and not settlement.ruinas:
            return False, "cannot_build_on_city"
    
    return True, ""


def can_build_puente(group: 'Group', world: 'World', direction: str) -> Tuple[bool, str, Optional[Tuple[int, int]]]:
    """Verifica si se puede construir Puente."""
    DIRECTION_VECTORS = {
        'N': (0, -1), 'S': (0, 1),
        'E': (1, 0), 'O': (-1, 0)
    }
    
    if direction not in DIRECTION_VECTORS:
        return False, "invalid_direction", None
    
    dx, dy = DIRECTION_VECTORS[direction]
    bridge_x, bridge_y = group.x + dx, group.y + dy
    
    if not world.is_valid_coordinates(bridge_x, bridge_y):
        return False, "bridge_out_of_bounds", None
    
    target_tile = world.get_tile(bridge_x, bridge_y)
    
    if not target_tile:
        return False, "invalid_target_tile", None
    
    if target_tile.terreno != TerrainType.AGUA:
        return False, "bridge_must_be_on_water", None
    
    if target_tile.has_structure:
        return False, "tile_already_has_structure", None
    
    if target_tile.has_settlement:
        settlement = world.get_settlement(target_tile.settlement_id)
        if settlement and not settlement.ruinas:
            return False, "cannot_build_bridge_on_city", None
    
    return True, "", (bridge_x, bridge_y)


def can_build_city_fortaleza(group: 'Group', world: 'World') -> Tuple[bool, str]:
    """Verifica si se puede construir Ciudad Fortaleza."""
    tile = world.get_tile(group.x, group.y)
    
    if not tile:
        return False, "invalid_tile"
    
    if tile.has_settlement:
        return False, "tile_already_has_settlement"
    
    if tile.has_structure:
        return False, "tile_already_has_structure"
    
    # Verificar radio de influencia (R21.2)
    for settlement in world.get_all_settlements():
        if settlement.ruinas:
            continue
        
        radius = calculate_influence_radius(settlement.nivel)
        if radius > 0:
            distance = abs(group.x - settlement.x) + abs(group.y - settlement.y)
            if distance <= radius:
                return False, f"within_radius_of_settlement_{settlement.id}"
    
    return True, ""


def can_build_city_upgrade(group: 'Group', world: 'World', 
                          upgrade: CityUpgrade, settlement: 'Settlement') -> Tuple[bool, str]:
    """Verifica si se puede construir mejora de ciudad."""
    if settlement.dueño_grupo_id != group.id:
        return False, "not_owner_of_settlement"
    
    if settlement.has_upgrade(upgrade):
        return False, "upgrade_already_exists"
    
    level_required = {
        CityUpgrade.HOSPITAL: 2,
        CityUpgrade.CARRETERAS: 3,
        CityUpgrade.VIVIENDAS_MEJORES: 4,
        CityUpgrade.LUGAR_EMBLEMATICO: 5
    }
    
    if settlement.nivel < level_required[upgrade]:
        return False, f"requires_level_{level_required[upgrade]}"
    
    if settlement.get_available_slots() <= 0:
        return False, "max_structures_reached"
    
    radius = calculate_influence_radius(settlement.nivel)
    distance = abs(group.x - settlement.x) + abs(group.y - settlement.y)
    
    if distance > radius:
        return False, "group_outside_influence_radius"
    
    return True, ""


def build_empalizada(group: 'Group', world: 'World', 
                    round_number: int, rng: random.Random) -> BuildResult:
    """Construye Empalizada."""
    can_build, reason = can_build_empalizada(group, world)
    
    if not can_build:
        return BuildResult(
            success=False,
            event_type="BUILD_FAILED",
            details={
                "group_id": group.id,
                "structure_type": "EMPALIZADA",
                "position": (group.x, group.y),
                "reason": reason
            }
        )
    
    structure = Structure(
        tipo=StructureType.EMPALIZADA,
        x=group.x,
        y=group.y,
        grupo_constructor_id=group.id,
        ronda_construccion=round_number
    )
    
    return BuildResult(
        success=True,
        event_type="BUILD_SUCCESS",
        details={
            "group_id": group.id,
            "structure_type": "EMPALIZADA",
            "position": (group.x, group.y),
            "blocks_movement": True
        },
        structure=structure
    )


def build_bastion(group: 'Group', world: 'World', 
                 round_number: int, rng: random.Random) -> BuildResult:
    """Construye Bastión."""
    can_build, reason = can_build_bastion(group, world)
    
    if not can_build:
        return BuildResult(
            success=False,
            event_type="BUILD_FAILED",
            details={
                "group_id": group.id,
                "structure_type": "BASTION",
                "position": (group.x, group.y),
                "reason": reason
            }
        )
    
    structure = Structure(
        tipo=StructureType.BASTION,
        x=group.x,
        y=group.y,
        grupo_constructor_id=group.id,
        ronda_construccion=round_number
    )
    
    return BuildResult(
        success=True,
        event_type="BUILD_SUCCESS",
        details={
            "group_id": group.id,
            "structure_type": "BASTION",
            "position": (group.x, group.y),
            "blocks_movement": False
        },
        structure=structure
    )


def build_puente(group: 'Group', world: 'World', direction: str,
                round_number: int, rng: random.Random) -> BuildResult:
    """Construye Puente."""
    can_build, reason, bridge_coords = can_build_puente(group, world, direction)
    
    if not can_build:
        return BuildResult(
            success=False,
            event_type="BUILD_FAILED",
            details={
                "group_id": group.id,
                "structure_type": "PUENTE",
                "position": (group.x, group.y),
                "direction": direction,
                "reason": reason
            }
        )
    
    bridge_x, bridge_y = bridge_coords
    
    structure = Structure(
        tipo=StructureType.PUENTE,
        x=bridge_x,
        y=bridge_y,
        grupo_constructor_id=group.id,
        ronda_construccion=round_number
    )
    
    return BuildResult(
        success=True,
        event_type="BUILD_SUCCESS",
        details={
            "group_id": group.id,
            "structure_type": "PUENTE",
            "position": (group.x, group.y),
            "bridge_position": (bridge_x, bridge_y),
            "direction": direction,
            "blocks_movement": False
        },
        structure=structure,
        converted_tile=(bridge_x, bridge_y, None)
    )


def build_city_fortaleza(group: 'Group', world: 'World', 
                        round_number: int, rng: random.Random,
                        next_settlement_id: int) -> BuildResult:
    """Construye Ciudad Fortaleza."""
    can_build, reason = can_build_city_fortaleza(group, world)
    
    if not can_build:
        return BuildResult(
            success=False,
            event_type="BUILD_FAILED",
            details={
                "group_id": group.id,
                "structure_type": "CIUDAD_FORTALEZA",
                "position": (group.x, group.y),
                "reason": reason
            }
        )
    
    settlement = Settlement(
        id=next_settlement_id,
        nivel=1,
        x=group.x,
        y=group.y,
        puntos_ciudad=math.ceil(1000.0),
        fundado_en_ronda=round_number,
        dueño_grupo_id=group.id,
        ruinas=False,
        mejoras=[],
        raza=group.raza,
        subraza=group.subraza,
        created_round=round_number,
        influence_radius=[]
    )
    
    structure = Structure(
        tipo=StructureType.CIUDAD_FORTALEZA,
        x=group.x,
        y=group.y,
        grupo_constructor_id=group.id,
        ronda_construccion=round_number
    )
    
    return BuildResult(
        success=True,
        event_type="BUILD_SUCCESS",
        details={
            "group_id": group.id,
            "structure_type": "CIUDAD_FORTALEZA",
            "position": (group.x, group.y),
            "settlement_id": settlement.id,
            "blocks_movement": True
        },
        structure=structure,
        settlement_updates={settlement.id: settlement}
    )


def build_city_upgrade(group: 'Group', world: 'World', 
                      upgrade: CityUpgrade, settlement_id: int,
                      round_number: int, rng: random.Random) -> BuildResult:
    """Construye mejora de ciudad."""
    settlement = world.get_settlement(settlement_id)
    
    if not settlement:
        return BuildResult(
            success=False,
            event_type="BUILD_FAILED",
            details={
                "group_id": group.id,
                "upgrade_type": upgrade.value,
                "settlement_id": settlement_id,
                "reason": "settlement_not_found"
            }
        )
    
    can_build, reason = can_build_city_upgrade(group, world, upgrade, settlement)
    
    if not can_build:
        return BuildResult(
            success=False,
            event_type="BUILD_FAILED",
            details={
                "group_id": group.id,
                "upgrade_type": upgrade.value,
                "settlement_id": settlement_id,
                "position": (group.x, group.y),
                "reason": reason
            }
        )
    
    updated_settlement = Settlement(
        id=settlement.id,
        nivel=settlement.nivel,
        x=settlement.x,
        y=settlement.y,
        puntos_ciudad=settlement.puntos_ciudad,
        fundado_en_ronda=settlement.fundado_en_ronda,
        dueño_grupo_id=settlement.dueño_grupo_id,
        ruinas=settlement.ruinas,
        mejoras=settlement.mejoras.copy(),
        raza=settlement.raza,
        subraza=settlement.subraza,
        created_round=settlement.created_round,
        influence_radius=settlement.influence_radius.copy()
    )
    updated_settlement.add_upgrade(upgrade)
    
    level_required = {
        CityUpgrade.HOSPITAL: 2,
        CityUpgrade.CARRETERAS: 3,
        CityUpgrade.VIVIENDAS_MEJORES: 4,
        CityUpgrade.LUGAR_EMBLEMATICO: 5
    }
    
    return BuildResult(
        success=True,
        event_type="CITY_UPGRADE_ADDED",
        details={
            "group_id": group.id,
            "upgrade_type": upgrade.value,
            "settlement_id": settlement_id,
            "position": (group.x, group.y),
            "required_level": level_required[upgrade],
            "current_level": settlement.nivel,
            "slots_used": len(updated_settlement.mejoras),
            "max_slots": updated_settlement.get_max_structures()
        },
        settlement_updates={settlement_id: updated_settlement}
    )


def destroy_structure(group: 'Group', world: 'World', 
                     structure: Structure, round_number: int) -> BuildResult:
    """Destruye una estructura existente."""
    if structure.tipo == StructureType.EMPALIZADA:
        distance = abs(group.x - structure.x) + abs(group.y - structure.y)
        if distance != 1:
            return BuildResult(
                success=False,
                event_type="BUILD_FAILED",
                details={
                    "group_id": group.id,
                    "action": "DESTROY",
                    "structure_type": structure.tipo.value,
                    "structure_position": (structure.x, structure.y),
                    "group_position": (group.x, group.y),
                    "reason": "must_be_adjacent_to_destroy_empalizada"
                }
            )
    else:
        if group.x != structure.x or group.y != structure.y:
            return BuildResult(
                success=False,
                event_type="BUILD_FAILED",
                details={
                    "group_id": group.id,
                    "action": "DESTROY",
                    "structure_type": structure.tipo.value,
                    "structure_position": (structure.x, structure.y),
                    "group_position": (group.x, group.y),
                    "reason": "must_be_on_same_tile_to_destroy"
                }
            )
    
    return BuildResult(
        success=True,
        event_type="STRUCTURE_DESTROYED",
        details={
            "group_id": group.id,
            "structure_type": structure.tipo.value,
            "structure_position": (structure.x, structure.y),
            "destroyed_by": group.id,
            "round": round_number
        },
        structure=None
    )


def calculate_disabled_upgrades(settlement: 'Settlement', new_level: int) -> List[CityUpgrade]:
    """
    Calcula qué mejoras quedarían desactivadas si se degrada a new_level.
    FUNCIÓN PURA - no modifica el settlement original.
    """
    level_required = {
        CityUpgrade.HOSPITAL: 2,
        CityUpgrade.CARRETERAS: 3,
        CityUpgrade.VIVIENDAS_MEJORES: 4,
        CityUpgrade.LUGAR_EMBLEMATICO: 5
    }
    
    disabled = []
    for upgrade in settlement.mejoras:
        if new_level < level_required.get(upgrade, 0):
            disabled.append(upgrade)
    return disabled


# ============================================================================
# Estructuras de resultado (PURAS - sin efectos secundarios)
# ============================================================================

@dataclass
class MoveResult:
    """Resultado de un intento de movimiento."""
    success: bool
    new_x: int
    new_y: int
    event_type: str
    details: dict
    interaction_groups: Optional[List[int]] = None


@dataclass
class ReputationChange:
    """Cambio de reputación entre dos grupos."""
    group_id_a: int
    group_id_b: int
    delta: int
    old_value_a: int
    old_value_b: int
    new_value_a: int
    new_value_b: int


@dataclass
class MergeResult:
    """Resultado de una posible unión entre grupos."""
    success: bool
    absorbing_group_id: int
    absorbed_group_id: int
    new_population: int
    new_power: float
    reason: Optional[str] = None


# ============================================================================
# Constantes
# ============================================================================

DIRECTIONS = ['N', 'S', 'E', 'O']
DIRECTION_VECTORS = {
    'N': (0, -1),
    'S': (0, 1),
    'E': (1, 0),
    'O': (-1, 0)
}
OPPOSITE_DIRECTION = {
    'N': 'S',
    'S': 'N',
    'E': 'O',
    'O': 'E'
}

# Tabla de probabilidad hostil según nivel de reputación (R13.2)
HOSTILE_PROBABILITY = {
    1: 0.75,  # Enemigos
    2: 0.70,  # Muy Hostiles
    3: 0.60,  # Hostiles
    4: 0.50,  # Neutrales
    5: 0.40,  # Conocidos
    6: 0.30,  # Aliados
    7: 0.25,  # Amigos
}

# Estados de combate para inmunidades (Módulo 14 y 15A)
# CORREGIDO: Usar los valores reales del Enum StateType
COMBAT_STATES = {
    "Sorpresa", "Miedo", "Terroífico", "Desmoralizado",
    "Inspirados", "Entorpecido", "Fortaleza"
}


# ============================================================================
# Sistema de reputación (R17) - FUNCIONES PURAS
# ============================================================================

def get_reputation(group: Group, other_group_id: int) -> int:
    """Obtiene la reputación de un grupo hacia otro."""
    return group.reputacion.get(other_group_id, 4)


def calculate_reputation_change(current_a: int, current_b: int, delta: int) -> Tuple[int, int]:
    """Calcula los nuevos valores de reputación después de un cambio."""
    new_a = max(1, min(7, current_a + delta))
    new_b = max(1, min(7, current_b + delta))
    return (new_a, new_b)


# ============================================================================
# Interacciones entre grupos (R13) - FUNCIONES PURAS
# ============================================================================

def choose_interaction_type(rep_level: int, rng: random.Random) -> str:
    """Decide si una interacción es hostil o pacífica según tabla R13.2."""
    prob_hostil = HOSTILE_PROBABILITY.get(rep_level, 0.50)
    return "HOSTIL" if rng.random() < prob_hostil else "PACIFICO"


def get_stack_reputation(group_c: Group, stack_groups: List[Group]) -> int:
    """Calcula la reputación promedio (ceil) entre un grupo y un stack de subgrupos."""
    if not stack_groups:
        return 4
    
    total_reputation = 0
    for g in stack_groups:
        total_reputation += get_reputation(group_c, g.id)
    
    avg = total_reputation / len(stack_groups)
    return math.ceil(avg)


def group_by_origin(groups: List[Group]) -> Dict[Optional[int], List[Group]]:
    """Agrupa grupos por su grupo_original_id."""
    stacks: Dict[Optional[int], List[Group]] = {}
    
    for group in groups:
        if not group.alive:
            continue
        origin_id = group.grupo_original_id if group.grupo_original_id is not None else group.id
        if origin_id not in stacks:
            stacks[origin_id] = []
        stacks[origin_id].append(group)
    
    return stacks


# ============================================================================
# Sistema de unión (R18) - FUNCIÓN PURA
# ============================================================================

def calculate_merge(
    origin_id_a: int, origin_id_b: int,
    subrace_a: str, subrace_b: str,
    reputation_a_to_b: int, reputation_b_to_a: int,
    population_a: int, population_b: int,
    power_a: float, power_b: float
) -> Tuple[bool, int, float, Optional[str]]:
    """Calcula si dos grupos pueden unirse (R18)."""
    if subrace_a != subrace_b:
        return False, 0, 0.0, "different_subrace"
    
    if origin_id_a != origin_id_b:
        return False, 0, 0.0, "different_origin"
    
    if reputation_a_to_b != 7 or reputation_b_to_a != 7:
        return False, 0, 0.0, "reputation_not_7"
    
    total_pop = population_a + population_b
    if total_pop > 0:
        new_power = math.ceil(
            (power_a * population_a + power_b * population_b) / total_pop
        )
    else:
        new_power = 0.0
    
    return True, total_pop, new_power, None


# ============================================================================
# Funciones de movimiento - FUNCIONES PURAS
# ============================================================================

def _get_new_coords(x: int, y: int, direction: str) -> Tuple[int, int]:
    dx, dy = DIRECTION_VECTORS[direction]
    return (x + dx, y + dy)


def _get_valid_directions(world: 'World', x: int, y: int, 
                          exclude_direction: str = None) -> List[str]:
    valid = []
    for direction in DIRECTIONS:
        if exclude_direction and direction == exclude_direction:
            continue
        new_x, new_y = _get_new_coords(x, y, direction)
        if world.is_valid_coordinates(new_x, new_y):
            valid.append(direction)
    return valid


def _is_water_with_group(world: 'World', x: int, y: int) -> bool:
    tile = world.get_tile(x, y)
    if not tile or tile.terreno != TerrainType.AGUA:
        return False
    groups_on_tile = world.get_groups_on_tile(x, y)
    return len(groups_on_tile) > 0


def _is_city_blocked(world: 'World', x: int, y: int, group: Group) -> Tuple[bool, Optional[str]]:
    tile = world.get_tile(x, y)
    if not tile or not tile.has_settlement:
        return (False, None)
    
    settlement = world.get_settlement(tile.settlement_id)
    if not settlement:
        return (False, None)
    
    if settlement.ruinas:
        return (False, None)
    
    if settlement.dueño_grupo_id == group.id:
        return (False, None)
    
    return (True, "CITY_BLOCKED_MOVE")


def move_group(world: 'World', group: Group, direction: str, 
               rng: random.Random) -> MoveResult:
    """Implementa Regla 5: Moverse. Función PURA."""
    if not group.alive:
        return MoveResult(
            success=False,
            new_x=group.x,
            new_y=group.y,
            event_type="MOVE_FAILED_DEAD",
            details={"reason": "group_is_dead"}
        )
    
    original_x, original_y = group.x, group.y
    new_x, new_y = _get_new_coords(original_x, original_y, direction)
    
    if not world.is_valid_coordinates(new_x, new_y):
        origin_direction = OPPOSITE_DIRECTION[direction]
        valid_dirs = _get_valid_directions(world, original_x, original_y, 
                                           exclude_direction=origin_direction)
        
        if valid_dirs:
            new_direction = rng.choice(valid_dirs)
            final_x, final_y = _get_new_coords(original_x, original_y, new_direction)
            
            return MoveResult(
                success=True,
                new_x=final_x,
                new_y=final_y,
                event_type="MOVE_BOUNCE",
                details={
                    "intent_direction": direction,
                    "bounce_direction": new_direction,
                    "from": (original_x, original_y),
                    "to": (final_x, final_y),
                    "reason": "border_rebound"
                }
            )
        else:
            return MoveResult(
                success=False,
                new_x=original_x,
                new_y=original_y,
                event_type="MOVE_FAILED_NO_VALID_DIR",
                details={
                    "intent_direction": direction,
                    "position": (original_x, original_y),
                    "reason": "no_valid_alternative_direction"
                }
            )
    
    if _is_water_with_group(world, new_x, new_y):
        return MoveResult(
            success=False,
            new_x=original_x,
            new_y=original_y,
            event_type="MOVE_BLOCKED_WATER_GROUP",
            details={
                "intent_direction": direction,
                "target": (new_x, new_y),
                "terrain": "AGUA",
                "reason": "target_tile_has_group_on_water"
            }
        )
    
    blocked, block_reason = _is_city_blocked(world, new_x, new_y, group)
    if blocked:
        return MoveResult(
            success=False,
            new_x=original_x,
            new_y=original_y,
            event_type=block_reason,
            details={
                "intent_direction": direction,
                "target": (new_x, new_y),
                "position": (original_x, original_y)
            }
        )
    
    groups_at_dest = world.get_groups_on_tile(new_x, new_y)
    if groups_at_dest:
        target_tile = world.get_tile(new_x, new_y)
        return MoveResult(
            success=True,
            new_x=new_x,
            new_y=new_y,
            event_type="INTERACTION_PENDING",
            interaction_groups=[g.id for g in groups_at_dest],
            details={
                "from": (original_x, original_y),
                "to": (new_x, new_y),
                "other_groups": [g.id for g in groups_at_dest],
                "terrain": target_tile.terreno.value if target_tile else "UNKNOWN"
            }
        )
    
    target_tile = world.get_tile(new_x, new_y)
    return MoveResult(
        success=True,
        new_x=new_x,
        new_y=new_y,
        event_type="MOVE_SUCCESS",
        details={
            "direction": direction,
            "from": (original_x, original_y),
            "to": (new_x, new_y),
            "terrain": target_tile.terreno.value if target_tile else "UNKNOWN",
            "has_settlement": target_tile.has_settlement if target_tile else False,
            "has_structure": target_tile.has_structure if target_tile else False
        }
    )


# ============================================================================
# Sistema de combate Grupo vs Grupo (Regla 14) - FUNCIONES PURAS
# ============================================================================

@dataclass
class CombatResult:
    """Resultado puro de un combate entre dos grupos."""
    winner_id: int
    loser_id: int
    winner_power: float
    loser_power: float
    loser_participants: int
    losses_absolute: int
    losses_percentage: float
    loser_remaining_population: int
    rebound_distance: int
    rebound_direction: str
    winner_eliminated: bool = False
    loser_eliminated: bool = False


@dataclass
class ReboundStepResult:
    """Resultado puro de un paso de rebote."""
    success: bool
    new_x: int
    new_y: int
    new_direction: str
    edge_bounce: bool
    blocked: bool
    block_reason: Optional[str]


def calculate_participants(population: int, has_vulnerable_or_marching: bool) -> int:
    """Calcula participantes según Regla 14.1."""
    if population <= 0:
        return 0
    
    percentage = 0.05 if has_vulnerable_or_marching else 0.10
    participants = math.ceil(population * percentage)
    return max(1, participants)


def calculate_losses(participants: int, rng: random.Random) -> int:
    """Calcula bajas del perdedor según Regla 14.3."""
    if participants <= 0:
        return 0
    
    percentage = rng.choice([0.10, 0.30, 0.50])
    losses = math.ceil(participants * percentage)
    return max(1, losses)


def calculate_rebound_distance(rng: random.Random) -> int:
    """Calcula distancia de rebote (1-3 casillas) según Regla 14.4."""
    return rng.randint(1, 3)


def determine_winner(power_a: float, power_b: float, 
                     defender_id: int, attacker_id: int) -> Tuple[int, int, float, float]:
    """Determina ganador y perdedor según Regla 14.2."""
    if power_a > power_b:
        return attacker_id, defender_id, power_a, power_b
    elif power_b > power_a:
        return defender_id, attacker_id, power_b, power_a
    else:
        return defender_id, attacker_id, power_b, power_a


def get_opposite_direction(direction: str) -> str:
    """Obtiene la dirección opuesta."""
    opposites = {'N': 'S', 'S': 'N', 'E': 'O', 'O': 'E'}
    return opposites.get(direction, 'N')


def get_valid_directions(x: int, y: int, width: int, height: int) -> List[str]:
    """Obtiene direcciones válidas que no salen del mapa."""
    DIRECTIONS = ['N', 'S', 'E', 'O']
    DIRECTION_VECTORS = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'O': (-1, 0)}
    
    valid = []
    for direction in DIRECTIONS:
        dx, dy = DIRECTION_VECTORS[direction]
        new_x, new_y = x + dx, y + dy
        if 1 <= new_x <= width and 1 <= new_y <= height:
            valid.append(direction)
    return valid


def choose_alternative_direction(original_direction: str, 
                                  x: int, y: int,
                                  width: int, height: int,
                                  rng: random.Random) -> Optional[str]:
    """Regla 1.1: Elegir dirección alternativa válida."""
    valid_directions = get_valid_directions(x, y, width, height)
    alternatives = [d for d in valid_directions if d != original_direction]
    
    if alternatives:
        return rng.choice(alternatives)
    return None


def calculate_rebound_step(current_x: int, current_y: int,
                          current_direction: str,
                          width: int, height: int,
                          rng: random.Random) -> ReboundStepResult:
    """Calcula el resultado de un paso de rebote."""
    DIRECTION_VECTORS = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'O': (-1, 0)}
    
    dx, dy = DIRECTION_VECTORS[current_direction]
    new_x, new_y = current_x + dx, current_y + dy
    
    if not (1 <= new_x <= width and 1 <= new_y <= height):
        alt_direction = choose_alternative_direction(
            current_direction, current_x, current_y, width, height, rng
        )
        
        if alt_direction:
            dx, dy = DIRECTION_VECTORS[alt_direction]
            alt_x, alt_y = current_x + dx, current_y + dy
            return ReboundStepResult(
                success=True,
                new_x=alt_x,
                new_y=alt_y,
                new_direction=alt_direction,
                edge_bounce=True,
                blocked=False,
                block_reason=None
            )
        else:
            return ReboundStepResult(
                success=False,
                new_x=current_x,
                new_y=current_y,
                new_direction=current_direction,
                edge_bounce=False,
                blocked=True,
                block_reason="OUT_OF_BOUNDS_NO_ALTERNATIVE"
            )
    
    return ReboundStepResult(
        success=True,
        new_x=new_x,
        new_y=new_y,
        new_direction=current_direction,
        edge_bounce=False,
        blocked=False,
        block_reason=None
    )


# ============================================================================
# Sistema de combate Grupo vs Ciudad - FUNCIONES PURAS
# ============================================================================

@dataclass
class CityBattleResult:
    """Resultado puro de un combate entre un grupo y una ciudad."""
    attacker_id: int
    settlement_id: int
    attacker_won: bool
    city_destroyed: bool
    attacker_participants: int
    attacker_power: float
    city_defense_power: int
    bonus_percent: int
    attacker_losses: int
    rebound_distance: int
    old_city_level: int
    new_city_level: int
    defender_group_id: Optional[int] = None


def calculate_attacker_participants(population: int, has_siege_trait: bool = False) -> int:
    """Calcula participantes del atacante según R15.4."""
    if population <= 0:
        return 0
    
    percentage = 0.40 if has_siege_trait else 0.30
    participants = math.ceil(population * percentage)
    return max(1, participants)


def calculate_city_defense_points(settlement_points: int, 
                                   defender_power: float = 0.0,
                                   defender_population: int = 0) -> int:
    """Calcula los puntos de defensa de una ciudad según R15.5 y R5.6."""
    city_defense = math.ceil(settlement_points * 0.10)
    
    if defender_population > 0:
        defender_total_power = defender_power * defender_population
        city_defense += defender_total_power
    
    return city_defense


def calculate_attacker_losses(participants: int, rng: random.Random) -> int:
    """Calcula bajas del atacante cuando pierde contra una ciudad."""
    if participants <= 0:
        return 0
    
    percentage = rng.choice([0.10, 0.30, 0.50])
    losses = math.ceil(participants * percentage)
    return max(1, losses)


def calculate_rebound_distance_city(rng: random.Random) -> int:
    """Calcula distancia de rebote para ataque a ciudad (1-3 casillas)."""
    return rng.randint(1, 3)


def calculate_city_battle(
    attacker_population: int,
    attacker_power_avg: float,
    attacker_participants: int,
    bonus_percent: int,
    settlement_points: int,
    settlement_level: int,
    defender_power_avg: float = 0.0,
    defender_population: int = 0,
    attacker_wins_tie: bool = True
) -> CityBattleResult:
    """Calcula el resultado de una batalla entre un grupo y una ciudad."""
    if attacker_population <= 0:
        return CityBattleResult(
            attacker_id=-1, settlement_id=-1, attacker_won=False, city_destroyed=False,
            attacker_participants=0, attacker_power=0.0, city_defense_power=0,
            bonus_percent=0, attacker_losses=0, rebound_distance=0,
            old_city_level=settlement_level, new_city_level=settlement_level,
            defender_group_id=None
        )
    
    attacker_base_power = attacker_power_avg * attacker_participants
    attacker_power = attacker_base_power * (1 + bonus_percent / 100.0)
    
    city_defense_power = calculate_city_defense_points(
        settlement_points, defender_power_avg, defender_population
    )
    
    if attacker_power > city_defense_power:
        attacker_won = True
        attacker_losses = 0
        rebound_distance = 1
    elif attacker_power < city_defense_power:
        attacker_won = False
        attacker_losses = 0
        rebound_distance = 0
    else:
        attacker_won = attacker_wins_tie
        attacker_losses = 0
        rebound_distance = 1 if attacker_won else 0
    
    if attacker_won:
        if settlement_level == 1:
            new_level = 0
            city_destroyed = True
        else:
            new_level = settlement_level - 1
            city_destroyed = False
    else:
        new_level = settlement_level
        city_destroyed = False
    
    return CityBattleResult(
        attacker_id=-1, settlement_id=-1,
        attacker_won=attacker_won, city_destroyed=city_destroyed,
        attacker_participants=attacker_participants, attacker_power=attacker_power,
        city_defense_power=city_defense_power, bonus_percent=bonus_percent,
        attacker_losses=attacker_losses, rebound_distance=rebound_distance,
        old_city_level=settlement_level, new_city_level=new_level,
        defender_group_id=None
    )


def calculate_city_battle_with_losses(
    attacker_population: int,
    attacker_power_avg: float,
    attacker_participants: int,
    bonus_percent: int,
    settlement_points: int,
    settlement_level: int,
    rng: random.Random,
    defender_power_avg: float = 0.0,
    defender_population: int = 0,
    attacker_wins_tie: bool = False
) -> CityBattleResult:
    """
    Wrapper para calculate_city_battle que cumple con la firma esperada.
    NOTA: Las pérdidas se calculan externamente en combat_resolver.py.
    """
    return calculate_city_battle(
        attacker_population=attacker_population,
        attacker_power_avg=attacker_power_avg,
        attacker_participants=attacker_participants,
        bonus_percent=bonus_percent,
        settlement_points=settlement_points,
        settlement_level=settlement_level,
        defender_power_avg=defender_power_avg,
        defender_population=defender_population,
        attacker_wins_tie=attacker_wins_tie
    )


def can_attack_from_position(attacker_x: int, attacker_y: int, 
                              settlement_x: int, settlement_y: int) -> bool:
    """Verifica si el atacante está adyacente a la ciudad (R15.1)."""
    return abs(attacker_x - settlement_x) + abs(attacker_y - settlement_y) == 1


def is_water_tile(terrain_type) -> bool:
    """Verifica si una casilla es AGUA."""
    return terrain_type == TerrainType.AGUA


def calculate_new_city_points_after_degradation(old_points: int, old_level: int, new_level: int) -> int:
    """Calcula los nuevos puntos de ciudad después de degradación."""
    return new_level * 1000


# ============================================================================
# Sistema de Asentamientos (R10, R16, R19) - FUNCIONES PURAS
# ============================================================================

@dataclass
class SettleResult:
    """Resultado puro de una acción de asentarse."""
    success: bool
    event_type: str
    details: Dict[str, Any]
    settlement_id: Optional[int] = None
    new_settlement: Optional['Settlement'] = None
    state_to_apply: Optional['StateType'] = None


def can_settle_action(group: 'Group', world: 'World', settlement: Optional['Settlement'] = None) -> Tuple[bool, str]:
    """Verifica si un grupo puede ejecutar la acción Asentarse según R10 y R16."""
    has_nomad_trait = False  # Placeholder
    
    if StateType.ESTABLECIENDO in group.estados and not has_nomad_trait:
        return False, "already_settling"
    
    blocking_states = [StateType.AGOTADO, StateType.EN_MARCHA, StateType.MAREADO]
    for state in blocking_states:
        if state in group.estados:
            return False, f"blocked_by_{state.value.lower().replace(' ', '_')}"
    
    if not group.alive:
        return False, "group_dead"
    
    if settlement is None or settlement.ruinas:
        return True, "can_found"
    
    if settlement.dueño_grupo_id == group.id:
        return True, "can_upgrade_or_repair"
    
    return False, "settlement_owned_by_other"


def calculate_settlement_upgrade(old_level: int, group_points: int, settlement_points: int) -> Tuple[int, int, bool]:
    """Calcula nuevo nivel y puntos después de mejorar/reparar."""
    new_points = settlement_points + group_points
    max_points_for_level = old_level * 1000
    
    if new_points < max_points_for_level:
        return old_level, new_points, False
    
    next_level = old_level + 1
    max_points_for_next = next_level * 1000
    
    if new_points >= max_points_for_next and old_level < 5:
        return next_level, new_points, False
    elif new_points >= max_points_for_level:
        return old_level, new_points, True
    
    return old_level, new_points, False


def create_settlement(settlement_id: int, group: 'Group', round_number: int, group_points: int) -> 'Settlement':
    """Crea un nuevo asentamiento (R10.2) con radio de influencia."""
    return Settlement(
        id=settlement_id,
        nivel=1,
        x=group.x,
        y=group.y,
        puntos_ciudad=group_points,
        fundado_en_ronda=round_number,
        dueño_grupo_id=group.id,
        ruinas=False,
        raza=group.raza,
        subraza=group.subraza,
        created_round=round_number,
        influence_radius=[]
    )


def on_group_death_settlements(world: 'World', group_id: int, logger: 'Logger', round_number: int) -> List[int]:
    """Maneja asentamientos huérfanos cuando un grupo muere (R23.2-3)."""
    orphaned_settlements = []
    
    for settlement in world.get_all_settlements():
        if settlement.dueño_grupo_id == group_id and not settlement.ruinas:
            orphaned_settlements.append(settlement.id)
    
    return orphaned_settlements


def get_owner_group_for_settlement(world: 'World', settlement: 'Settlement', 
                                    original_groups: Dict[int, List[int]]) -> Optional[int]:
    """Determina el grupo dueño de un asentamiento después de división (R19.4)."""
    if settlement.ruinas:
        return None
    
    if settlement.dueño_grupo_id is None:
        return None
    
    original_owner = settlement.dueño_grupo_id
    
    for origin_id, group_ids in original_groups.items():
        if original_owner in group_ids or origin_id == original_owner:
            if group_ids:
                return min(group_ids)
    
    return original_owner


# ============================================================================
# Sistema de Peligros (Regla 12) - FUNCIONES PURAS
# ============================================================================

@dataclass
class DangerResult:
    """Resultado puro de la evaluación de peligro para un grupo."""
    group_id: int
    triggered: bool
    survived: bool
    population_before: int
    population_after: int
    power_total: float
    global_power_median: float
    ratio: float
    danger_probability: float
    survival_probability: float
    roll_value: float
    loss_percentage: Optional[int] = None
    action_consumed: bool = False


def calculate_global_power_median(groups: List['Group']) -> float:
    """Calcula la mediana del poder_total de todos los grupos vivos."""
    if not groups:
        return 0.0
    
    powers = [g.poder_total for g in groups if g.alive]
    
    if not powers:
        return 0.0
    
    powers.sort()
    n = len(powers)
    
    if n % 2 == 1:
        median = powers[n // 2]
    else:
        median = (powers[n // 2 - 1] + powers[n // 2]) / 2.0
    
    return math.ceil(median)


def get_danger_probability_by_ratio(ratio: float) -> float:
    """Calcula probabilidad de que ocurra peligro según ratio."""
    if ratio >= 1.5:
        return 0.05
    elif ratio >= 1.0:
        return 0.10
    elif ratio >= 0.75:
        return 0.20
    elif ratio >= 0.5:
        return 0.35
    else:
        return 0.50


def calculate_survival_probability(group_power: float, global_power: float) -> float:
    """Calcula probabilidad de superar el peligro."""
    if global_power <= 0:
        return 0.95
    
    raw_prob = (group_power / global_power) * 100.0
    prob_decimal = max(0.05, min(0.95, raw_prob / 100.0))
    return prob_decimal


def calculate_loss_percentage(rng: random.Random) -> int:
    """Calcula porcentaje de pérdida de población."""
    return rng.choice([10, 30, 50])


def calculate_population_loss(population: int, percentage: int) -> int:
    """Calcula pérdida de población con redondeo ceil, mínimo 1."""
    if population <= 0:
        return 0
    
    loss = math.ceil(population * percentage / 100.0)
    return max(1, loss)


def evaluate_danger(group: 'Group', global_power_median: float, rng: random.Random, is_first_round: bool) -> DangerResult:
    """Evalúa peligro para un grupo al inicio de la ronda."""
    population_before = group.poblacion
    
    if is_first_round:
        return DangerResult(
            group_id=group.id, triggered=False, survived=True,
            population_before=population_before, population_after=population_before,
            power_total=group.poder_total, global_power_median=global_power_median,
            ratio=0.0, danger_probability=0.0, survival_probability=1.0,
            roll_value=0.0, action_consumed=False
        )
    
    if global_power_median <= 0:
        ratio = float('inf') if group.poder_total > 0 else 1.0
    else:
        ratio = group.poder_total / global_power_median
    
    danger_prob = get_danger_probability_by_ratio(ratio)
    danger_roll = rng.random()
    triggered = danger_roll < danger_prob
    
    if not triggered:
        return DangerResult(
            group_id=group.id, triggered=False, survived=True,
            population_before=population_before, population_after=population_before,
            power_total=group.poder_total, global_power_median=global_power_median,
            ratio=ratio, danger_probability=danger_prob, survival_probability=1.0,
            roll_value=danger_roll, action_consumed=False
        )
    
    survival_prob = calculate_survival_probability(group.poder_total, global_power_median)
    survival_roll = rng.random()
    survived = survival_roll < survival_prob
    
    if survived:
        return DangerResult(
            group_id=group.id, triggered=True, survived=True,
            population_before=population_before, population_after=population_before,
            power_total=group.poder_total, global_power_median=global_power_median,
            ratio=ratio, danger_probability=danger_prob, survival_probability=survival_prob,
            roll_value=survival_roll, action_consumed=False
        )
    else:
        loss_percentage = calculate_loss_percentage(rng)
        loss_amount = calculate_population_loss(population_before, loss_percentage)
        population_after = max(0, population_before - loss_amount)
        
        return DangerResult(
            group_id=group.id, triggered=True, survived=False,
            population_before=population_before, population_after=population_after,
            power_total=group.poder_total, global_power_median=global_power_median,
            ratio=ratio, danger_probability=danger_prob, survival_probability=survival_prob,
            roll_value=survival_roll, loss_percentage=loss_percentage, action_consumed=True
        )


# ============================================================================
# MÓDULO 11: Acción Crecer (Regla 7) - FUNCIONES PURAS
# ============================================================================

@dataclass
class GrowResult:
    """Resultado de la acción Crecer."""
    success: bool
    event_type: str
    details: Dict[str, Any]
    new_population: int
    new_total_power: float
    growth_factor: float
    overpopulation_triggered: bool = False
    split_triggered: bool = False
    split_groups: Optional[List[Tuple['Group', bool]]] = None


def calculate_growth_factor(rng: random.Random) -> float:
    """Calcula factor de crecimiento: 1.5 o 2.0 (R7.1)."""
    return 1.5 if rng.random() < 0.5 else 2.0


def calculate_grow_population(population: int, factor: float) -> int:
    """Calcula nueva población después de Crecer con redondeo ceil universal."""
    return math.ceil(population * factor)


def action_grow(group: 'Group', rng: random.Random) -> GrowResult:
    """Ejecuta la acción Crecer (R7)."""
    old_population = group.poblacion
    factor = calculate_growth_factor(rng)
    new_population = calculate_grow_population(old_population, factor)
    new_total_power = new_population * group.poder_promedio
    
    return GrowResult(
        success=True,
        event_type="GROW_SUCCESS",
        details={
            "old_population": old_population,
            "new_population": new_population,
            "growth_factor": factor,
            "old_total_power": group.poder_total,
            "new_total_power": new_total_power,
            "power_avg": group.poder_promedio
        },
        new_population=new_population,
        new_total_power=new_total_power,
        growth_factor=factor
    )


def has_grow_consecutive(group: 'Group') -> bool:
    """Verifica si el grupo usó Crecer dos veces seguidas (R25 Sobrepoblación)."""
    return group.last_action_was_grow is True


# ============================================================================
# MÓDULO 11: Acción Entrenar (Regla 8) - FUNCIONES PURAS
# ============================================================================

@dataclass
class TrainResult:
    """Resultado de la acción Entrenar."""
    success: bool
    event_type: str
    details: Dict[str, Any]
    new_power_avg: float
    new_total_power: float
    exhausted_state_applied: bool


def action_train(group: 'Group') -> TrainResult:
    """Ejecuta la acción Entrenar (R8)."""
    old_power_avg = group.poder_promedio
    new_power_avg = old_power_avg + 3
    new_total_power = group.poblacion * new_power_avg
    
    return TrainResult(
        success=True,
        event_type="TRAIN_SUCCESS",
        details={
            "old_power_avg": old_power_avg,
            "new_power_avg": new_power_avg,
            "old_total_power": group.poder_total,
            "new_total_power": new_total_power,
            "population": group.poblacion
        },
        new_power_avg=new_power_avg,
        new_total_power=new_total_power,
        exhausted_state_applied=True
    )


# ============================================================================
# MÓDULO 11: Estado Sobrepoblación y División Involuntaria (R25)
# ============================================================================

@dataclass
class ForcedSplitResult:
    """Resultado de una división involuntaria por Sobrepoblación."""
    triggered: bool
    split_groups: List[Tuple['Group', bool]]
    details: Dict[str, Any]


def calculate_forced_split(group: 'Group', rng: random.Random, 
                           next_group_id: int, current_round: int,
                           split_probability: float = 0.25) -> ForcedSplitResult:
    """Calcula división involuntaria por Sobrepoblación (R25.5)."""
    split_roll = rng.random()
    triggered = split_roll < split_probability
    
    if not triggered:
        return ForcedSplitResult(
            triggered=False,
            split_groups=[],
            details={
                "roll": split_roll,
                "probability": split_probability,
                "split_occurred": False
            }
        )
    
    old_population = group.poblacion
    original_population = math.ceil(old_population / 2)
    new_population = old_population - original_population
    power_avg = group.poder_promedio
    
    original_group = Group(
        id=group.id,
        raza=group.raza,
        subraza=group.subraza,
        x=group.x,
        y=group.y,
        poblacion=original_population,
        poder_promedio=power_avg,
        estados=deepcopy(group.estados),
        asentamiento_id=group.asentamiento_id,
        grupo_original_id=group.grupo_original_id,
        reputacion=deepcopy(group.reputacion),
        acted_this_round=group.acted_this_round,
        created_in_round=group.created_in_round,
        last_action_was_grow=group.last_action_was_grow
    )
    
    new_group = Group(
        id=next_group_id,
        raza=group.raza,
        subraza=group.subraza,
        x=group.x,
        y=group.y,
        poblacion=new_population,
        poder_promedio=power_avg,
        estados=deepcopy(group.estados),
        asentamiento_id=None,
        grupo_original_id=group.grupo_original_id or group.id,
        reputacion=deepcopy(group.reputacion),
        acted_this_round=group.acted_this_round,
        created_in_round=current_round,
        last_action_was_grow=False
    )
    
    return ForcedSplitResult(
        triggered=True,
        split_groups=[(original_group, True), (new_group, False)],
        details={
            "roll": split_roll,
            "probability": split_probability,
            "split_occurred": True,
            "original_population": original_population,
            "new_population": new_population,
            "new_group_id": next_group_id,
            "original_group_id": group.id,
            "inherited_states": [s.value for s in group.estados.keys()]
        }
    )


# ============================================================================
# Módulo 10: Nacimientos (Regla 24) - FUNCIONES PURAS
# ============================================================================

@dataclass
class BirthAllocation:
    """Asignación de nacimientos a una entidad."""
    entity_id: int
    entity_type: str
    base_amount: int
    bonus_amount: int
    total_amount: int
    race: str
    subrace: Optional[str] = None
    settlement_id: Optional[int] = None


@dataclass
class BirthResult:
    """Resultado de la distribución de nacimientos por raza."""
    race: str
    total_births: int
    allocations: List[BirthAllocation]
    lost_births: int


def calculate_birth_distribution(num_entities: int, total_births: int = 1000) -> Tuple[List[int], int]:
    """Calcula distribución equitativa de nacimientos."""
    if num_entities <= 0:
        return [], total_births
    
    base = total_births // num_entities
    remainder = total_births % num_entities
    
    allocations = []
    for i in range(num_entities):
        amount = base + (1 if i < remainder else 0)
        allocations.append(amount)
    
    return allocations, 0


def calculate_housing_bonus(amount: int, has_housing_upgrade: bool) -> int:
    """Calcula bonus por Viviendas Mejores (+25%, redondeo ceil)."""
    if not has_housing_upgrade:
        return 0
    
    bonus = math.ceil(amount * 0.25)
    return bonus


def has_housing_upgrade_for_group(group: 'Group', world: 'World') -> bool:
    """Verifica si un grupo tiene al menos una ciudad con mejora 'Viviendas mejores'."""
    for settlement in world.get_all_settlements():
        if settlement.dueño_grupo_id == group.id and not settlement.ruinas:
            if hasattr(settlement, 'mejoras') and CityUpgrade.VIVIENDAS_MEJORES in settlement.mejoras:
                return True
    return False


def create_group_from_settlement_data(
    settlement_id: int,
    settlement_race: str,
    settlement_subrace: str,
    settlement_x: int,
    settlement_y: int,
    population: int,
    next_group_id: int,
    current_round: int
) -> 'Group':
    """Crea un nuevo grupo desde un asentamiento huérfano."""
    return Group(
        id=next_group_id,
        raza=settlement_race,
        subraza=settlement_subrace,
        x=settlement_x,
        y=settlement_y,
        poblacion=population,
        poder_promedio=350.0,
        created_in_round=current_round,
        acted_this_round=True
    )


# ============================================================================
# STUBS/FUNCIONES FALTANTES PARA COMPATIBILIDAD CON engine.py
# ============================================================================

def create_group_from_settlement(settlement: 'Settlement', population: int,
                                  next_group_id: int, current_round: int) -> 'Group':
    """Wrapper para create_group_from_settlement_data."""
    return create_group_from_settlement_data(
        settlement_id=settlement.id,
        settlement_race=settlement.raza,
        settlement_subrace=settlement.subraza,
        settlement_x=settlement.x,
        settlement_y=settlement.y,
        population=population,
        next_group_id=next_group_id,
        current_round=current_round
    )


def action_settle(world: 'World', group_id: int, rng: random.Random,
                  logger: 'Logger', context: Dict[str, Any]) -> 'SettleResult':
    """Wrapper para la función de asentarse."""
    group = world.get_group(group_id)
    if not group or not group.alive:
        return SettleResult(
            success=False,
            event_type="SETTLE_FAILED",
            details={"group_id": group_id, "reason": "group_not_found_or_dead"},
            state_to_apply=StateType.ESTABLECIENDO
        )
    
    # OBTENER ASENTAMIENTO EXISTENTE EN LA CASILLA
    tile = world.get_tile(group.x, group.y)
    existing_settlement = None
    if tile and tile.settlement_id:
        existing_settlement = world.get_settlement(tile.settlement_id)
    
    # Verificar si se puede asentar
    can_settle, reason = can_settle_action(group, world, existing_settlement)
    
    if not can_settle:
        return SettleResult(
            success=False,
            event_type="SETTLE_FAILED",
            details={"group_id": group_id, "reason": reason},
            state_to_apply=StateType.ESTABLECIENDO
        )
    
    group_points = math.ceil(group.poblacion * group.poder_promedio)
    
    # ====================================================================
    # CASO 1: No hay asentamiento o está en ruinas → FUNDAR
    # ====================================================================
    if existing_settlement is None or existing_settlement.ruinas:
        if has_trait_by_race(group.raza, group.subraza, "Metrópolis"):
            # Fundar nivel 3 (Villa)
            new_settlement = Settlement(
                id=context["next_settlement_id"],
                nivel=3,
                x=group.x,
                y=group.y,
                puntos_ciudad=3000,
                fundado_en_ronda=context["round_number"],
                dueño_grupo_id=group.id,
                ruinas=False,
                raza=group.raza,
                subraza=group.subraza,
                created_round=context["round_number"],
                influence_radius=[]
            )
            
            if logger:
                logger.log_event(
                    round_num=context["round_number"],
                    turn_index=context["turn_index"],
                    group_id=group.id,
                    event_type="SETTLEMENT_FOUNDED_AS_VILLA",
                    details={
                        "settlement_id": new_settlement.id,
                        "level": 3,
                        "trait": "Metrópolis"
                    }
                )
        else:
            # Fundar nivel 1 normal
            new_settlement = create_settlement(
                settlement_id=context["next_settlement_id"],
                group=group,
                round_number=context["round_number"],
                group_points=group_points
            )
        
        return SettleResult(
            success=True,
            event_type="SETTLEMENT_FOUNDED",
            details={"settlement_id": new_settlement.id},
            settlement_id=new_settlement.id,
            new_settlement=new_settlement,
            state_to_apply=StateType.ESTABLECIENDO
        )
    
    # ====================================================================
    # CASO 2: Hay asentamiento y el grupo es dueño → MEJORAR
    # ====================================================================
    if existing_settlement.dueño_grupo_id == group.id:
        old_level = existing_settlement.nivel
        old_points = existing_settlement.puntos_ciudad
        max_level = get_settlement_max_level(existing_settlement)
        
        # Calcular nuevo nivel y puntos
        new_points = existing_settlement.puntos_ciudad + group_points
        points_for_next_level = (old_level + 1) * 1000
        
        new_level = old_level
        if new_points >= points_for_next_level and old_level < max_level:
            new_level = old_level + 1
        
        # Determinar tipo de evento
        if new_level > old_level:
            event_type = "SETTLEMENT_UPGRADED"
        elif new_points > old_points:
            event_type = "SETTLEMENT_REPAIRED"
        else:
            event_type = "SETTLEMENT_IMPROVED"
        
        # Actualizar asentamiento existente
        existing_settlement.puntos_ciudad = new_points
        existing_settlement.nivel = new_level
        existing_settlement.ruinas = False
        
        # Actualizar radio de influencia si el nivel subió
        if new_level > old_level:
            update_settlement_influence(
                existing_settlement, 
                world.get_all_settlements(), 
                logger, 
                context["round_number"]
            )
        
        if logger:
            logger.log_event(
                round_num=context["round_number"],
                turn_index=context["turn_index"],
                group_id=group.id,
                event_type=event_type,
                details={
                    "settlement_id": existing_settlement.id,
                    "old_level": old_level,
                    "new_level": new_level,
                    "old_points": old_points,
                    "new_points": new_points,
                    "points_added": group_points
                }
            )
        
        return SettleResult(
            success=True,
            event_type=event_type,
            details={
                "settlement_id": existing_settlement.id,
                "old_level": old_level,
                "new_level": new_level,
                "points_added": group_points,
                "total_points": new_points
            },
            settlement_id=existing_settlement.id,
            new_settlement=existing_settlement,
            state_to_apply=StateType.ESTABLECIENDO
        )
    
    # ====================================================================
    # CASO 3: Asentamiento de otro grupo → NO SE PUEDE
    # ====================================================================
    return SettleResult(
        success=False,
        event_type="SETTLE_FAILED",
        details={"group_id": group_id, "reason": "settlement_owned_by_other"},
        state_to_apply=StateType.ESTABLECIENDO
    )

def apply_entorpecido_when_attacked(attacker: 'Group', defender: 'Group', world: 'World',
                                     logger: Optional['Logger'] = None,
                                     round_number: int = 0, turn_index: int = -1) -> None:
    """Metrópolis: Al ser atacado, el atacante entra en Entorpecido."""
    if not is_metropolis_settlement_owner(defender, world):
        return
    
    if StateType.ENTORPECIDO not in attacker.estados:
        attacker.estados[StateType.ENTORPECIDO] = 1
        if logger:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=attacker.id,
                event_type="TRAIT_EFFECT_APPLIED",
                details={
                    "trait": "Metrópolis",
                    "effect": "Entorpecido_al_atacar",
                    "defender_id": defender.id,
                    "state": "Entorpecido",
                    "duration": 1
                }
            )

def calculate_migrate_distance(rng: random.Random) -> int:
    """Calcula distancia de migración: 2-4 casillas (R9.1)."""
    return rng.randint(2, 4)


def can_start_migration(group: 'Group', world: 'World') -> Tuple[bool, str]:
    """Verifica si un grupo puede iniciar migración (R9.3)."""
    if not group.alive:
        return False, "group_dead"
    
    tile = world.get_tile(group.x, group.y)
    if not tile:
        return False, "invalid_tile"

    # Anfibio puede empezar migración desde agua
    if tile.terreno == TerrainType.AGUA and not has_trait(group, "Anfibio"):
        return False, "cannot_start_on_water"
    
    blocking_states = [StateType.AGOTADO, StateType.ESTABLECIENDO]
    for state in blocking_states:
        if state in group.estados:
            return False, f"blocked_by_{state.value.lower().replace(' ', '_')}"
    
    return True, ""


def get_coords_in_direction(x: int, y: int, direction: str) -> Tuple[int, int]:
    """Obtiene coordenadas después de mover 1 casilla en dirección."""
    DIR_VECTORS = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'O': (-1, 0)}
    dx, dy = DIR_VECTORS.get(direction, (0, 0))
    return (x + dx, y + dy)


def can_enter_tile_during_migration(x: int, y: int, group: 'Group',
                                    world: 'World') -> Tuple[bool, Optional[str]]:
    """Verifica si se puede entrar a una casilla durante migración."""
    if not world.is_valid_coordinates(x, y):
        return False, "OUT_OF_BOUNDS"
    
    tile = world.get_tile(x, y)
    if not tile:
        return False, "INVALID_TILE"
    
    if tile.terreno == TerrainType.AGUA:
        return False, "WATER"
    
    if tile.has_settlement:
        settlement = world.get_settlement(tile.settlement_id)
        if settlement and not settlement.ruinas:
            if settlement.dueño_grupo_id != group.id:
                return False, "CITY_BLOCKED"
    
    return True, None


# ============================================================================
# MÓDULO 13: Radio de influencia (Regla 21) - FUNCIONES PURAS
# ============================================================================

@dataclass
class InfluenceMaskResult:
    """Resultado del cálculo de máscara de influencia."""
    settlement_id: int
    level: int
    created_round: int
    full_mask: List[Tuple[int, int]]
    final_mask: List[Tuple[int, int]]
    blocked_tiles: List[Tuple[Tuple[int, int], int]]
    success: bool


def get_cross_mask(x: int, y: int, distance: int) -> List[Tuple[int, int]]:
    """Genera máscara en cruz (N,S,E,O) a distancia especificada."""
    mask = []
    if distance >= 1:
        mask.extend([(x, y-1), (x, y+1), (x-1, y), (x+1, y)])
    if distance >= 2:
        mask.extend([(x, y-2), (x, y+2), (x-2, y), (x+2, y)])
    return mask


def get_ring_mask(x: int, y: int, ring: int) -> List[Tuple[int, int]]:
    """Genera máscara de anillo/rodeo alrededor de una casilla."""
    mask = []
    if ring == 1:
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                if 1 <= x + dx <= 40 and 1 <= y + dy <= 30:
                    mask.append((x + dx, y + dy))
    return mask


def get_full_influence_mask(settlement: 'Settlement') -> List[Tuple[int, int]]:
    """Genera la máscara completa de influencia según nivel (R21.8)."""
    x, y = settlement.x, settlement.y
    mask = []
    
    if settlement.nivel == 1:
        pass
    elif settlement.nivel == 2:
        mask = get_cross_mask(x, y, distance=1)
    elif settlement.nivel == 3 or settlement.nivel == 4:
        mask = get_ring_mask(x, y, ring=1)
    elif settlement.nivel == 5:
        mask = get_cross_mask(x, y, distance=2) + get_ring_mask(x, y, ring=1)
    
    return mask


def apply_older_settlement_priority(
    settlements: List['Settlement'],
    logger: Optional['Logger'] = None,
    round_number: int = 0
) -> Dict[int, List[Tuple[int, int]]]:
    """Aplica la prioridad por antigüedad (R21.3) para resolver conflictos."""
    active_settlements = [s for s in settlements if not s.ruinas]
    sorted_settlements = sorted(active_settlements, key=lambda s: s.created_round)
    
    final_masks: Dict[int, List[Tuple[int, int]]] = {}
    occupied_tiles: Set[Tuple[int, int]] = set()
    
    for settlement in sorted_settlements:
        full_mask = get_full_influence_mask(settlement)
        final_mask = []
        
        for tile in full_mask:
            if tile not in occupied_tiles:
                final_mask.append(tile)
                occupied_tiles.add(tile)
        
        final_masks[settlement.id] = final_mask
        
        if logger:
            logger.log_event(
                round_num=round_number,
                turn_index=-1,
                group_id=-1,
                event_type="INFLUENCE_CALCULATED",
                details={
                    "settlement_id": settlement.id,
                    "level": settlement.nivel,
                    "created_round": settlement.created_round,
                    "final_mask_size": len(final_mask)
                }
            )
    
    return final_masks


def is_within_any_influence(x: int, y: int, settlements: List['Settlement']) -> Tuple[bool, Optional[int]]:
    """Verifica si una casilla está dentro del radio de algún asentamiento activo."""
    for settlement in settlements:
        if settlement.ruinas:
            continue
        if hasattr(settlement, 'influence_radius') and (x, y) in settlement.influence_radius:
            return True, settlement.id
    return False, None


def can_found_settlement_at(x: int, y: int, settlements: List['Settlement']) -> Tuple[bool, Optional[int]]:
    """Verifica si se puede fundar un asentamiento en las coordenadas dadas."""
    return is_within_any_influence(x, y, settlements)


def update_settlement_influence(
    settlement: 'Settlement',
    all_settlements: List['Settlement'],
    logger: Optional['Logger'] = None,
    round_number: int = 0
) -> List[Tuple[int, int]]:
    """Actualiza la máscara de influencia de un asentamiento después de subir de nivel."""
    if settlement.ruinas:
        settlement.influence_radius = []
        return []
    
    final_masks = apply_older_settlement_priority(all_settlements, logger, round_number)
    new_mask = final_masks.get(settlement.id, [])
    settlement.influence_radius = new_mask
    
    if logger:
        logger.log_event(
            round_num=round_number,
            turn_index=-1,
            group_id=-1,
            event_type="SETTLEMENT_LEVEL_UP_INFLUENCE_UPDATED",
            details={
                "settlement_id": settlement.id,
                "new_level": settlement.nivel,
                "new_mask_size": len(new_mask),
                "created_round": settlement.created_round
            }
        )
    
    return new_mask


def get_influence_radius_by_level(level: int) -> str:
    """Helper para debugging: devuelve nombre del radio por nivel."""
    if level == 1:
        return "none"
    elif level == 2:
        return "cross_1"
    elif level == 3 or level == 4:
        return "ring_1"
    elif level == 5:
        return "cross_2_and_ring_1"
    return "unknown"


# ============================================================================
# MÓDULO 14: Sistema de Rasgos - Helpers
# ============================================================================

def has_trait(group: 'Group', trait_name: str) -> bool:
    """Verifica si un grupo tiene un rasgo específico."""
    return trait_name in group.traits


# ============================================================================
# MÓDULO 14: Rasgos de movimiento - Navegante
# ============================================================================

@dataclass
class NavigatorMoveResult:
    """Resultado de movimiento con Navegante (2 casillas)."""
    success: bool
    steps: List[Tuple[int, int, str]]
    final_x: int
    final_y: int
    event_type: str
    details: Dict[str, Any]
    interaction_groups: Optional[List[int]] = None


def move_navigator_on_water(world: 'World', group: 'Group', direction: str,
                            rng: random.Random) -> NavigatorMoveResult:
    """Movimiento especial para Navegante en agua: 2 casillas."""
    original_x, original_y = group.x, group.y
    current_x, current_y = original_x, original_y
    steps_made = []
    
    for step in range(1, 3):
        new_x, new_y = _get_new_coords(current_x, current_y, direction)
        
        if not world.is_valid_coordinates(new_x, new_y):
            valid_dirs = _get_valid_directions(world, current_x, current_y,
                                               exclude_direction=OPPOSITE_DIRECTION[direction])
            if valid_dirs:
                new_direction = rng.choice(valid_dirs)
                new_x, new_y = _get_new_coords(current_x, current_y, new_direction)
                direction = new_direction
            else:
                return NavigatorMoveResult(
                    success=False,
                    steps=steps_made,
                    final_x=current_x,
                    final_y=current_y,
                    event_type="NAVIGATOR_MOVE_BLOCKED",
                    details={"direction": direction, "step": step, "reason": "out_of_bounds_no_alternative"}
                )
        
        blocked, block_reason = _is_city_blocked(world, new_x, new_y, group)
        if blocked:
            return NavigatorMoveResult(
                success=False,
                steps=steps_made,
                final_x=current_x,
                final_y=current_y,
                event_type="NAVIGATOR_MOVE_BLOCKED_BY_CITY",
                details={"direction": direction, "step": step, "target": (new_x, new_y), "reason": block_reason}
            )
        
        groups_at_dest = world.get_groups_on_tile(new_x, new_y)
        if groups_at_dest:
            return NavigatorMoveResult(
                success=True,
                steps=steps_made + [(new_x, new_y, "INTERACTION")],
                final_x=new_x,
                final_y=new_y,
                event_type="NAVIGATOR_MOVE_INTERACTION_PENDING",
                details={"from": (current_x, current_y), "to": (new_x, new_y), "step": step},
                interaction_groups=[g.id for g in groups_at_dest]
            )
        
        current_x, current_y = new_x, new_y
        steps_made.append((current_x, current_y, "SUCCESS"))
    
    target_tile = world.get_tile(current_x, current_y)
    return NavigatorMoveResult(
        success=True,
        steps=steps_made,
        final_x=current_x,
        final_y=current_y,
        event_type="NAVIGATOR_MOVE_SUCCESS",
        details={
            "direction": direction,
            "from": (original_x, original_y),
            "to": (current_x, current_y),
            "steps": 2,
            "terrain": target_tile.terreno.value if target_tile else "UNKNOWN"
        }
    )


# ============================================================================
# MÓDULO 14: Rasgos de asentamiento - Expansionista y Nómada
# ============================================================================

def can_settle_during_establishing(group: 'Group', target_settlement: Optional['Settlement'] = None) -> Tuple[bool, str]:
    """R10.5 + Expansionista: Permite asentarse durante Estableciendo si ciudad resultante ≤ nivel 2."""
    if StateType.ESTABLECIENDO not in group.estados:
        return True, "not_establishing"
    
    if has_trait(group, "Nómada") and not has_trait(group, "Expansionista"):
        return False, "nomad_cannot_settle_during_establishing"
    
    if has_trait(group, "Expansionista"):
        if target_settlement is None:
            return True, "expansionista_settle_during_establishing_new"
        elif not target_settlement.ruinas and target_settlement.nivel <= 2:
            return True, "expansionista_settle_during_establishing_upgrade"
        else:
            return False, f"expansionista_cannot_upgrade_city_level_{target_settlement.nivel}_needs_<=2"
    
    return False, "establishing_blocks_settle"


def can_move_during_establishing(group: 'Group') -> bool:
    """R10.5 + Nómada: Verifica si puede moverse durante Estableciendo."""
    if StateType.ESTABLECIENDO not in group.estados:
        return True
    return has_trait(group, "Nómada")


def can_migrate_during_establishing(group: 'Group') -> bool:
    """R9 + Nómada: Verifica si puede migrar durante Estableciendo."""
    if StateType.ESTABLECIENDO not in group.estados:
        return True
    return has_trait(group, "Nómada")


# ============================================================================
# MÓDULO 14: Rasgo Crecimiento Exponencial
# ============================================================================

def calculate_growth_factor_exponential() -> float:
    """Crecimiento Exponencial: siempre ×2."""
    return 2.0


def should_apply_exhausted_from_overpopulation(group: 'Group') -> bool:
    """Sobrepoblación con Crecimiento Exponencial: NO aplica Agotado."""
    if has_trait(group, "Crecimiento Exponencial"):
        return False
    return True


# ============================================================================
# MÓDULO 14: Rasgo Asediadores - Overrides combate ciudad
# ============================================================================

def calculate_siege_participants(population: int, group: 'Group') -> int:
    """R15.4 override: Asediadores participan 40% en lugar de 30%."""
    if population <= 0:
        return 0
    
    percentage = 0.40 if has_trait(group, "Asediadores") else 0.30
    participants = math.ceil(population * percentage)
    return max(1, participants)


def calculate_siege_losses_when_losing(participants: int, group: 'Group', rng: random.Random) -> int:
    """R15.7 override: Asediadores siempre pierden 10% (no variable 10/30/50%)."""
    if participants <= 0:
        return 0
    
    if has_trait(group, "Asediadores"):
        percentage = 0.10
    else:
        percentage = rng.choice([0.10, 0.30, 0.50])
    
    losses = math.ceil(participants * percentage)
    return max(1, losses)


# ============================================================================
# MÓDULO 14: Rasgos de combate - Duros y Precisos
# ============================================================================

def calculate_combat_losses(loser_participants: int, winner: 'Group', loser: 'Group',
                            rng: random.Random, is_winner: bool = False) -> int:
    """Calcula bajas en combate con overrides."""
    if loser_participants <= 0:
        return 0
    
    if has_trait(loser, "Duros"):
        percentage = 0.10
    elif is_winner and has_trait(winner, "Precisos"):
        percentage = 0.50
    else:
        percentage = rng.choice([0.10, 0.30, 0.50])
    
    losses = math.ceil(loser_participants * percentage)
    return max(1, losses)


def get_combat_participation_percentage(group: 'Group', has_vulnerable: bool) -> float:
    """R14.1 con posibilidad de override por rasgos."""
    if has_vulnerable:
        return 0.05
    return 0.10


# ============================================================================
# MÓDULO 14: Rasgo De Piedra - Inmunidad a estados de combate
# ============================================================================

def is_immune_to_combat_state(group: 'Group', state_name: str) -> bool:
    """Verifica si un grupo es inmune a un estado de combate."""
    if has_trait(group, "De piedra"):
        return state_name in COMBAT_STATES
    return False


def apply_combat_state_safe(group: 'Group', state: 'StateType', duration: int,
                            logger: Optional['Logger'] = None,
                            round_number: int = 0, turn_index: int = -1) -> bool:
    """Aplica un estado de combate respetando inmunidades."""
    if is_immune_to_combat_state(group, state.value):
        if logger:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="TRAIT_IMMUNITY_APPLIED",
                details={"trait": "De piedra", "state": state.value}
            )
        return False
    
    group.estados[state] = duration
    return True


# ============================================================================
# MÓDULO 14: Rasgo Anfibio - Migración en agua y Sorpresa
# ============================================================================

def can_migrate_on_water(group: 'Group') -> bool:
    """R9.2 override: Anfibio puede migrar en agua."""
    return has_trait(group, "Anfibio")


def get_surprise_state_duration() -> int:
    """Sorpresa dura 1 turno."""
    return 1


def apply_surprise_on_exit_water(group: 'Group', logger: Optional['Logger'] = None,
                                 round_number: int = 0, turn_index: int = -1) -> None:
    """Anfibio: Al salir del agua aplica Sorpresa."""
    if StateType.SORPRESA not in group.estados:
        group.estados[StateType.SORPRESA] = 1
        if logger:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="TRAIT_OVERRIDE_APPLIED",
                details={"trait": "Anfibio", "effect": "aplica_Sorpresa", "state": "Sorpresa", "duration": 1}
            )


# ============================================================================
# MÓDULO 15A: Rasgos complejos (Parte 3) – Combate/Estados
# ============================================================================

def was_attacked_last_turn(group: 'Group') -> bool:
    """Verifica si el grupo fue atacado en el turno anterior."""
    return getattr(group, '_was_attacked_last_turn', False)


def set_attacked_flag(group: 'Group', value: bool) -> None:
    """Establece flag de ataque para tracking de Reflejos Felinos."""
    group._was_attacked_last_turn = value


def calculate_pack_bonus(group: 'Group', world: 'World') -> int:
    """Calcula bonus de poder para Hombre Bestia Tribu Perruna (Manada)."""
    if not has_trait(group, "Manada"):
        return 0
    
    allies_count = 0
    for other in world.get_all_groups():
        if other.id == group.id or not other.alive:
            continue
        if other.subraza != group.subraza:
            continue
        
        distance = abs(other.x - group.x) + abs(other.y - group.y)
        if distance <= 2:
            allies_count += 1
    
    bonus = min(allies_count, 5) * 5
    return bonus


def apply_war_rune_debuff(winner: 'Group', loser: 'Group', 
                          logger: Optional['Logger'] = None,
                          round_number: int = 0, turn_index: int = -1) -> None:
    """Runa de guerra: Si Enano Oscuro pierde, el enemigo sufre -10% poder 2 turnos."""
    if not has_trait(loser, "Runa de guerra"):
        return
    
    if StateType.DEBUFF_PODER not in winner.estados:
        winner.estados[StateType.DEBUFF_PODER] = 2
        winner._power_multiplier = 0.9
    
    if logger:
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=winner.id,
            event_type="TRAIT_STATE_APPLIED",
            details={"trait": "Runa de guerra", "loser_id": loser.id, "effect": "-10% poder", "duration": 2}
        )


def get_power_multiplier(group: 'Group') -> float:
    """Obtiene multiplicador de poder por debuffs/buffs."""
    multiplier = 1.0
    if StateType.DEBUFF_PODER in group.estados:
        multiplier *= getattr(group, '_power_multiplier', 0.9)
    return multiplier


def apply_fear_on_victory(winner: 'Group', loser: 'Group',
                          logger: Optional['Logger'] = None,
                          round_number: int = 0, turn_index: int = -1) -> None:
    """Como las leyendas (Gigante Montaña): Al vencer combate, oponente entra en Miedo 3 turnos."""
    if not has_trait(winner, "Como las leyendas"):
        return
    
    if StateType.MIEDO not in loser.estados:
        loser.estados[StateType.MIEDO] = 3
        if logger:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=loser.id,
                event_type="TRAIT_STATE_APPLIED",
                details={"trait": "Como las leyendas", "winner_id": winner.id, "state": "Miedo", "duration": 3}
            )


def apply_fear_during_combat(attacker: 'Group', defender: 'Group',
                             logger: Optional['Logger'] = None,
                             round_number: int = 0, turn_index: int = -1) -> None:
    """El miedo no está en el músculo (Alto Orco): Aplica Miedo durante combate."""
    if has_trait(attacker, "El miedo no está en el músculo"):
        if StateType.MIEDO not in defender.estados:
            defender.estados[StateType.MIEDO] = 1
            if logger:
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=defender.id,
                    event_type="TRAIT_STATE_APPLIED",
                    details={"trait": "El miedo no está en el músculo", "attacker_id": attacker.id, "state": "Miedo"}
                )
    
    if has_trait(defender, "El miedo no está en el músculo"):
        if StateType.MIEDO not in attacker.estados:
            attacker.estados[StateType.MIEDO] = 1
            if logger:
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=attacker.id,
                    event_type="TRAIT_STATE_APPLIED",
                    details={"trait": "El miedo no está en el músculo", "defender_id": defender.id, "state": "Miedo"}
                )


def apply_surprise_on_migration(group: 'Group',
                                logger: Optional['Logger'] = None,
                                round_number: int = 0, turn_index: int = -1) -> None:
    """Como una sombra (Elfo Oscuro): Al migrar, aplica Sorpresa."""
    if not has_trait(group, "Como una sombra"):
        return
    
    if StateType.SORPRESA not in group.estados:
        group.estados[StateType.SORPRESA] = 1
        if logger:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="TRAIT_STATE_APPLIED",
                details={"trait": "Como una sombra", "effect": "aplica_Sorpresa", "state": "Sorpresa"}
            )


def apply_surprise_when_attacked_during_marching(group: 'Group', attacker: 'Group',
                                                  logger: Optional['Logger'] = None,
                                                  round_number: int = 0, turn_index: int = -1) -> None:
    """Como una sombra (Elfo Oscuro): Si es atacado durante En Marcha, aplica Sorpresa."""
    if not has_trait(group, "Como una sombra"):
        return
    
    if StateType.SORPRESA not in group.estados:
        group.estados[StateType.SORPRESA] = 1
        if logger:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="TRAIT_STATE_APPLIED",
                details={"trait": "Como una sombra", "attacker_id": attacker.id, "state": "Sorpresa"}
            )


def apply_cat_reflexes_surprise(group: 'Group',
                                logger: Optional['Logger'] = None,
                                round_number: int = 0, turn_index: int = -1) -> None:
    """Reflejos Felinos: Sorpresa si no fue atacado el turno anterior. Inmune a Sorpresa."""
    if not has_trait(group, "Reflejos Felinos"):
        return
    
    if StateType.SORPRESA in group.estados:
        if logger:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="TRAIT_IMMUNITY_TRIGGERED",
                details={"trait": "Reflejos Felinos", "immune_to": "Sorpresa"}
            )
        del group.estados[StateType.SORPRESA]
    
    if not was_attacked_last_turn(group):
        if StateType.SORPRESA not in group.estados:
            group.estados[StateType.SORPRESA] = 1
            if logger:
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="TRAIT_STATE_APPLIED",
                    details={"trait": "Reflejos Felinos", "state": "Sorpresa"}
                )


def is_immune_to_state(group: 'Group', state_name: str) -> bool:
    """Verifica inmunidades por rasgos."""
    if has_trait(group, "Guardián de la Naturaleza"):
        immune_states = {"Miedo", "Entorpecido", "Vulnerable"}
        if state_name in immune_states:
            return True
    
    if has_trait(group, "Reflejos Felinos") and state_name == "Sorpresa":
        return True
    
    if is_immune_to_combat_state(group, state_name):
        return True
    
    return False


def can_goblin_train(group: 'Group') -> bool:
    """Goblin: No puede entrenar."""
    if has_trait(group, "El más débil"):
        return False
    return True


def is_grow_free_for_goblin(group: 'Group') -> bool:
    """Goblin: Crecer es gratuito (no consume acción ni estados)."""
    return has_trait(group, "El más débil")


def calculate_goblin_losses(participants: int) -> int:
    """Goblin: Si hay bajas propias, siempre son 50%."""
    if participants <= 0:
        return 0
    return math.ceil(participants * 0.50)


def calculate_goblin_power_comparison(group: 'Group', global_power_median: float,
                                       logger: Optional['Logger'] = None,
                                       round_number: int = 0, turn_index: int = -1) -> None:
    """Goblin: Si poder_total < poder_global_mediana → aplica Vulnerable. Si ≥ mediana → aplica Sorpresa."""
    if not has_trait(group, "El más débil"):
        return
    
    if group.poder_total < global_power_median:
        if StateType.VULNERABLE not in group.estados:
            group.estados[StateType.VULNERABLE] = 1
            if logger:
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="TRAIT_STATE_APPLIED",
                    details={
                        "trait": "El más débil",
                        "power_total": group.poder_total,
                        "global_median": global_power_median,
                        "state": "Vulnerable"
                    }
                )
    else:
        if StateType.SORPRESA not in group.estados:
            group.estados[StateType.SORPRESA] = 1
            if logger:
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="TRAIT_STATE_APPLIED",
                    details={
                        "trait": "El más débil",
                        "power_total": group.poder_total,
                        "global_median": global_power_median,
                        "state": "Sorpresa"
                    }
                )
                
# ============================================================================
# MÓDULO 15B: Nuevas acciones (Forjar, Congelar)
# ============================================================================

@dataclass
class ForgeResult:
    """Resultado de la acción Forjar (reemplaza Entrenar)"""
    success: bool
    event_type: str
    details: Dict[str, Any]
    new_power_avg: float
    power_increase_percent: int
    population_cost: int


def action_forge(group: 'Group', rng: random.Random) -> ForgeResult:
    """
    Forjar: +3% poder, reemplaza Entrenar para Enano del metal.
    """
    old_power_avg = group.poder_promedio
    power_increase_percent = 3
    new_power_avg = old_power_avg * (1 + power_increase_percent / 100.0)
    
    return ForgeResult(
        success=True,
        event_type="FORGE_SUCCESS",
        details={
            "old_power_avg": old_power_avg,
            "new_power_avg": new_power_avg,
            "power_increase_percent": power_increase_percent,
            "old_total_power": group.poder_total,
            "new_total_power": group.poblacion * new_power_avg,
            "population": group.poblacion
        },
        new_power_avg=new_power_avg,
        power_increase_percent=power_increase_percent,
        population_cost=0
    )


@dataclass
class FreezeResult:
    """Resultado de la acción Congelar (Gigante Nieve)"""
    success: bool
    event_type: str
    details: Dict[str, Any]
    steps: List[Tuple[int, int]]
    tiles_frozen: List[Tuple[int, int]]


def calculate_freeze_path(group: 'Group', direction: str, 
                          world: 'World', rng: random.Random) -> FreezeResult:
    """
    Congelar: 2-4 casillas en línea.
    No consume movimiento del grupo.
    """
    from models import TerrainType, TileEffect, TileEffectType
    
    distance = rng.randint(2, 4)
    DIR_VECTORS = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'O': (-1, 0)}
    dx, dy = DIR_VECTORS.get(direction, (0, 0))
    
    steps = []
    frozen_tiles = []
    current_x, current_y = group.x, group.y
    
    for step in range(1, distance + 1):
        next_x = current_x + dx * step
        next_y = current_y + dy * step
        
        if not world.is_valid_coordinates(next_x, next_y):
            break
        
        tile = world.get_tile(next_x, next_y)
        if tile and tile.terreno != TerrainType.AGUA:
            steps.append((next_x, next_y))
            frozen_tiles.append((next_x, next_y))
        else:
            # Agua no se puede congelar
            break
    
    return FreezeResult(
        success=len(steps) > 0,
        event_type="FREEZE_SUCCESS" if steps else "FREEZE_FAILED",
        details={
            "direction": direction,
            "distance_planned": distance,
            "steps_completed": len(steps),
            "frozen_positions": frozen_tiles
        },
        steps=steps,
        tiles_frozen=frozen_tiles
    )


def can_use_forge(group: 'Group') -> bool:
    """Verifica si el grupo puede usar Forjar (Enano del metal)"""
    return has_trait(group, "Herreros Legendarios")


def can_use_freeze(group: 'Group') -> bool:
    """Verifica si el grupo puede usar Congelar (Gigante Nieve)"""
    return has_trait(group, "Congelar")


# ============================================================================
# MÓDULO 15B: Efectos persistentes en tiles
# ============================================================================

def apply_freeze_effect(world: 'World', x: int, y: int, group_id: int, 
                        round_number: int, duration: int = 3) -> bool:
    """
    Aplica efecto de congelado a una casilla.
    """
    from models import TileEffect, TileEffectType
    
    tile = world.get_tile(x, y)
    if not tile:
        return False
    
    effect = TileEffect(
        tipo=TileEffectType.CONGELADO,
        x=x,
        y=y,
        duracion_restante=duration,
        aplicado_por_grupo_id=group_id,
        ronda_aplicacion=round_number
    )
    
    world.add_tile_effect(effect)
    return True


def has_freeze_effect_at(world: 'World', x: int, y: int) -> bool:
    """Verifica si una casilla tiene efecto de congelado activo"""
    return world.has_tile_effect_at(x, y, "CONGELADO")


def get_freeze_power_penalty(world: 'World', x: int, y: int) -> float:
    """Retorna el multiplicador de poder por congelado (0.9 = -10%)"""
    if has_freeze_effect_at(world, x, y):
        return 0.9
    return 1.0


# ============================================================================
# MÓDULO 15B: Elfo Alto - Solo lo mejor
# ============================================================================

@dataclass
class EliteTrainResult:
    """Resultado de Entrenamiento para Elfo Alto"""
    success: bool
    event_type: str
    details: Dict[str, Any]
    old_power_avg: float  # ← AÑADIR
    new_power_avg: float
    population_cost: int


def can_elite_train(group: 'Group', has_trained_this_round: bool) -> Tuple[bool, str]:
    """Verifica si Elfo Alto puede entrenar (1 vez por ronda)"""
    if not has_trait(group, "Solo lo mejor"):
        return True, ""
    
    if has_trained_this_round:
        return False, "already_trained_this_round"
    
    return True, ""


def action_elite_train(group: 'Group') -> EliteTrainResult:
    """
    Entrenar para Elfo Alto: +5 poder_promedio, cuesta 1 población.
    """
    if group.poblacion <= 1:
        return EliteTrainResult(
            success=False,
            event_type="ELITE_TRAIN_FAILED",
            details={"reason": "insufficient_population", "required": 1, "current": group.poblacion},
            old_power_avg=group.poder_promedio,  # ← AÑADIR
            new_power_avg=group.poder_promedio,
            population_cost=0
        )
    
    old_power_avg = group.poder_promedio
    new_power_avg = old_power_avg + 5
    old_population = group.poblacion
    new_population = old_population - 1
    
    return EliteTrainResult(
        success=True,
        event_type="ELITE_TRAIN_SUCCESS",
        details={
            "old_power_avg": old_power_avg,
            "new_power_avg": new_power_avg,
            "old_population": old_population,
            "new_population": new_population,
            "power_increase": 5,
            "population_cost": 1
        },
        old_power_avg=old_power_avg,  # ← AÑADIR
        new_power_avg=new_power_avg,
        population_cost=1
    )


# ============================================================================
# MÓDULO 15B: Elfo Silvano - Uno con la vida
# ============================================================================

def get_elf_silvano_influence_radius(settlement: 'Settlement') -> List[Tuple[int, int]]:
    """
    Radio Cruz 3 para Elfo Silvano (override R21.8)
    """
    x, y = settlement.x, settlement.y
    mask = []
    
    # Cruz 3: N,S,E,O hasta distancia 3
    for distance in range(1, 4):
        if 1 <= y - distance <= 30:
            mask.append((x, y - distance))  # N
        if 1 <= y + distance <= 30:
            mask.append((x, y + distance))  # S
        if 1 <= x - distance <= 40:
            mask.append((x - distance, y))  # O
        if 1 <= x + distance <= 40:
            mask.append((x + distance, y))  # E
    
    return mask


def can_build_fortaleza_for_group(group: 'Group') -> bool:
    """Verifica si el grupo puede construir Ciudad Fortaleza"""
    if has_trait(group, "Uno con la vida"):
        return False
    return True


def apply_surprise_in_sylvan_radius(world: 'World', settlement: 'Settlement',
                                     logger: 'Logger', round_number: int,
                                     turn_index: int) -> None:
    """
    Aplica Sorpresa a grupos enemigos dentro del radio de Elfo Silvano.
    """
    if not hasattr(settlement, 'influence_radius'):
        return
    
    for x, y in settlement.influence_radius:
        groups_on_tile = world.get_groups_on_tile(x, y)
        for group in groups_on_tile:
            if group.id != settlement.dueño_grupo_id:
                if StateType.SORPRESA not in group.estados:
                    group.estados[StateType.SORPRESA] = 1
                    if logger:
                        logger.log_event(
                            round_num=round_number,
                            turn_index=turn_index,
                            group_id=group.id,
                            event_type="TRAIT_EFFECT_APPLIED",
                            details={
                                "trait": "Uno con la vida",
                                "effect": "Sorpresa_en_radio",
                                "settlement_id": settlement.id,
                                "state": "Sorpresa"
                            }
                        )


# ============================================================================
# MÓDULO 15B: Humano Ciudad - Metrópolis
# ============================================================================

def get_settlement_max_level(settlement: 'Settlement') -> int:
    """
    Nivel máximo para Humano Ciudad: 7, para otros: 5.
    """
    if settlement.raza == "Humano" and settlement.subraza == "Ciudad":
        return 7
    return 5


def get_influence_radius_for_level(level: int, settlement: 'Settlement') -> List[Tuple[int, int]]:
    """
    Radio de influencia con override para Elfo Silvano y Metrópolis.
    """
    if has_trait_by_race(settlement.raza, settlement.subraza, "Uno con la vida"):
        return get_elf_silvano_influence_radius(settlement)
    
    # Metroplis nivel 7: radio +1 adicional
    if settlement.raza == "Humano" and settlement.subraza == "Ciudad" and level == 7:
        # Cruz 2 + Rodeo 1 (nivel 5) + radio extra
        return get_cross_mask(settlement.x, settlement.y, 2) + get_ring_mask(settlement.x, settlement.y, 1)
    
    # Niveles estándar
    if level == 1:
        return []
    elif level == 2:
        return get_cross_mask(settlement.x, settlement.y, 1)
    elif level == 3 or level == 4:
        return get_ring_mask(settlement.x, settlement.y, 1)
    elif level >= 5:
        return get_cross_mask(settlement.x, settlement.y, 2) + get_ring_mask(settlement.x, settlement.y, 1)


def has_trait_by_race(race: str, subrace: str, trait_name: str) -> bool:
    """Helper para verificar rasgos por raza/subraza"""
    trait_map = {
        ("Humano", "Ciudad"): ["Expansionista", "Metrópolis"],
        ("Elfo", "Silvano"): ["Uno con la vida", "Nómada"],
        ("Enano", "Del metal"): ["Herreros Legendarios"],
        ("Gigante", "Nieve"): ["Congelar"],
        ("Gigante", "Bosque"): ["Guardián de la Naturaleza"],
        ("Elfo", "Alto"): ["Solo lo mejor"],
    }
    return trait_name in trait_map.get((race, subrace), [])


def is_metropolis_settlement(settlement: 'Settlement') -> bool:
    """Verifica si es un asentamiento de Humano Ciudad nivel 7"""
    return (settlement.raza == "Humano" and 
            settlement.subraza == "Ciudad" and 
            settlement.nivel == 7)


def is_metropolis_settlement_owner(group: 'Group', world: 'World') -> bool:
    """Verifica si el grupo es dueño de una ciudad Metrópolis nivel 7."""
    for settlement in world.get_all_settlements():
        if settlement.dueño_grupo_id == group.id and is_metropolis_settlement(settlement):
            return True
    return False

# ============================================================================
# MÓDULO 15B: Guardián de la Naturaleza - destrucción de construcciones
# ============================================================================

def destroy_structures_along_path(world: 'World', path: List[Tuple[int, int]],
                                   group_id: int, logger: 'Logger',
                                   round_number: int, turn_index: int) -> List[Tuple[int, int]]:
    """
    Destruye construcciones en la ruta de migración (Guardián de la Naturaleza).
    """
    destroyed = []
    for x, y in path:
        structure = world.get_structure_at(x, y)
        if structure:
            world.remove_structure(x, y)
            destroyed.append((x, y))
            if logger:
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group_id,
                    event_type="construction_destroyed_by_trait",
                    details={
                        "trait": "Guardián de la Naturaleza",
                        "position": f"({x},{y})",
                        "structure_type": structure.tipo.value
                    }
                )
    return destroyed

# ============================================================================
# MÓDULO 15C: Nuevos rasgos
# ============================================================================

# ----------------------------------------------------------------------------
# Humano Nevado - La caza helada
# ----------------------------------------------------------------------------

def can_attack_same_target(group: 'Group', target_id: int) -> Tuple[bool, str]:
    """
    Verifica si el grupo puede atacar al mismo objetivo.
    R: Caza helada - No puede atacar al mismo objetivo en el siguiente turno.
    """
    if has_trait(group, "La caza helada"):
        if getattr(group, '_last_attacked_target_id', None) == target_id:
            return False, "cannot_attack_same_target_next_turn"
    return True, ""


def record_attack_target(group: 'Group', target_id: int) -> None:
    """Registra el último objetivo atacado para Caza helada."""
    if has_trait(group, "La caza helada"):
        group._last_attacked_target_id = target_id


def apply_entorpecido_on_attack(attacker: 'Group', defender: 'Group',
                                 logger: Optional['Logger'] = None,
                                 round_number: int = 0, turn_index: int = -1) -> None:
    """
    Caza helada: Al atacar, aplica Entorpecido al enemigo.
    """
    if not has_trait(attacker, "La caza helada"):
        return
    
    if StateType.ENTORPECIDO not in defender.estados:
        defender.estados[StateType.ENTORPECIDO] = 1
        if logger:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=defender.id,
                event_type="trait_state_applied",
                details={
                    "trait": "La caza helada",
                    "attacker_id": attacker.id,
                    "state": "Entorpecido",
                    "duration": 1
                }
            )


def can_free_move_after_attack(group: 'Group') -> bool:
    """
    Caza helada: Puede moverse después de atacar (acción gratuita).
    """
    if not has_trait(group, "La caza helada"):
        return False
    
    if getattr(group, '_free_move_used_this_turn', False):
        return False
    
    return True


def mark_free_move_used(group: 'Group') -> None:
    """Marca que se usó la acción gratuita de movimiento en este turno."""
    group._free_move_used_this_turn = True


def reset_free_move_flag(group: 'Group') -> None:
    """Reinicia el flag de movimiento gratuito al inicio de ronda."""
    group._free_move_used_this_turn = False
    group._last_attacked_target_id = None


# ----------------------------------------------------------------------------
# Humano Desértico - Acosador
# ----------------------------------------------------------------------------

def apply_acoser_effects(winner: 'Group', loser: 'Group', 
                          logger: Optional['Logger'] = None,
                          round_number: int = 0, turn_index: int = -1) -> None:
    """
    Acosador: Siempre aplica Agotado + Vulnerable al oponente en combate.
    Aplica tanto si gana como si pierde, tanto si es atacante como defensor.
    """
    # Aplicar efectos al perdedor si tiene Acosador
    if has_trait(winner, "Acosador"):
        _apply_exhausted_vulnerable(loser, winner.id, "winner", logger, round_number, turn_index)
    
    # Aplicar efectos al ganador si el perdedor tiene Acosador
    if has_trait(loser, "Acosador"):
        _apply_exhausted_vulnerable(winner, loser.id, "loser", logger, round_number, turn_index)


def _apply_exhausted_vulnerable(target: 'Group', source_id: int, source_role: str,
                                 logger: Optional['Logger'] = None,
                                 round_number: int = 0, turn_index: int = -1) -> None:
    """Aplica Agotado y Vulnerable a un grupo."""
    states_applied = []
    
    if StateType.AGOTADO not in target.estados:
        target.estados[StateType.AGOTADO] = 1
        states_applied.append("Agotado")
    
    if StateType.VULNERABLE not in target.estados:
        target.estados[StateType.VULNERABLE] = 1
        states_applied.append("Vulnerable")
    
    if logger and states_applied:
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=target.id,
            event_type="trait_state_applied",
            details={
                "trait": "Acosador",
                "source_id": source_id,
                "source_role": source_role,
                "states_applied": states_applied,
                "duration": 1
            }
        )


# ----------------------------------------------------------------------------
# Orco - Buscapleitos
# ----------------------------------------------------------------------------

def calculate_hostility_bonus(attacker: 'Group', defender: 'Group') -> int:
    """
    Buscapleitos: +5% a +20% poder según hostilidad.
    
    Hostilidad se determina por reputación:
    - Reputación 1-2 (Enemigos): +20%
    - Reputación 3-4 (Hostiles/Neutrales): +10%
    - Reputación 5-6 (Conocidos/Aliados): +5%
    - Reputación 7 (Amigos): 0%
    """
    from rules import get_reputation
    
    if not has_trait(attacker, "Buscapleitos"):
        return 0
    
    rep = get_reputation(attacker, defender.id)
    
    if rep <= 2:
        bonus = 20
    elif rep <= 4:
        bonus = 10
    elif rep <= 6:
        bonus = 5
    else:
        bonus = 0
    
    return bonus


def apply_buscapleitos_bonus(group: 'Group', opponent: 'Group') -> float:
    """
    Aplica multiplicador de poder por Buscapleitos.
    Retorna multiplicador (ej: 1.20 para +20%).
    """
    bonus = calculate_hostility_bonus(group, opponent)
    if bonus > 0:
        return 1.0 + (bonus / 100.0)
    return 1.0


# ----------------------------------------------------------------------------
# Constructo Centinela Arcano - Guardián del Orden
# ----------------------------------------------------------------------------

def calculate_guardian_power_bonus(attacker: 'Group', defender: 'Group') -> float:
    """
    Guardián del Orden: +10% o +15% poder según reputación fuera de rango 4.
    
    Si reputación está fuera del rango 4 (>=5 o <=3):
    - +10% si réplica (defensor)
    - +15% si es atacante
    """
    from rules import get_reputation
    
    if not has_trait(attacker, "Guardián del Orden"):
        return 1.0
    
    rep = get_reputation(attacker, defender.id)
    
    # Solo activa si reputación está fuera del rango 4
    if rep == 4:
        return 1.0
    
    # Determinar rol (esto debe pasarse desde el contexto)
    # Por defecto asumimos +10%, el caller debe especificar si es ataque (+15%)
    return 1.0  # El valor específico se determina en combat_resolver


def get_guardian_power_multiplier(attacker: 'Group', defender: 'Group', is_attacking: bool) -> float:
    """
    Guardián del Orden: Retorna multiplicador de poder.
    - +10% si defendiendo
    - +15% si atacando
    """
    from rules import get_reputation
    
    if not has_trait(attacker, "Guardián del Orden"):
        return 1.0
    
    rep = get_reputation(attacker, defender.id)
    
    if rep == 4:
        return 1.0
    
    bonus = 15 if is_attacking else 10
    return 1.0 + (bonus / 100.0)


def is_immune_to_fear_by_guardian(group: 'Group') -> bool:
    """Guardián del Orden: Inmune a Miedo."""
    if has_trait(group, "Guardián del Orden"):
        return True
    return False


# ----------------------------------------------------------------------------
# Mediano Pies Ligeros - Pies ligeros
# ----------------------------------------------------------------------------

def can_ignore_city_during_migration(group: 'Group') -> bool:
    """
    Pies ligeros: Durante migración puede atravesar ciudades sin interactuar.
    """
    return has_trait(group, "Pies ligeros")


def can_bypass_city_interaction(group: 'Group') -> bool:
    """
    Verifica si el grupo puede ignorar ciudades durante migración.
    """
    return can_ignore_city_during_migration(group)


# ----------------------------------------------------------------------------
# Mediano Peloso - Amigos distantes
# ----------------------------------------------------------------------------

def does_not_trigger_harmful_effects(group: 'Group') -> bool:
    """
    Amigos distantes: No activa efectos nocivos.
    """
    return has_trait(group, "Amigos distantes")


def can_merge_without_reputation_7(group: 'Group') -> bool:
    """
    Amigos distantes: Puede unirse sin requerir reputación 7 tras división.
    """
    return has_trait(group, "Amigos distantes")


def calculate_merge_peloso(
    origin_id_a: int, origin_id_b: int,
    subrace_a: str, subrace_b: str,
    reputation_a_to_b: int, reputation_b_to_a: int,
    population_a: int, population_b: int,
    power_a: float, power_b: float
) -> Tuple[bool, int, float, Optional[str]]:
    """
    Cálculo de unión para Mediano Peloso (Amigos distantes).
    Puede unirse sin requerir reputación 7 si al menos uno tiene el rasgo.
    """
    if subrace_a != subrace_b:
        return False, 0, 0.0, "different_subrace"
    
    if origin_id_a != origin_id_b:
        return False, 0, 0.0, "different_origin"
    
    # Amigos distantes: omitir verificación de reputación 7
    # (ya que pueden unirse sin requisito)
    
    total_pop = population_a + population_b
    if total_pop > 0:
        new_power = math.ceil(
            (power_a * population_a + power_b * population_b) / total_pop
        )
    else:
        new_power = 0.0
    
    return True, total_pop, new_power, None


# ----------------------------------------------------------------------------
# Enano de piedra - Como una joya (completar)
# ----------------------------------------------------------------------------

def can_build_fortaleza_for_dwarf(group: 'Group', settlement_at_tile=None) -> Tuple[bool, str]:
    """
    Como una joya: Puede construir Ciudad Fortaleza con límite máximo 10.
    """
    if not has_trait(group, "Como una joya"):
        return True, ""  # Otros grupos no tienen límite especial
    
    built_count = getattr(group, '_fortaleza_construidas', 0)
    if built_count >= 10:
        return False, f"max_fortalezas_reached_{built_count}_of_10"
    
    return True, ""


def register_fortaleza_built(group: 'Group', logger: Optional['Logger'] = None,
                              round_number: int = 0, turn_index: int = -1) -> None:
    """
    Registra que el grupo construyó una Ciudad Fortaleza.
    Incrementa contador y registra log.
    """
    if not has_trait(group, "Como una joya"):
        return
    
    current = getattr(group, '_fortaleza_construidas', 0)
    group._fortaleza_construidas = current + 1
    
    if logger:
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group.id,
            event_type="trait_city_fortress_count",
            details={
                "trait": "Como una joya",
                "fortalezas_construidas": group._fortaleza_construidas,
                "max_allowed": 10
            }
        )


def is_fortaleza_unupgradeable(settlement: 'Settlement', group: 'Group') -> bool:
    """
    Como una joya: Ciudades Fortaleza construidas por este grupo son inmejorables.
    """
    if not has_trait(group, "Como una joya"):
        return False
    
    # Verificar si este asentamiento fue construido por este grupo como Ciudad Fortaleza
    # (Esto requiere tracking en el asentamiento)
    return getattr(settlement, '_construido_por_enano', False) and settlement.nivel == 1


def apply_entorpecido_when_attacked_by_dwarf(defender: 'Group', attacker: 'Group',
                                              logger: Optional['Logger'] = None,
                                              round_number: int = 0, turn_index: int = -1) -> None:
    """
    Como una joya: Si es atacado, aplica Entorpecido al atacante.
    """
    if not has_trait(defender, "Como una joya"):
        return
    
    if StateType.ENTORPECIDO not in attacker.estados:
        attacker.estados[StateType.ENTORPECIDO] = 1
        if logger:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=attacker.id,
                event_type="trait_state_applied",
                details={
                    "trait": "Como una joya",
                    "defender_id": defender.id,
                    "state": "Entorpecido",
                    "duration": 1
                }
            )


def mark_settlement_as_built_by_dwarf(settlement: 'Settlement') -> None:
    """Marca un asentamiento como construido por Enano de piedra."""
    settlement._construido_por_enano = True


# ----------------------------------------------------------------------------
# Integración de inmunidades para Guardián del Orden
# ----------------------------------------------------------------------------

def is_immune_to_state_15c(group: 'Group', state_name: str) -> bool:
    """
    Verifica inmunidades por rasgos del Módulo 15C.
    """
    if has_trait(group, "Guardián del Orden") and state_name == "Miedo":
        return True
    return False

def set_free_move_available(group: 'Group', available: bool) -> None:
    """Establece si el grupo tiene movimiento gratuito disponible (Caza helada)."""
    group._free_move_available = available


def has_free_move_available(group: 'Group') -> bool:
    """Verifica si el grupo tiene movimiento gratuito disponible."""
    return getattr(group, '_free_move_available', False)