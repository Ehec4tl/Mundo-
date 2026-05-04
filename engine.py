# engine.py
"""
Módulo Engine - Loop global de rondas y sistema de turnos.
Integración completa con sistema de interacciones y reputación.
CORREGIDO: Llama a on_group_death_settlements cuando un grupo muere.
Implementa nacimientos cada 5 rondas (Módulo 10).
MÓDULO 11: Implementa Crecer (R7), Entrenar (R8), Sobrepoblación (R25)
MÓDULO 12: Implementa Migrar (R9)
MÓDULO 14: Implementa Rasgos (Nómada, Navegante, Anfibio, Crecimiento Exponencial, Expansionista)
MÓDULO 15A: Implementa rasgos Goblin (El más débil) y Reflejos Felinos
MÓDULO 15B: Implementa rasgos Enano del metal (Forjar), Gigante Nieve (Congelar), Elfo Alto (Entrenar élite)
MÓDULO 15B: Implementa rasgos Sylvan (Uno con la vida) y Guardián de la Naturaleza
MÓDULO 15C: Implementa rasgos Pies ligeros, La caza helada, Guardián del Orden, Peloso
"""

from typing import List, Optional, Callable, Dict, Any
import random
import math
from models import Group, StateType, TerrainType, TileEffectType
from world import World
from logger import Logger
from interaction_resolver import resolve_tile_interactions
from combat_resolver import resolve_combat, resolve_city_battle
from rules import (
    on_group_death_settlements,
    create_group_from_settlement,
    calculate_birth_distribution,
    calculate_housing_bonus,
    has_housing_upgrade_for_group,
    action_grow,
    action_train,
    has_grow_consecutive,
    calculate_forced_split,
    action_settle,
    SettleResult,
    # MÓDULO 12: Migrar
    calculate_migrate_distance,
    can_start_migration,
    get_coords_in_direction,
    can_enter_tile_during_migration,
    # MÓDULO 14: Rasgos
    has_trait,
    can_move_during_establishing,
    can_migrate_during_establishing,
    can_settle_during_establishing,
    calculate_growth_factor,
    should_apply_exhausted_from_overpopulation,
    can_migrate_on_water,
    apply_surprise_on_exit_water,
    is_immune_to_combat_state,
    move_navigator_on_water,
    calculate_siege_participants,
    calculate_siege_losses_when_losing,
    # MÓDULO 15A: Rasgos Goblin y Reflejos Felinos
    can_goblin_train,
    is_grow_free_for_goblin,
    apply_cat_reflexes_surprise,
    calculate_goblin_power_comparison,
    calculate_global_power_median,
    set_attacked_flag,
    # MÓDULO 15A: Elfo Oscuro (Como una sombra)
    apply_surprise_on_migration,
    # MÓDULO 15B: Nuevos rasgos
    action_forge,
    can_use_forge,
    action_elite_train,
    can_elite_train,
    calculate_freeze_path,
    apply_freeze_effect,
    get_freeze_power_penalty,
    get_settlement_max_level,
    get_influence_radius_for_level,
    has_trait_by_race,
    is_metropolis_settlement,
    destroy_structures_along_path,
    can_build_fortaleza_for_group,
    apply_surprise_in_sylvan_radius,
    # MÓDULO 15C: Nuevos rasgos
    can_attack_same_target,
    record_attack_target,
    apply_entorpecido_on_attack,
    can_free_move_after_attack,
    mark_free_move_used,
    reset_free_move_flag,
    set_free_move_available,
    has_free_move_available,
    can_build_fortaleza_for_dwarf,
    register_fortaleza_built,
    is_fortaleza_unupgradeable,
    mark_settlement_as_built_by_dwarf,
    can_bypass_city_interaction,
    is_immune_to_fear_by_guardian,
    is_immune_to_state_15c,
    calculate_merge_peloso,
)


# ============================================================================
# FUNCIONES DE APOYO
# ============================================================================

def can_use_freeze(group: Group) -> bool:
    """Verifica si el grupo puede usar la acción Congelar (Gigante Nieve)."""
    return has_trait(group, "Congelar")


def _apply_freeze_penalties(world: World, logger: Logger, round_number: int) -> None:
    """Aplica penalización de congelado a grupos en tiles congelados."""
    for group in world.get_all_groups():
        if not group.alive:
            continue
        
        freeze_penalty = get_freeze_power_penalty(world, group.x, group.y)
        if freeze_penalty < 1.0:
            if not hasattr(group, '_freeze_multiplier'):
                group._freeze_multiplier = 1.0
            group._freeze_multiplier = freeze_penalty
            logger.log_event(
                round_num=round_number,
                turn_index=-1,
                group_id=group.id,
                event_type="TILE_EFFECT_APPLIED",
                details={
                    "effect_type": "CONGELADO",
                    "position": f"({group.x},{group.y})",
                    "power_multiplier": freeze_penalty
                }
            )
        else:
            if hasattr(group, '_freeze_multiplier'):
                group._freeze_multiplier = 1.0


def _apply_sylvan_radius_effects(world: World, logger: Logger, round_number: int) -> None:
    """
    Aplica efectos de Sylvan (Uno con la vida) en el radio de influencia.
    F1: Llamar apply_surprise_in_sylvan_radius para cada asentamiento Sylvan.
    """
    for settlement in world.get_all_settlements():
        if settlement.ruinas:
            continue
        
        if has_trait_by_race(settlement.raza, settlement.subraza, "Uno con la vida"):
            apply_surprise_in_sylvan_radius(
                world, settlement, logger, round_number, -1
            )


# ============================================================================
# APLICAR PELIGROS
# ============================================================================

