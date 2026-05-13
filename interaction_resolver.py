"""
interaction_resolver.py - Orquestación de interacciones entre grupos.
MÓDULO 15C: Integra Amigos distantes (Mediano Peloso).
BUGFIX #002: Implementada actualización de reputación en combates (R17)
"""

import random
from typing import List, Dict, Optional

from models import Group
from world import World
from logger import Logger
from rules import (
    group_by_origin, 
    get_reputation, 
    choose_interaction_type, 
    calculate_merge,
    get_stack_reputation,
    has_trait,
    calculate_merge_peloso,  # MÓDULO 15C
)
from combat_resolver import resolve_combat, resolve_stack_combat, apply_rebound


def _update_reputation_after_hostile_interaction(
    group_a: Group, group_b: Group, 
    logger: Logger, round_number: int, turn_index: int
) -> None:
    """
    BUGFIX #002: Actualiza reputación después de una interacción hostil.
    Manual R17.4: "Interacción hostil: -1"
    
    Args:
        group_a: Primer grupo
        group_b: Segundo grupo
        logger: Logger para registrar cambios
        round_number: Ronda actual
        turn_index: Índice de turno
    """
    # Obtener reputaciones actuales
    rep_a_to_b = get_reputation(group_a, group_b.id)
    rep_b_to_a = get_reputation(group_b, group_a.id)
    
    # Aplicar cambio por interacción hostil: -1
    new_rep_a_to_b = max(1, rep_a_to_b - 1)  # Mínimo 1 (Enemigos)
    new_rep_b_to_a = max(1, rep_b_to_a - 1)  # Mínimo 1 (Enemigos)
    
    # Actualizar reputaciones
    group_a.reputacion[group_b.id] = new_rep_a_to_b
    group_b.reputacion[group_a.id] = new_rep_b_to_a
    
    # Loguear cambios
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=group_a.id,
        event_type="REPUTATION_CHANGED",
        details={
            "group_id_a": group_a.id,
            "group_id_b": group_b.id,
            "interaction_type": "HOSTILE",
            "old_reputation_a_to_b": rep_a_to_b,
            "new_reputation_a_to_b": new_rep_a_to_b,
            "old_reputation_b_to_a": rep_b_to_a,
            "new_reputation_b_to_a": new_rep_b_to_a,
            "change": -1
        }
    )


def _update_reputation_after_peaceful_interaction(
    group_a: Group, group_b: Group, 
    logger: Logger, round_number: int, turn_index: int
) -> None:
    """
    BUGFIX #002: Actualiza reputación después de una interacción pacífica.
    Manual R17.3: "Interacción pacífica: +1"
    
    Args:
        group_a: Primer grupo
        group_b: Segundo grupo
        logger: Logger para registrar cambios
        round_number: Ronda actual
        turn_index: Índice de turno
    """
    # Obtener reputaciones actuales
    rep_a_to_b = get_reputation(group_a, group_b.id)
    rep_b_to_a = get_reputation(group_b, group_a.id)
    
    # Aplicar cambio por interacción pacífica: +1
    new_rep_a_to_b = min(7, rep_a_to_b + 1)  # Máximo 7 (Amigos)
    new_rep_b_to_a = min(7, rep_b_to_a + 1)  # Máximo 7 (Amigos)
    
    # Actualizar reputaciones
    group_a.reputacion[group_b.id] = new_rep_a_to_b
    group_b.reputacion[group_a.id] = new_rep_b_to_a
    
    # Loguear cambios
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=group_a.id,
        event_type="REPUTATION_CHANGED",
        details={
            "group_id_a": group_a.id,
            "group_id_b": group_b.id,
            "interaction_type": "PEACEFUL",
            "old_reputation_a_to_b": rep_a_to_b,
            "new_reputation_a_to_b": new_rep_a_to_b,
            "old_reputation_b_to_a": rep_b_to_a,
            "new_reputation_b_to_a": new_rep_b_to_a,
            "change": +1
        }
    )


