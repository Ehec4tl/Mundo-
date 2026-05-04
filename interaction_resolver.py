"""
interaction_resolver.py - Orquestación de interacciones entre grupos.
MÓDULO 15C: Integra Amigos distantes (Mediano Peloso).
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


def resolve_tile_interactions(world: World, x: int, y: int,
                              rng: random.Random, logger: Logger,
                              round_number: int, turn_index: int) -> None:
    """
    Resuelve todas las interacciones en una casilla según Regla 13.
    MÓDULO 15C: Integra Amigos distantes.
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