def apply_dangers(world: World, rng: random.Random, logger: Logger, round_number: int) -> None:
    """
    Aplica peligros ambientales a todos los grupos al inicio de la ronda.
    Regla 12: Evaluados al inicio de cada ronda, antes de cualquier acción.
    """
    from rules import evaluate_danger, calculate_global_power_median
    
    groups = world.get_all_groups()
    
    if not groups:
        return
    
    groups_to_remove = []
    global_power_median = calculate_global_power_median(groups)
    
    for group in groups:
        if not group.alive:
            continue
        
        is_first_round = False
        
        result = evaluate_danger(
            group=group,
            global_power_median=global_power_median,
            rng=rng,
            is_first_round=is_first_round
        )
        
        logger.log_event(
            round_num=round_number,
            turn_index=-1,
            group_id=group.id,
            event_type="DANGER_EVALUATION",
            details={
                "triggered": result.triggered,
                "survived": result.survived,
                "population_before": result.population_before,
                "population_after": result.population_after,
                "power_total": result.power_total,
                "global_power_median": result.global_power_median,
                "ratio": result.ratio,
                "danger_probability": result.danger_probability,
                "survival_probability": result.survival_probability,
                "roll_value": result.roll_value,
                "loss_percentage": result.loss_percentage,
                "action_consumed": result.action_consumed
            }
        )
        
        if result.triggered and not result.survived:
            group.poblacion = result.population_after
            
            if not group.alive:
                groups_to_remove.append(group)
                logger.log_event(
                    round_num=round_number,
                    turn_index=-1,
                    group_id=group.id,
                    event_type="GROUP_DIED",
                    details={
                        "cause": "danger_failed",
                        "final_population": 0,
                        "population_before": result.population_before,
                        "loss_percentage": result.loss_percentage
                    }
                )
                group.acted_this_round = True
        
        elif result.triggered and result.survived:
            group.acted_this_round = True
    
    for group in groups_to_remove:
        from rules import on_group_death_settlements
        orphaned_settlements = on_group_death_settlements(world, group.id, logger, round_number)
        
        if orphaned_settlements:
            logger.log_event(
                round_num=round_number,
                turn_index=-1,
                group_id=group.id,
                event_type="SETTLEMENTS_ORPHANED",
                details={
                    "settlement_ids": orphaned_settlements,
                    "cause": "danger_death"
                }
            )
        
        world.remove_group(group.id)


# ============================================================================
# APLICAR EFECTOS DE RASGOS AL INICIO DE RONDA
# ============================================================================

def apply_trait_effects_start_of_round(world: World, rng: random.Random, 
                                        logger: Logger, round_number: int) -> None:
    """
    Aplica efectos de rasgos al inicio de la ronda.
    MÓDULO 15A: Reflejos Felinos (Sorpresa condicional),
                El más débil (Vulnerable/Sorpresa según poder)
    MÓDULO 15C: Reiniciar flags de Caza helada.
    """
    groups = world.get_all_groups()
    
    global_power_median = calculate_global_power_median(groups)
    
    for group in groups:
        if not group.alive:
            continue
        
        apply_cat_reflexes_surprise(group, logger, round_number, -1)
        calculate_goblin_power_comparison(group, global_power_median, logger, round_number, -1)
        
        # MÓDULO 15C: Reiniciar flags de movimiento gratuito
        reset_free_move_flag(group)
        set_free_move_available(group, False)
    
    for group in groups:
        set_attacked_flag(group, False)


# ============================================================================
# ELEGIR ACCIÓN
# ============================================================================

def choose_action(group: Group, world: World, rng: random.Random) -> str:
    """
    STUB - Elige una acción para el grupo.
    MÓDULO 14: Nómada puede moverse/migrar durante Estableciendo.
    MÓDULO 15B: Añadir Forjar y Congelar.
    """
    # Verificar si está Agotado - solo puede WAIT (R8.4)
    if StateType.AGOTADO in group.estados:
        return "WAIT"
    
    # R9.8: En Marcha solo permite acciones de movimiento (Moverse)
    if StateType.EN_MARCHA in group.estados:
        directions = ['N', 'S', 'E', 'O']
        return f"MOVE_{rng.choice(directions)}"
    
    # MÓDULO 14: Nómada puede moverse/migrar durante Estableciendo
    if StateType.ESTABLECIENDO in group.estados:
        if has_trait(group, "Nómada"):
            roll = rng.random()
            if roll < 0.5:
                directions = ['N', 'S', 'E', 'O']
                return f"MOVE_{rng.choice(directions)}"
            else:
                directions = ['N', 'S', 'E', 'O']
                return f"MIGRATE_{rng.choice(directions)}"
        else:
            return "WAIT"
    
    # MÓDULO 15B: Elfo Alto no puede usar Crecer
    if has_trait(group, "Solo lo mejor"):
        roll = rng.random()
        if roll < 0.5:
            return "TRAIN"
        elif roll < 0.8:
            directions = ['N', 'S', 'E', 'O']
            return f"MIGRATE_{rng.choice(directions)}"
        else:
            return "WAIT"
    
    # MÓDULO 15B: Enano del metal usa Forjar en lugar de Entrenar
    if can_use_forge(group):
        roll = rng.random()
        if roll < 0.2:
            return "FORGE"
        elif roll < 0.4:
            return "GROW"
        elif roll < 0.7:
            directions = ['N', 'S', 'E', 'O']
            return f"MIGRATE_{rng.choice(directions)}"
        else:
            return "WAIT"
    
    # MÓDULO 15B: Gigante Nieve usa Congelar
    if can_use_freeze(group):
        roll = rng.random()
        if roll < 0.3:
            directions = ['N', 'S', 'E', 'O']
            return f"FREEZE_{rng.choice(directions)}"
        elif roll < 0.5:
            return "GROW"
        elif roll < 0.7:
            directions = ['N', 'S', 'E', 'O']
            return f"MIGRATE_{rng.choice(directions)}"
        else:
            return "WAIT"
    
     # Verificar si puede construir (si tiene suficiente población)
    if group.poblacion >= 100:  # Umbral simple para pruebas
        roll = rng.random()
        if roll < 0.3:
            # Elegir qué construir
            build_options = ["BUILD_EMPALIZADA", "BUILD_BASTION"]
            # Puente requiere dirección
            if rng.random() < 0.5:
                directions = ['N', 'S', 'E', 'O']
                return f"BUILD_PUENTE_{rng.choice(directions)}"
            return rng.choice(build_options)
        
    # Stub simple para pruebas (grupos normales)
    roll = rng.random()
    if roll < 0.2:
        return "GROW"
    elif roll < 0.4:
        return "TRAIN"
    elif roll < 0.7:
        directions = ['N', 'S', 'E', 'O']
        return f"MIGRATE_{rng.choice(directions)}"
    else:
        return "WAIT"


# ============================================================================
# EJECUTAR ACCIÓN
# ============================================================================