def resolve_tile_interactions(world: World, x: int, y: int,
                              rng: random.Random, logger: Logger,
                              round_number: int, turn_index: int) -> None:
    """
    Resuelve todas las interacciones en una casilla según Regla 13.
    MÓDULO 15C: Integra Amigos distantes.
    BUGFIX #002: Ahora actualiza reputación después de interacciones (R17)
    """
    groups = world.get_groups_on_tile(x, y)
    
    if len(groups) < 2:
        return
    
    # Regla 13.4: Agrupar por origen
    stacks = group_by_origin(groups)
    stack_list = list(stacks.values())
    
    if len(stack_list) < 2:
        return
    
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=-1,
        event_type="TILE_INTERACTION_START",
        details={
            "position": f"({x},{y})",
            "stacks_count": len(stack_list)
        }
    )
    
    # Resolver todas las combinaciones (i, j) con i < j
    active_stacks = stack_list.copy()
    i = 0
    
    while i < len(active_stacks):
        stack_i = active_stacks[i]
        rep_i = stack_i[0]  # Grupo representante del stack
        
        j = i + 1
        while j < len(active_stacks):
            stack_j = active_stacks[j]
            rep_j = stack_j[0]
            
            # Verificar si ambos stacks tienen grupos vivos
            stack_i_alive = any(g.poblacion > 0 for g in stack_i)
            stack_j_alive = any(g.poblacion > 0 for g in stack_j)
            
            if stack_i_alive and stack_j_alive:
                # Determinar tipo de interacción (R13.2)
                rep_level = get_stack_reputation(rep_i, stack_j)
                interaction_type = choose_interaction_type(rep_level, rng)
                
                if interaction_type == "HOSTIL":
                    # COMBATE
                    winner_stack, loser_stack = resolve_stack_combat(
                        stack_i, stack_j, world, rng, logger, round_number, turn_index
                    )
                    
                    # BUGFIX #002: Actualizar reputación después del combate hostil
                    # Reducir reputación entre los stacks (cada grupo vs cada grupo)
                    if winner_stack and loser_stack:
                        for winner in winner_stack:
                            for loser in loser_stack:
                                _update_reputation_after_hostile_interaction(
                                    winner, loser, logger, round_number, turn_index
                                )
                    
                    # Actualizar stacks activos
                    active_stacks = [s for s in active_stacks if any(g.poblacion > 0 for g in s)]
                    i = 0
                    break
                else:
                    # INTERACCIÓN PACÍFICA - posible unión
                    
                    # MÓDULO 15C: Verificar si alguno tiene Amigos distantes
                    has_peloso_a = any(has_trait(g, "Amigos distantes") for g in stack_i)
                    has_peloso_b = any(has_trait(g, "Amigos distantes") for g in stack_j)
                    
                    if has_peloso_a or has_peloso_b:
                        can_merge, new_pop, new_power, reason = calculate_merge_peloso(
                            origin_id_a=rep_i.grupo_original_id or rep_i.id,
                            origin_id_b=rep_j.grupo_original_id or rep_j.id,
                            subrace_a=rep_i.subraza,
                            subrace_b=rep_j.subraza,
                            reputation_a_to_b=get_reputation(rep_i, rep_j.id),
                            reputation_b_to_a=get_reputation(rep_j, rep_i.id),
                            population_a=sum(g.poblacion for g in stack_i),
                            population_b=sum(g.poblacion for g in stack_j),
                            power_a=rep_i.poder_promedio,
                            power_b=rep_j.poder_promedio,
                            has_peloso_a=has_peloso_a,
                            has_peloso_b=has_peloso_b
                        )
                        
                        if can_merge:
                            logger.log_event(
                                round_num=round_number,
                                turn_index=turn_index,
                                group_id=-1,
                                event_type="TRAIT_OVERRIDE_APPLIED",
                                details={
                                    "trait": "Amigos distantes",
                                    "effect": "union_sin_reputacion_7",
                                    "stack_a_origin": rep_i.grupo_original_id or rep_i.id,
                                    "stack_b_origin": rep_j.grupo_original_id or rep_j.id
                                }
                            )
                    else:
                        can_merge, new_pop, new_power, reason = calculate_merge(
                            origin_id_a=rep_i.grupo_original_id or rep_i.id,
                            origin_id_b=rep_j.grupo_original_id or rep_j.id,
                            subrace_a=rep_i.subraza,
                            subrace_b=rep_j.subraza,
                            reputation_a_to_b=get_reputation(rep_i, rep_j.id),
                            reputation_b_to_a=get_reputation(rep_j, rep_i.id),
                            population_a=sum(g.poblacion for g in stack_i),
                            population_b=sum(g.poblacion for g in stack_j),
                            power_a=rep_i.poder_promedio,
                            power_b=rep_j.poder_promedio
                        )
                    
                    if can_merge:
                        # Unir stacks (absorber stack_j en stack_i)
                        target_group = stack_i[0]
                        
                        logger.log_event(
                            round_num=round_number,
                            turn_index=turn_index,
                            group_id=target_group.id,
                            event_type="STACK_MERGE",
                            details={
                                "absorbing_origin": rep_i.grupo_original_id or rep_i.id,
                                "absorbed_origin": rep_j.grupo_original_id or rep_j.id,
                                "new_population": new_pop,
                                "new_power": new_power,
                                "peloso_override": (has_peloso_a or has_peloso_b)
                            }
                        )
                        
                        # Mover población al grupo objetivo
                        for group in stack_j:
                            if group.id != target_group.id:
                                target_group.poblacion += group.poblacion
                                target_group.poder_promedio = new_power
                                world.remove_group(group.id)
                        
                        # BUGFIX #002: Actualizar reputación después de merge pacífico
                        # Aumentar reputación entre los stacks (solo una vez por merge)
                        for group_a in stack_i:
                            for group_b in stack_j:
                                if group_a.id != group_b.id:
                                    _update_reputation_after_peaceful_interaction(
                                        group_a, group_b, logger, round_number, turn_index
                                    )
                        
                        active_stacks = [s for s in active_stacks if s != stack_j]
                        i = 0
                        break
            
            j += 1
        i += 1
    
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=-1,
        event_type="TILE_INTERACTION_END",
        details={
            "position": f"({x},{y})",
            "remaining_groups": len([g for g in world.get_groups_on_tile(x, y) if g.poblacion > 0])
        }
    )