def execute_action(group: Group, action: str, world: World, rng: random.Random,
                   logger: Logger, round_number: int, turn_index: int) -> None:
    """
    Ejecuta la acción elegida sobre el grupo.
    MÓDULO 14: Integra overrides de rasgos.
    MÓDULO 15A: Goblin no puede entrenar, crecimiento gratuito.
    MÓDULO 15B: Implementa Forjar, Congelar, Entrenar élite.
    MÓDULO 15C: Integración de Pies ligeros y movimiento gratuito.
    """
    from models import StateType
    
    # ========================================================================
    # Acción MOVERSE (R5) - con soporte Navegante en agua
    # ========================================================================
    if action.startswith("MOVE_"):
        direction = action.split("_")[1]
        
        if StateType.ESTABLECIENDO in group.estados and not can_move_during_establishing(group):
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="MOVE_BLOCKED",
                details={"reason": "establishing_state_active"}
            )
            group.last_action_was_grow = False
            return
        
        from rules import move_group
        
        current_tile = world.get_tile(group.x, group.y)
        is_on_water = current_tile and current_tile.terreno == TerrainType.AGUA
        
        if has_trait(group, "Navegante") and is_on_water:
            nav_result = move_navigator_on_water(world, group, direction, rng)
            
            if nav_result.success:
                old_x, old_y = group.x, group.y
                world.move_group_to(group.id, nav_result.final_x, nav_result.final_y)
                
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type=nav_result.event_type,
                    details={
                        "from": (old_x, old_y),
                        "to": (nav_result.final_x, nav_result.final_y),
                        "trait": "Navegante",
                        **nav_result.details
                    }
                )
                
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="TRAIT_OVERRIDE_APPLIED",
                    details={
                        "trait": "Navegante",
                        "regla_afectada": "moverse_en_agua",
                        "effect": "2_casillas_instead_of_1"
                    }
                )
                
                if nav_result.event_type == "NAVIGATOR_MOVE_INTERACTION_PENDING":
                    resolve_tile_interactions(
                        world, nav_result.final_x, nav_result.final_y,
                        rng, logger, round_number, turn_index
                    )
            else:
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type=nav_result.event_type,
                    details=nav_result.details
                )
            
            group.last_action_was_grow = False
            return
        
        result = move_group(world, group, direction, rng)
        
        if result.success:
            old_x, old_y = group.x, group.y
            world.move_group_to(group.id, result.new_x, result.new_y)
            
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type=result.event_type,
                details={
                    "from": (old_x, old_y),
                    "to": (result.new_x, result.new_y),
                    **result.details
                }
            )
            
            if result.event_type == "INTERACTION_PENDING" and result.interaction_groups:
                resolve_tile_interactions(
                    world, result.new_x, result.new_y,
                    rng, logger, round_number, turn_index
                )
        else:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type=result.event_type,
                details=result.details
            )
        
        group.last_action_was_grow = False
        return
    
     # ========================================================================
    # Acción CONSTRUIR
    # ========================================================================
    if action.startswith("BUILD_"):
        from rules import (
            build_empalizada, build_bastion, build_puente, build_city_fortaleza,
            BuildResult, can_build_empalizada, can_build_bastion, can_build_puente
        )
        
        # BUILD_EMPALIZADA
        if action == "BUILD_EMPALIZADA":
            result = build_empalizada(group, world, round_number, rng)
            
        # BUILD_BASTION
        elif action == "BUILD_BASTION":
            result = build_bastion(group, world, round_number, rng)
        
        # BUILD_PUENTE_* (con dirección)
        elif action.startswith("BUILD_PUENTE_"):
            direction = action.split("_")[2]
            result = build_puente(group, world, direction, round_number, rng)
        
        # BUILD_CITY_FORTALEZA
        elif action == "BUILD_CITY_FORTALEZA":
            next_id = max([s.id for s in world.get_all_settlements()] + [0]) + 1
            result = build_city_fortaleza(group, world, round_number, rng, next_id)
        
        else:
            logger.log_event(...)
            return
        
        # Aplicar resultado
        if result.success and result.structure:
            world.add_structure(result.structure)
            
            if result.converted_tile:
                x, y, _ = result.converted_tile
                world.convert_water_to_land(x, y)
            
            if result.settlement_updates:
                for sid, settlement in result.settlement_updates.items():
                    world.update_settlement(settlement)
        
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group.id,
            event_type="BUILD_FAILED",
            details={"action": action, "reason": "not_implemented_yet"}
        )
        group.last_action_was_grow = False
        return
    
    # ========================================================================
    # Acción FORJAR (Enano del metal) - reemplaza Entrenar
    # ========================================================================
    if action == "FORGE":
        if not can_use_forge(group):
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="FORGE_BLOCKED",
                details={"reason": "trait_not_present"}
            )
            group.last_action_was_grow = False
            return
        
        if StateType.AGOTADO in group.estados:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="FORGE_BLOCKED",
                details={
                    "reason": "exhausted_state_active",
                    "state_duration": group.estados.get(StateType.AGOTADO, 0)
                }
            )
            group.last_action_was_grow = False
            return
        
        result = action_forge(group, rng)
        
        old_power_avg = group.poder_promedio
        group.poder_promedio = result.new_power_avg
        
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group.id,
            event_type="TRAIT_ACTION_USED",
            details={
                "action": "FORGE",
                "trait": "Enano del metal",
                "old_power_avg": old_power_avg,
                "new_power_avg": result.new_power_avg,
                **result.details
            }
        )
        
        if StateType.AGOTADO not in group.estados:
            group.estados[StateType.AGOTADO] = 1
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="STATE_APPLIED",
                details={
                    "state": "Agotado",
                    "duration": 1,
                    "from_action": "FORGE"
                }
            )
        
        group.last_action_was_grow = False
        return
    
    # ========================================================================
    # Acción CONGELAR (Gigante Nieve)
    # ========================================================================
    if action.startswith("FREEZE_"):
        direction = action.split("_")[1]
        
        if not can_use_freeze(group):
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="FREEZE_BLOCKED",
                details={"reason": "trait_not_present"}
            )
            group.last_action_was_grow = False
            return
        
        result = calculate_freeze_path(group, direction, world, rng)
        
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group.id,
            event_type="TRAIT_ACTION_USED",
            details={
                "action": "FREEZE",
                "trait": "Congelar",
                "result": result.event_type,
                "frozen_tiles": result.tiles_frozen,
                "allowed_movement": result.allowed_movement if hasattr(result, 'allowed_movement') else None,
                "cannot_attack": result.cannot_attack if hasattr(result, 'cannot_attack') else None
            }
        )
        
        for x, y in result.tiles_frozen:
            apply_freeze_effect(world, x, y, group.id, round_number, 3)
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="TILE_EFFECT_APPLIED",
                details={
                    "effect_type": "CONGELADO",
                    "position": f"({x},{y})",
                    "duration": 3,
                    "trait": "Congelar"
                }
            )
        
        group.last_action_was_grow = False
        return
    
    # ========================================================================
    # Acción ENTRENAR (R8) - con override para Elfo Alto
    # ========================================================================
    if action == "TRAIN":
        if has_trait(group, "Solo lo mejor"):
            can_train, reason = can_elite_train(group, 
                hasattr(group, '_trained_this_round') and group._trained_this_round)
            
            if not can_train:
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="ELITE_TRAIN_BLOCKED",
                    details={"reason": reason}
                )
                group.last_action_was_grow = False
                return
            
            result = action_elite_train(group)
            
            if result.success:
                old_population = group.poblacion
                group.poblacion -= result.population_cost
                group.poder_promedio = result.new_power_avg
                group._trained_this_round = True
                
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="TRAIT_ACTION_USED",
                    details={
                        "action": "ELITE_TRAIN",
                        "trait": "Solo lo mejor",
                        "old_population": old_population,
                        "new_population": group.poblacion,
                        "population_cost": result.population_cost,
                        "old_power_avg": result.old_power_avg,
                        "new_power_avg": result.new_power_avg,
                        "success": True
                    }
                )
            else:
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="ELITE_TRAIN_BLOCKED",
                    details=result.details
                )
            
            group.last_action_was_grow = False
            return
        
        if not can_goblin_train(group):
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="TRAIN_BLOCKED",
                details={"reason": "goblin_cannot_train", "trait": "El más débil"}
            )
            group.last_action_was_grow = False
            return
        
        if StateType.AGOTADO in group.estados:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="TRAIN_BLOCKED",
                details={
                    "reason": "exhausted_state_active",
                    "state_duration": group.estados.get(StateType.AGOTADO, 0)
                }
            )
            group.last_action_was_grow = False
            return
        
        result = action_train(group)
        
        old_power_avg = group.poder_promedio
        group.poder_promedio = result.new_power_avg
        
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group.id,
            event_type="TRAIN_USED",
            details=result.details
        )
        
        if StateType.AGOTADO not in group.estados:
            group.estados[StateType.AGOTADO] = 1
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="STATE_APPLIED",
                details={
                    "state": "Agotado",
                    "duration": 1,
                    "from_action": "TRAIN"
                }
            )
        
        group.last_action_was_grow = False
        return
    
    # ========================================================================
    # Acción CRECER (R7) - MÓDULO 15A: Goblin tiene crecimiento gratuito
    # ========================================================================
    if action == "GROW":
        is_goblin_free = is_grow_free_for_goblin(group)
        
        old_population = group.poblacion
        
        if has_trait(group, "Crecimiento Exponencial"):
            factor = 2.0
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="TRAIT_OVERRIDE_APPLIED",
                details={
                    "trait": "Crecimiento Exponencial",
                    "regla_afectada": "calcular_factor_crecimiento",
                    "original_value": "1.5_o_2.0_segun_RNG",
                    "new_value": "2.0_siempre"
                }
            )
        else:
            factor = calculate_growth_factor(rng)
        
        new_population = math.ceil(old_population * factor)
        group.poblacion = new_population
        
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group.id,
            event_type="GROW_USED",
            details={
                "old_population": old_population,
                "new_population": new_population,
                "growth_factor": factor,
                "trait_applied": "Crecimiento Exponencial" if has_trait(group, "Crecimiento Exponencial") else None,
                "free_action": is_goblin_free
            }
        )
        
        if is_goblin_free:
            group.acted_this_round = False
            group.last_action_was_grow = False
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="TRAIT_OVERRIDE_APPLIED",
                details={
                    "trait": "El más débil",
                    "regla_afectada": "crecer",
                    "effect": "gratuito_sin_consumir_accion"
                }
            )
            return
        
        if has_grow_consecutive(group):
            apply_exhausted = should_apply_exhausted_from_overpopulation(group)
            
            if StateType.SOBREPOBLACION not in group.estados:
                group.estados[StateType.SOBREPOBLACION] = 2
                
                if StateType.VULNERABLE not in group.estados:
                    group.estados[StateType.VULNERABLE] = 2
                
                if apply_exhausted:
                    if StateType.AGOTADO not in group.estados:
                        group.estados[StateType.AGOTADO] = 2
                        logger.log_event(
                            round_num=round_number,
                            turn_index=turn_index,
                            group_id=group.id,
                            event_type="STATE_APPLIED",
                            details={
                                "state": "Agotado",
                                "duration": 2,
                                "from_action": "GROW_CONSECUTIVE"
                            }
                        )
                else:
                    logger.log_event(
                        round_num=round_number,
                        turn_index=turn_index,
                        group_id=group.id,
                        event_type="TRAIT_OVERRIDE_APPLIED",
                        details={
                            "trait": "Crecimiento Exponencial",
                            "regla_afectada": "sobrepoblacion_aplica_agotado",
                            "original_value": "True",
                            "new_value": "False"
                        }
                    )
                
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="STATE_APPLIED",
                    details={
                        "state": "Sobrepoblación",
                        "duration": 2,
                        "from_action": "GROW_CONSECUTIVE",
                        "previous_action_was_grow": True
                    }
                )
                
                next_group_id = max([g.id for g in world.get_all_groups()] + [0]) + 1
                split_result = calculate_forced_split(
                    group, rng, next_group_id, round_number, split_probability=0.25
                )
                
                if split_result.triggered:
                    logger.log_event(
                        round_num=round_number,
                        turn_index=turn_index,
                        group_id=group.id,
                        event_type="FORCED_SPLIT_TRIGGERED",
                        details=split_result.details
                    )
                    
                    for split_group, is_original in split_result.split_groups:
                        if is_original:
                            old_tile = world.get_tile(group.x, group.y)
                            if old_tile:
                                old_tile.remove_group(group.id)
                            group.poblacion = split_group.poblacion
                            group.estados = split_group.estados
                            if old_tile:
                                old_tile.add_group(group.id)
                        else:
                            world.add_group(split_group, round_number)
                            logger.log_event(
                                round_num=round_number,
                                turn_index=turn_index,
                                group_id=-1,
                                event_type="GROUP_CREATED_FROM_FORCED_SPLIT",
                                details={
                                    "original_group_id": group.id,
                                    "new_group_id": split_group.id,
                                    "population": split_group.poblacion
                                }
                            )
                else:
                    logger.log_event(
                        round_num=round_number,
                        turn_index=turn_index,
                        group_id=group.id,
                        event_type="FORCED_SPLIT_TRIGGERED",
                        details=split_result.details
                    )
        
        group.last_action_was_grow = True
        return
    
    # ========================================================================
    # Acción ASENTARSE (R10) - con override Expansionista
    # ========================================================================
    if action == "SETTLE":
        settlement_at_tile = world.get_settlement_by_coords(group.x, group.y)
        
        # MÓDULO 15C: Enano del metal construye Fortaleza inmejorable
        can_build, _ = can_build_fortaleza_for_dwarf(group, settlement_at_tile)
        is_dwarf_fortaleza = can_build        
        can_settle, reason = can_settle_during_establishing(group, settlement_at_tile)
        
        if not can_settle:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="SETTLE_FAILED",
                details={
                    "reason": reason,
                    "position": (group.x, group.y),
                    "has_trait_nomad": has_trait(group, "Nómada"),
                    "has_trait_expansionista": has_trait(group, "Expansionista")
                }
            )
            
            if StateType.ESTABLECIENDO not in group.estados:
                group.estados[StateType.ESTABLECIENDO] = 1
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="STATE_APPLIED",
                    details={
                        "state": "Estableciendo",
                        "duration": 1,
                        "from_action": "SETTLE_FAILED"
                    }
                )
            
            group.last_action_was_grow = False
            return
        
        context = {
            "round_number": round_number,
            "turn_index": turn_index,
            "next_settlement_id": max([s.id for s in world.get_all_settlements()] + [0]) + 1
        }
        
        result = action_settle(world, group.id, rng, logger, context)
        
        if result.success:
            if result.event_type == "SETTLEMENT_FOUNDED" and result.new_settlement:
                world.add_settlement(result.new_settlement)
                
                # MÓDULO 15C: Marcar como construida por Enano (inmejorable)
                if is_dwarf_fortaleza and result.new_settlement:
                    mark_settlement_as_built_by_dwarf(result.new_settlement)
                    logger.log_event(
                        round_num=round_number,
                        turn_index=turn_index,
                        group_id=group.id,
                        event_type="TRAIT_OVERRIDE_APPLIED",
                        details={
                            "trait": "Enano del metal",
                            "regla_afectada": "asentar_ciudad_fortaleza",
                            "effect": "ciudad_inmejorable"
                        }
                    )
                
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type=result.event_type,
                    details=result.details
                )
            elif result.new_settlement:
                old_settlement = world.get_settlement(result.settlement_id)
                if old_settlement:
                    old_settlement.nivel = result.new_settlement.nivel
                    old_settlement.puntos_ciudad = result.new_settlement.puntos_ciudad
                    old_settlement.ruinas = result.new_settlement.ruinas
                    logger.log_event(
                        round_num=round_number,
                        turn_index=turn_index,
                        group_id=group.id,
                        event_type=result.event_type,
                        details=result.details
                    )
        else:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type=result.event_type,
                details=result.details
            )
        
        if StateType.ESTABLECIENDO not in group.estados:
            group.estados[StateType.ESTABLECIENDO] = 1
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="STATE_APPLIED",
                details={
                    "state": "Estableciendo",
                    "duration": 1,
                    "from_action": "SETTLE",
                    "action_success": result.success
                }
            )
        
        if has_trait(group, "Expansionista") and StateType.ESTABLECIENDO in group.estados:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="TRAIT_OVERRIDE_APPLIED",
                details={
                    "trait": "Expansionista",
                    "regla_afectada": "asentarse_durante_estableciendo",
                    "settlement_level": settlement_at_tile.nivel if settlement_at_tile else 1
                }
            )
        
        group.last_action_was_grow = False
        return
    
    # ========================================================================
    # Acción MIGRAR (R9) - con override Anfibio, Nómada y Pies ligeros
    # ========================================================================
    if action.startswith("MIGRATE_"):
        direction = action.split("_")[1]
        
        if StateType.ESTABLECIENDO in group.estados and not can_migrate_during_establishing(group):
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="MIGRATE_FAILED",
                details={
                    "direction": direction,
                    "reason": "establishing_state_active_no_nomad",
                    "position": (group.x, group.y)
                }
            )
            group.last_action_was_grow = False
            return
        
        current_tile = world.get_tile(group.x, group.y)
        is_on_water = current_tile and current_tile.terreno == TerrainType.AGUA
        
        can_migrate, reason = can_start_migration(group, world)
        
        if not can_migrate:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="MIGRATE_FAILED",
                details={
                    "direction": direction,
                    "reason": reason,
                    "position": (group.x, group.y)
                }
            )
            group.last_action_was_grow = False
            return
        
        if is_on_water and not can_migrate_on_water(group):
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="MIGRATE_FAILED",
                details={
                    "direction": direction,
                    "reason": "cannot_migrate_from_water_without_anfibio",
                    "position": (group.x, group.y)
                }
            )
            group.last_action_was_grow = False
            return
        
        if is_on_water and has_trait(group, "Anfibio"):
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="TRAIT_OVERRIDE_APPLIED",
                details={
                    "trait": "Anfibio",
                    "regla_afectada": "migrar_en_agua",
                    "original_value": "prohibido",
                    "new_value": "permitido"
                }
            )
        
        distance_planned = calculate_migrate_distance(rng)
        start_x, start_y = group.x, group.y
        current_x, current_y = start_x, start_y
        steps_completed = 0
        cancelled = False
        cancel_reason = None
        combat_triggered = False
        
        if has_trait(group, "Como una sombra"):
            apply_surprise_on_migration(group, logger, round_number, turn_index)
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="TRAIT_OVERRIDE_APPLIED",
                details={
                    "trait": "Como una sombra",
                    "regla_afectada": "migrar_vulnerable",
                    "original_value": "Vulnerable_aplicado",
                    "new_value": "Vulnerable_NO_aplicado_Sorpresa_aplicada"
                }
            )
        else:
            if StateType.VULNERABLE not in group.estados:
                group.estados[StateType.VULNERABLE] = 1
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="STATE_APPLIED",
                    details={
                        "state": "Vulnerable",
                        "duration": 1,
                        "from_action": "MIGRATE"
                    }
                )
        
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group.id,
            event_type="MIGRATE_STARTED",
            details={
                "direction": direction,
                "distance_planned": distance_planned,
                "start_position": (start_x, start_y),
                "is_on_water": is_on_water,
                "trait_anfibio": has_trait(group, "Anfibio"),
                "trait_como_una_sombra": has_trait(group, "Como una sombra")
            }
        )
        
        migration_path = [(start_x, start_y)]
        
        for step in range(1, distance_planned + 1):
            if cancelled:
                break
            
            next_x, next_y = get_coords_in_direction(current_x, current_y, direction)
            migration_path.append((current_x, current_y))
            
            if not world.is_valid_coordinates(next_x, next_y):
                alt_dirs = []
                for alt_dir in ['N', 'S', 'E', 'O']:
                    if alt_dir == direction:
                        continue
                    alt_x, alt_y = get_coords_in_direction(current_x, current_y, alt_dir)
                    if world.is_valid_coordinates(alt_x, alt_y):
                        alt_dirs.append(alt_dir)
                
                if alt_dirs:
                    new_dir = rng.choice(alt_dirs)
                    next_x, next_y = get_coords_in_direction(current_x, current_y, new_dir)
                    logger.log_event(
                        round_num=round_number,
                        turn_index=turn_index,
                        group_id=group.id,
                        event_type="MIGRATE_STEP",
                        details={
                            "step": step,
                            "border_bounce": True,
                            "original_direction": direction,
                            "new_direction": new_dir,
                            "from": (current_x, current_y),
                            "to": (next_x, next_y)
                        }
                    )
                    direction = new_dir
                else:
                    cancelled = True
                    cancel_reason = "BORDER_NO_ALTERNATIVE"
                    break
            
            can_enter, block_reason = can_enter_tile_during_migration(next_x, next_y, group, world)
            
            # MÓDULO 15C: Pies ligeros - atravesar ciudades sin interactuar
            if not can_enter and block_reason == "CITY_BLOCKED" and can_bypass_city_interaction(group):
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="TRAIT_OVERRIDE_APPLIED",
                    details={
                        "trait": "Pies ligeros",
                        "effect": "atravesar_ciudad_sin_interaccion",
                        "position": (next_x, next_y)
                    }
                )
                can_enter = True
                block_reason = None
            
            if not can_enter:
                if block_reason == "WATER":
                    cancelled = True
                    cancel_reason = "WATER_BLOCKED"
                    break
                elif block_reason == "CITY_BLOCKED":
                    tile = world.get_tile(next_x, next_y)
                    if tile and tile.has_settlement:
                        settlement = world.get_settlement(tile.settlement_id)
                        if settlement and not settlement.ruinas:
                            combat_triggered = True
                            logger.log_event(
                                round_num=round_number,
                                turn_index=turn_index,
                                group_id=group.id,
                                event_type="MIGRATE_COMBAT_TRIGGERED",
                                details={
                                    "step": step,
                                    "combat_type": "CITY",
                                    "settlement_id": settlement.id
                                }
                            )
                            battle_result = resolve_city_battle(
                                world, group.id, settlement.id, rng, logger, round_number, turn_index
                            )
                            current_group = world.get_group(group.id)
                            if not current_group or not current_group.alive:
                                cancelled = True
                                cancel_reason = "CITY_BATTLE_DEFEAT_DEATH"
                                break
                            if current_group and (current_group.x != current_x or current_group.y != current_y):
                                current_x, current_y = current_group.x, current_group.y
                                steps_completed = step
                                migration_path.append((current_x, current_y))
                            continue
                else:
                    cancelled = True
                    cancel_reason = block_reason
                    break
            
            groups_at_dest = world.get_groups_on_tile(next_x, next_y)
            other_group = None
            for g in groups_at_dest:
                if g.id != group.id and g.alive:
                    other_group = g
                    break
            
            if other_group:
                combat_triggered = True
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="MIGRATE_COMBAT_TRIGGERED",
                    details={
                        "step": step,
                        "combat_type": "GROUP",
                        "other_group_id": other_group.id
                    }
                )
                
                winner, loser = resolve_combat(
                    group, other_group, world, rng, logger, round_number, turn_index
                )
                
                # MÓDULO 15C: Marcar movimiento gratuito disponible después del combate
                if can_free_move_after_attack(group):
                    set_free_move_available(group, True)
                    logger.log_event(
                        round_num=round_number,
                        turn_index=turn_index,
                        group_id=group.id,
                        event_type="TRAIT_OVERRIDE_APPLIED",
                        details={
                            "trait": "La caza helada",
                            "effect": "movimiento_gratuito_disponible",
                            "from": (current_x, current_y)
                        }
                    )
                
                current_group = world.get_group(group.id)
                if not current_group or not current_group.alive:
                    cancelled = True
                    cancel_reason = "GROUP_BATTLE_DEFEAT_DEATH"
                    break
                
                if winner and winner.id != group.id:
                    cancelled = True
                    cancel_reason = "GROUP_BATTLE_DEFEAT"
                    break
            
            old_tile = world.get_tile(current_x, current_y)
            if old_tile:
                old_tile.remove_group(group.id)
            
            current_x, current_y = next_x, next_y
            group.x = current_x
            group.y = current_y
            migration_path.append((current_x, current_y))
            
            new_tile = world.get_tile(current_x, current_y)
            if new_tile:
                new_tile.add_group(group.id)
            
            steps_completed = step
            
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="MIGRATE_STEP",
                details={
                    "step": step,
                    "completed": steps_completed,
                    "from": (old_tile.x, old_tile.y) if old_tile else (0, 0),
                    "to": (current_x, current_y)
                }
            )
        
        if has_trait(group, "Guardián de la Naturaleza") and steps_completed > 0:
            destroyed = destroy_structures_along_path(
                world, migration_path, group.id, logger, round_number, turn_index
            )
            if len(destroyed) > 0:
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="TRAIT_ACTION_USED",
                    details={
                        "action": "DESTROY_STRUCTURES",
                        "trait": "Guardián de la Naturaleza",
                        "structures_destroyed": len(destroyed),
                        "path_length": len(migration_path)
                    }
                )
        
        if not cancelled and steps_completed > 0:
            if StateType.EN_MARCHA not in group.estados:
                group.estados[StateType.EN_MARCHA] = 1
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="STATE_APPLIED",
                    details={
                        "state": "En Marcha",
                        "duration": 1,
                        "from_action": "MIGRATE_COMPLETED"
                    }
                )
            
            if StateType.VULNERABLE in group.estados and not has_trait(group, "Como una sombra"):
                del group.estados[StateType.VULNERABLE]
            
            final_tile = world.get_tile(group.x, group.y)
            final_is_water = final_tile and final_tile.terreno == TerrainType.AGUA
            if has_trait(group, "Anfibio") and is_on_water and not final_is_water:
                apply_surprise_on_exit_water(group, logger, round_number, turn_index)
            
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="MIGRATE_COMPLETED",
                details={
                    "distance_planned": distance_planned,
                    "distance_completed": steps_completed,
                    "start_position": (start_x, start_y),
                    "final_position": (current_x, current_y),
                    "combat_occurred": combat_triggered
                }
            )
        elif cancelled:
            if StateType.VULNERABLE in group.estados and not has_trait(group, "Como una sombra"):
                del group.estados[StateType.VULNERABLE]
            
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="MIGRATE_CANCELLED",
                details={
                    "distance_planned": distance_planned,
                    "distance_completed": steps_completed,
                    "stop_reason": cancel_reason,
                    "final_position": (current_x, current_y)
                }
            )
        
        group.last_action_was_grow = False
        return
    
    # ========================================================================
    # Acción WAIT
    # ========================================================================
    if action == "WAIT":
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group.id,
            event_type="ACCION",
            details={"action": action, "position": (group.x, group.y)}
        )
        group.last_action_was_grow = False
        return
    
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=group.id,
        event_type="ACCION",
        details={"action": action, "result": "NOT_IMPLEMENTED"}
    )
    group.last_action_was_grow = False


# ============================================================================
# APLICAR NACIMIENTOS
# ============================================================================

def apply_births(world: World, rng: random.Random, logger: Logger, round_number: int) -> None:
    """Aplica nacimientos cada 5 rondas (Regla 24)."""
    if round_number % 5 != 0:
        return
    
    logger.log_event(
        round_num=round_number,
        turn_index=-1,
        group_id=-1,
        event_type="BIRTHS_EVENT_START",
        details={"round": round_number}
    )
    
    all_groups = world.get_all_groups()
    races = set()
    for group in all_groups:
        if group.alive:
            races.add(group.raza)
    
    try:
        for settlement in world.get_all_settlements():
            if settlement.ruinas:
                continue
            if settlement.dueño_grupo_id is None and hasattr(settlement, 'raza') and settlement.raza:
                races.add(settlement.raza)
    except AttributeError:
        pass
    
    if not races:
        logger.log_event(
            round_num=round_number,
            turn_index=-1,
            group_id=-1,
            event_type="BIRTHS_EVENT_END",
            details={"total_births": 0, "reason": "no_races_found"}
        )
        return
    
    total_births_assigned = 0
    
    for race in races:
        eligible_entities = []
        
        for group in all_groups:
            if group.alive and group.raza == race:
                eligible_entities.append(("group", group))
        
        try:
            for settlement in world.get_all_settlements():
                if settlement.ruinas:
                    continue
                if settlement.dueño_grupo_id is None and hasattr(settlement, 'raza') and settlement.raza == race:
                    eligible_entities.append(("settlement", settlement))
        except AttributeError:
            pass
        
        if not eligible_entities:
            logger.log_event(
                round_num=round_number,
                turn_index=-1,
                group_id=-1,
                event_type="BIRTHS_RACE_DISTRIBUTION",
                details={
                    "race": race,
                    "total_births": 1000,
                    "eligible_entities": 0,
                    "lost_births": 1000,
                    "reason": "no_eligible_entities"
                }
            )
            continue
        
        num_entities = len(eligible_entities)
        allocations, lost = calculate_birth_distribution(num_entities, 1000)
        
        logger.log_event(
            round_num=round_number,
            turn_index=-1,
            group_id=-1,
            event_type="BIRTHS_RACE_DISTRIBUTION",
            details={
                "race": race,
                "total_births": 1000,
                "eligible_entities": num_entities,
                "allocations": allocations,
                "lost_births": lost
            }
        )
        
        for i, (entity_type, entity) in enumerate(eligible_entities):
            if i >= len(allocations):
                break
                
            base_amount = allocations[i]
            bonus_amount = 0
            
            if entity_type == "group":
                group = entity
                has_housing = has_housing_upgrade_for_group(group, world)
                bonus_amount = calculate_housing_bonus(base_amount, has_housing)
                total_amount = base_amount + bonus_amount
                
                old_population = group.poblacion
                group.poblacion += total_amount
                
                logger.log_event(
                    round_num=round_number,
                    turn_index=-1,
                    group_id=group.id,
                    event_type="BIRTHS_ASSIGNED_TO_GROUP",
                    details={
                        "race": race,
                        "base_amount": base_amount,
                        "bonus_amount": bonus_amount,
                        "total_amount": total_amount,
                        "population_before": old_population,
                        "population_after": group.poblacion,
                        "bonus_reason": "housing_upgrade" if has_housing else None
                    }
                )
                total_births_assigned += total_amount
                
            elif entity_type == "settlement":
                settlement = entity
                total_amount = base_amount
                
                all_groups_current = world.get_all_groups()
                next_group_id = max([g.id for g in all_groups_current] + [0]) + 1
                
                new_group = create_group_from_settlement(
                    settlement=settlement,
                    population=total_amount,
                    next_group_id=next_group_id,
                    current_round=round_number
                )
                
                world.add_group(new_group)
                settlement.dueño_grupo_id = new_group.id
                
                logger.log_event(
                    round_num=round_number,
                    turn_index=-1,
                    group_id=-1,
                    event_type="BIRTHS_ASSIGNED_TO_ORPHAN_SETTLEMENT",
                    details={
                        "race": race,
                        "settlement_id": settlement.id,
                        "settlement_position": (settlement.x, settlement.y),
                        "base_amount": base_amount,
                        "total_amount": total_amount,
                        "new_group_id": new_group.id
                    }
                )
                
                total_births_assigned += total_amount
    
    logger.log_event(
        round_num=round_number,
        turn_index=-1,
        group_id=-1,
        event_type="BIRTHS_EVENT_END",
        details={
            "round": round_number,
            "total_births_assigned": total_births_assigned
        }
    )


def _handle_group_death(world: World, group_id: int, logger: Logger, 
                        round_number: int, turn_index: int, cause: str) -> List[int]:
    """Maneja la muerte de un grupo: libera asentamientos y registra log."""
    orphaned_settlements = on_group_death_settlements(world, group_id, logger, round_number)
    
    if orphaned_settlements:
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_id,
            event_type="SETTLEMENTS_ORPHANED",
            details={
                "settlement_ids": orphaned_settlements,
                "cause": cause
            }
        )
    
    return orphaned_settlements


# ============================================================================
# ENGINE PRINCIPAL
# ============================================================================

class Engine:
    """
    Motor principal de la simulación.
    Gestiona el loop de rondas, orden de turnos fijo, y RNG reproducible.
    MÓDULO 15C: Integración de rasgos.
    """

    def __init__(self, world: World, rng: random.Random, logger: Logger):
        self.world = world
        self.rng = rng
        self.logger = logger
        self._turn_order: List[int] = []

    def _build_turn_order(self) -> None:
        groups = self.world.get_all_groups()
        groups_sorted = sorted(groups, key=lambda g: g.id)
        self._turn_order = [g.id for g in groups_sorted]

    def _decrement_states(self, group: Group, round_number: int) -> None:
        from models import StateType
        
        expired = []
        for state, turns_left in group.estados.items():
            # MÓDULO 15C: Guardián del Orden - inmune a Miedo
            if is_immune_to_fear_by_guardian(group) and state == StateType.MIEDO:
                self.logger.log_event(
                    round_num=round_number,
                    turn_index=-1,
                    group_id=group.id,
                    event_type="TRAIT_IMMUNITY_APPLIED",
                    details={
                        "trait": "Guardián del Orden",
                        "immune_to": "Miedo"
                    }
                )
                continue
            
            if turns_left <= 1:
                expired.append(state)
            else:
                group.estados[state] = turns_left - 1

        for state in expired:
            if state == StateType.DEBUFF_PODER:
                group._power_multiplier = 1.0
            
            del group.estados[state]
            self.logger.log_event(
                round_num=round_number,
                turn_index=-1,
                group_id=group.id,
                event_type="STATE_EXPIRED",
                details={
                    "state": state.value,
                    "group_id": group.id,
                    "position": (group.x, group.y)
                }
            )

    def _decrement_all_states_end_of_round(self, round_number: int) -> None:
        groups_to_remove = []
        
        for group in self.world.get_all_groups():
            self._decrement_states(group, round_number)
            if not group.alive:
                groups_to_remove.append(group)
        
        for group in groups_to_remove:
            _handle_group_death(
                self.world, group.id, self.logger, 
                round_number, -1,
                cause="state_expiration"
            )
            self.world.remove_group(group.id)

    def _reset_acted_flags(self) -> None:
        """Reinicia flags de acción al inicio de ronda."""
        for group in self.world.get_all_groups():
            group.acted_this_round = False
            if hasattr(group, '_trained_this_round'):
                group._trained_this_round = False
            
            # MÓDULO 15C: Reiniciar flags de rasgos
            reset_free_move_flag(group)

    def _resolve_tile_interactions(self, x: int, y: int, round_number: int, turn_index: int) -> None:
        resolve_tile_interactions(
            world=self.world,
            x=x,
            y=y,
            rng=self.rng,
            logger=self.logger,
            round_number=round_number,
            turn_index=turn_index
        )

    def _resolve_all_tile_interactions_end_of_round(self, round_number: int) -> None:
        tiles_with_groups = {}
        
        for group in self.world.get_all_groups():
            if not group.alive:
                continue
            key = (group.x, group.y)
            if key not in tiles_with_groups:
                tiles_with_groups[key] = []
            tiles_with_groups[key].append(group.id)
        
        for (x, y), group_ids in tiles_with_groups.items():
            if len(group_ids) > 1:
                self._resolve_tile_interactions(x, y, round_number, turn_index=-1)

    def _add_new_groups_to_turn_order(self) -> None:
        current_group_ids = set(self._turn_order)
        all_groups = self.world.get_all_groups()

        new_group_ids = [g.id for g in all_groups if g.id not in current_group_ids]
        if new_group_ids:
            new_group_ids.sort()
            self._turn_order.extend(new_group_ids)
            
            self.logger.log_event(
                round_num=0,
                turn_index=-1,
                group_id=-1,
                event_type="TURN_ORDER_UPDATED",
                details={"new_groups_added": new_group_ids, "new_order": self._turn_order.copy()}
            )

    def run_simulation(self, max_rounds: int) -> None:
        self._build_turn_order()
        
        self.logger.log_event(
            round_num=0,
            turn_index=-1,
            group_id=-1,
            event_type="INIT_TURN_ORDER",
            details={"initial_order": self._turn_order.copy()}
        )

        for round_num in range(1, max_rounds + 1):
            self._reset_acted_flags()
            
            self.logger.log_event(
                round_num=round_num,
                turn_index=-1,
                group_id=-1,
                event_type="INICIO_RONDA",
                details={"round": round_num}
            )

            # Decrementar efectos de tiles (congelado)
            self.world.decrement_tile_effects(round_num, self.logger)
            
            # Aplicar peligros
            apply_dangers(self.world, self.rng, self.logger, round_num)
            
            # Aplicar efectos de rasgos
            apply_trait_effects_start_of_round(self.world, self.rng, self.logger, round_num)
            
            # Aplicar penalizaciones de congelado
            _apply_freeze_penalties(self.world, self.logger, round_num)
            
            # F1: Aplicar efectos de Sylvan (Uno con la vida) en radio de influencia
            _apply_sylvan_radius_effects(self.world, self.logger, round_num)

            # MÓDULO 15C: Verificar y procesar movimiento gratuito para grupos
            for group in self.world.get_all_groups():
                if has_free_move_available(group):
                    self.logger.log_event(
                        round_num=round_num,
                        turn_index=-1,
                        group_id=group.id,
                        event_type="TRAIT_FREE_MOVE_GRANTED",
                        details={
                            "trait": "La caza helada",
                            "status": "pending"
                        }
                    )

            for turn_idx, group_id in enumerate(self._turn_order):
                group = self.world.get_group(group_id)

                if group is None or not group.alive:
                    continue
                
                if group.acted_this_round:
                    self.logger.log_event(
                        round_num=round_num,
                        turn_index=turn_idx,
                        group_id=group.id,
                        event_type="TURNO_SALTADO",
                        details={"reason": "already_acted_this_round"}
                    )
                    continue

                self.logger.log_event(
                    round_num=round_num,
                    turn_index=turn_idx,
                    group_id=group.id,
                    event_type="INICIO_TURNO",
                    details={
                        "poblacion": group.poblacion,
                        "posicion": (group.x, group.y),
                        "estados_activos": [s.value for s in group.estados.keys()]
                    }
                )

                group.acted_this_round = True
                action = choose_action(group, self.world, self.rng)

                execute_action(
                    group=group,
                    action=action,
                    world=self.world,
                    rng=self.rng,
                    logger=self.logger,
                    round_number=round_num,
                    turn_index=turn_idx
                )

            self._resolve_all_tile_interactions_end_of_round(round_num)
            self._decrement_all_states_end_of_round(round_num)

            if round_num % 5 == 0:
                apply_births(self.world, self.rng, self.logger, round_num)

            self._add_new_groups_to_turn_order()

            self.logger.log_event(
                round_num=round_num,
                turn_index=-1,
                group_id=-1,
                event_type="FIN_RONDA",
                details={
                    "round": round_num,
                    "total_groups": self.world.group_count,
                    "total_population": sum(g.poblacion for g in self.world.get_all_groups()),
                    "turn_order_length": len(self._turn_order)
                }
            )

        self.logger.log_event(
            round_num=max_rounds,
            turn_index=-1,
            group_id=-1,
            event_type="FIN_SIMULACION",
            details={
                "total_rounds": max_rounds,
                "final_groups": self.world.group_count,
                "final_population": sum(g.poblacion for g in self.world.get_all_groups())
            }
        )