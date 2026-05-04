"""
combat_resolver.py - Orquestación de combates entre grupos.
Aplica cambios de estado, maneja rebotes, y registra logs.
MÓDULO 14: Integra overrides de Duros, Precisos, Asediadores y De piedra.
MÓDULO 15A: Integra Manada, Runa de guerra, Como las leyendas,
            El miedo no está en el músculo, El más débil, Reflejos Felinos.
MÓDULO 15B: Integra Metrópolis (Entorpecido al atacante)
MÓDULO 15C: Integra nuevos rasgos (Caza helada, Acosador, Buscapleitos, 
            Guardián del Orden, Como una joya, Como una sombra)
"""

import random
import math
from typing import Tuple, Optional, List, Dict, Any

from models import Group, StateType, TerrainType, Settlement
from world import World
from logger import Logger
from rules import (
    calculate_participants, calculate_losses, calculate_rebound_distance,
    determine_winner, get_opposite_direction, calculate_rebound_step,
    CombatResult, ReboundStepResult,
    calculate_siege_participants,
    calculate_siege_losses_when_losing,
    calculate_combat_losses,
    get_combat_participation_percentage,
    has_trait,
    is_immune_to_combat_state,
    # MÓDULO 15A
    calculate_pack_bonus,
    get_power_multiplier,
    apply_fear_on_victory,
    apply_fear_during_combat,
    apply_war_rune_debuff,
    calculate_goblin_losses,
    set_attacked_flag,
    was_attacked_last_turn,
    # Ciudad
    calculate_city_battle,
    can_attack_from_position,
    is_water_tile,
    calculate_new_city_points_after_degradation,
    calculate_disabled_upgrades,
    on_group_death_settlements,
    # MÓDULO 15B
    apply_entorpecido_when_attacked,  # Metrópolis - Entorpecido al atacante
    # MÓDULO 15C
    apply_entorpecido_on_attack,
    record_attack_target,
    can_attack_same_target,
    apply_acoser_effects,
    calculate_hostility_bonus,
    get_guardian_power_multiplier,
    is_immune_to_fear_by_guardian,
    apply_entorpecido_when_attacked_by_dwarf,
    set_free_move_available,
    apply_surprise_when_attacked_during_marching,  # Como una sombra - Sorpresa al ser atacado en En Marcha
    get_reputation,
    get_freeze_power_penalty,
    get_valid_directions
)


# ============================================================================
# Funciones auxiliares (definidas UNA SOLA vez)
# ============================================================================

def is_water_with_group(world: World, x: int, y: int) -> bool:
    """Verifica si una casilla es AGUA y tiene al menos un grupo."""
    tile = world.get_tile(x, y)
    if not tile or tile.terreno != TerrainType.AGUA:
        return False
    
    groups_on_tile = world.get_groups_on_tile(x, y)
    return len(groups_on_tile) > 0


def is_city_occupied_by_enemy(world: World, x: int, y: int, group_id: int) -> bool:
    """Verifica si una casilla tiene ciudad enemiga (Regla 5.6)."""
    tile = world.get_tile(x, y)
    if not tile or not tile.has_settlement:
        return False
    
    settlement = world.get_settlement(tile.settlement_id)
    if not settlement or settlement.ruinas:
        return False
    
    if settlement.dueño_grupo_id == group_id:
        return False
    
    return True


# ============================================================================
# Funciones de rebote
# ============================================================================

def apply_rebound(group: Group, distance: int, battle_direction: str,
                  world: World, rng: random.Random,
                  logger: Logger, round_number: int, turn_index: int) -> bool:
    """
    Aplica rebote al grupo perdedor. MODIFICA ESTADO y LOGUEA.
    
    Returns:
        True si el rebote se completó, False si se detuvo antes
    """
    rebound_direction = get_opposite_direction(battle_direction)
    current_x, current_y = group.x, group.y
    
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=group.id,
        event_type="REBOUND_START",
        details={
            "from_position": f"({current_x},{current_y})",
            "target_distance": distance,
            "initial_direction": rebound_direction
        }
    )
    
    steps_taken = 0
    
    for step in range(distance):
        # Calcular siguiente paso (función pura)
        step_result = calculate_rebound_step(
            current_x, current_y, rebound_direction,
            world.width, world.height, rng
        )
        
        if not step_result.success:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="REBOUND_END",
                details={
                    "status": "stopped",
                    "reason": step_result.block_reason,
                    "steps_taken": step,
                    "final_position": f"({current_x},{current_y})"
                }
            )
            return False
        
        new_x, new_y = step_result.new_x, step_result.new_y
        rebound_direction = step_result.new_direction
        
        # Verificar agua con grupo
        if is_water_with_group(world, new_x, new_y):
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="REBOUND_END",
                details={
                    "status": "stopped_water_occupied",
                    "steps_taken": step,
                    "final_position": f"({current_x},{current_y})",
                    "blocked_position": f"({new_x},{new_y})"
                }
            )
            return True
        
        # Verificar ciudad enemiga
        if is_city_occupied_by_enemy(world, new_x, new_y, group.id):
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="REBOUND_END",
                details={
                    "status": "stopped_enemy_city",
                    "steps_taken": step,
                    "final_position": f"({current_x},{current_y})",
                    "blocked_position": f"({new_x},{new_y})"
                }
            )
            return True
        
        # Mover grupo
        old_x, old_y = current_x, current_y
        world.move_group_to(group.id, new_x, new_y)
        current_x, current_y = new_x, new_y
        steps_taken = step + 1
        
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group.id,
            event_type="REBOUND_STEP",
            details={
                "step": step + 1,
                "direction": rebound_direction,
                "edge_bounce": step_result.edge_bounce,
                "from": f"({old_x},{old_y})",
                "to": f"({current_x},{current_y})"
            }
        )
        
        # Verificar encuentro con otros grupos (R14.6)
        other_groups = [g for g in world.get_groups_on_tile(current_x, current_y) 
                        if g.id != group.id]
        
        if other_groups:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="REBOUND_STEP",
                details={
                    "step": step + 1,
                    "encountered_groups": [g.id for g in other_groups],
                    "chain_reaction": True
                }
            )
    
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=group.id,
        event_type="REBOUND_END",
        details={
            "status": "completed",
            "steps_taken": steps_taken,
            "final_position": f"({current_x},{current_y})"
        }
    )
    
    return True


# ============================================================================
# Resolución de combate grupo vs grupo
# ============================================================================

def resolve_combat(group_a: Group, group_b: Group,
                   world: World, rng: random.Random,
                   logger: Logger, round_number: int, turn_index: int) -> Tuple[Optional[Group], Optional[Group]]:
    """
    Resuelve un combate entre dos grupos. MODIFICA ESTADO y LOGUEA.
    MÓDULO 14: Integra overrides de Duros, Precisos y De piedra.
    MÓDULO 15A: Integra Manada, Runa de guerra, Como las leyendas,
                El miedo no está en el músculo, El más débil.
    MÓDULO 15B: Integra Metrópolis (Entorpecido al atacante)
    MÓDULO 15C: Integra Caza helada, Acosador, Buscapleitos, Guardián del Orden.
    """
    
    # Verificar si puede atacar al mismo objetivo (Caza helada)
    can_attack_a, reason_a = can_attack_same_target(group_a, group_b.id)
    can_attack_b, reason_b = can_attack_same_target(group_b, group_a.id)
    
    if not can_attack_a:
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_a.id,
            event_type="TRAIT_ATTACK_BLOCKED",
            details={
                "trait": "La caza helada",
                "target_id": group_b.id,
                "reason": reason_a
            }
        )
        return None, None
    
    if not can_attack_b:
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_b.id,
            event_type="TRAIT_ATTACK_BLOCKED",
            details={
                "trait": "La caza helada",
                "target_id": group_a.id,
                "reason": reason_b
            }
        )
        return None, None
    
    # Marcar que ambos grupos fueron atacados (para Reflejos Felinos)
    set_attacked_flag(group_a, True)
    set_attacked_flag(group_b, True)
    
    # MÓDULO 15A: Como una sombra - si el defensor está en En Marcha, aplica Sorpresa al atacante
    if StateType.EN_MARCHA in group_b.estados:
        apply_surprise_when_attacked_during_marching(group_b, group_a, logger, round_number, turn_index)
    if StateType.EN_MARCHA in group_a.estados:
        apply_surprise_when_attacked_during_marching(group_a, group_b, logger, round_number, turn_index)
    
    # Verificar inmunidades de De piedra antes de aplicar estados de combate
    if is_immune_to_combat_state(group_a, "Sorpresa"):
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_a.id,
            event_type="TRAIT_IMMUNITY_APPLIED",
            details={
                "trait": "De piedra",
                "state": "Sorpresa",
                "regla_afectada": "combate_state_immunity"
            }
        )
    
    if is_immune_to_combat_state(group_b, "Sorpresa"):
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_b.id,
            event_type="TRAIT_IMMUNITY_APPLIED",
            details={
                "trait": "De piedra",
                "state": "Sorpresa",
                "regla_afectada": "combate_state_immunity"
            }
        )
    
    # Calcular poder con bonuses (Manada)
    power_a = group_a.poder_total
    power_b = group_b.poder_total
    
    pack_bonus_a = calculate_pack_bonus(group_a, world)
    pack_bonus_b = calculate_pack_bonus(group_b, world)
    
    if pack_bonus_a > 0:
        power_a = power_a * (1 + pack_bonus_a / 100.0)
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_a.id,
            event_type="TRAIT_POWER_MODIFIER_APPLIED",
            details={
                "trait": "Manada",
                "bonus_percent": pack_bonus_a,
                "original_power": group_a.poder_total,
                "modified_power": power_a
            }
        )
    
    if pack_bonus_b > 0:
        power_b = power_b * (1 + pack_bonus_b / 100.0)
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_b.id,
            event_type="TRAIT_POWER_MODIFIER_APPLIED",
            details={
                "trait": "Manada",
                "bonus_percent": pack_bonus_b,
                "original_power": group_b.poder_total,
                "modified_power": power_b
            }
        )
    
    # MÓDULO 15C: Buscapleitos - bono de poder por hostilidad
    buscapleitos_bonus_a = calculate_hostility_bonus(group_a, group_b)
    buscapleitos_bonus_b = calculate_hostility_bonus(group_b, group_a)
    
    if buscapleitos_bonus_a > 0:
        power_a = power_a * (1 + buscapleitos_bonus_a / 100.0)
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_a.id,
            event_type="TRAIT_POWER_MODIFIER_APPLIED",
            details={
                "trait": "Buscapleitos",
                "bonus_percent": buscapleitos_bonus_a,
                "modified_power": power_a,
                "opponent_id": group_b.id,
                "reputation": get_reputation(group_a, group_b.id)
            }
        )
    
    if buscapleitos_bonus_b > 0:
        power_b = power_b * (1 + buscapleitos_bonus_b / 100.0)
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_b.id,
            event_type="TRAIT_POWER_MODIFIER_APPLIED",
            details={
                "trait": "Buscapleitos",
                "bonus_percent": buscapleitos_bonus_b,
                "modified_power": power_b,
                "opponent_id": group_a.id,
                "reputation": get_reputation(group_b, group_a.id)
            }
        )
    
    # MÓDULO 15C: Guardián del Orden - bono de poder
    guardian_bonus_a = get_guardian_power_multiplier(group_a, group_b, is_attacking=True)
    guardian_bonus_b = get_guardian_power_multiplier(group_b, group_a, is_attacking=False)
    
    if guardian_bonus_a > 1.0:
        power_a = power_a * guardian_bonus_a
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_a.id,
            event_type="TRAIT_POWER_MODIFIER_APPLIED",
            details={
                "trait": "Guardián del Orden",
                "bonus_percent": (guardian_bonus_a - 1.0) * 100,
                "modified_power": power_a,
                "opponent_id": group_b.id,
                "reputation": get_reputation(group_a, group_b.id),
                "role": "attacker"
            }
        )
    
    if guardian_bonus_b > 1.0:
        power_b = power_b * guardian_bonus_b
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_b.id,
            event_type="TRAIT_POWER_MODIFIER_APPLIED",
            details={
                "trait": "Guardián del Orden",
                "bonus_percent": (guardian_bonus_b - 1.0) * 100,
                "modified_power": power_b,
                "opponent_id": group_a.id,
                "reputation": get_reputation(group_b, group_a.id),
                "role": "defender"
            }
        )
    
    # Aplicar multiplicadores por debuffs (Runa de guerra)
    power_a *= get_power_multiplier(group_a)
    power_b *= get_power_multiplier(group_b)
    
    # Aplicar multiplicador por congelado
    freeze_a = get_freeze_power_penalty(world, group_a.x, group_a.y)
    freeze_b = get_freeze_power_penalty(world, group_b.x, group_b.y)
    
    power_a = power_a * freeze_a
    power_b = power_b * freeze_b
    
    if freeze_a < 1.0:
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_a.id,
            event_type="TRAIT_EFFECT_APPLIED",
            details={"trait": "Congelado", "power_multiplier": freeze_a}
        )
    
    if freeze_b < 1.0:
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_b.id,
            event_type="TRAIT_EFFECT_APPLIED",
            details={"trait": "Congelado", "power_multiplier": freeze_b}
        )
    
    # Verificar estados para penalización
    a_has_penalty = (StateType.VULNERABLE in group_a.estados or 
                     StateType.EN_MARCHA in group_a.estados)
    b_has_penalty = (StateType.VULNERABLE in group_b.estados or 
                     StateType.EN_MARCHA in group_b.estados)
    
    # Calcular participantes con overrides por estado
    a_participants = max(1, math.ceil(group_a.poblacion * 
                                      get_combat_participation_percentage(group_a, a_has_penalty)))
    b_participants = max(1, math.ceil(group_b.poblacion * 
                                      get_combat_participation_percentage(group_b, b_has_penalty)))
    
    # Log inicio batalla
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=group_a.id,
        event_type="BATTLE_START",
        details={
            "attacker_id": group_a.id,
            "defender_id": group_b.id,
            "position": f"({group_a.x},{group_a.y})",
            "attacker_population": group_a.poblacion,
            "defender_population": group_b.poblacion,
            "attacker_participants": a_participants,
            "defender_participants": b_participants,
            "attacker_power": power_a,
            "defender_power": power_b,
            "pack_bonus_a": pack_bonus_a,
            "pack_bonus_b": pack_bonus_b
        }
    )
    
    # Verificar mínimo de participantes
    if a_participants == 0 or b_participants == 0:
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=-1,
            event_type="BATTLE_ABORTED",
            details={"reason": "no_participants"}
        )
        return None, None
    
    # Aplicar Miedo durante combate (El miedo no está en el músculo)
    apply_fear_during_combat(group_a, group_b, logger, round_number, turn_index)
    
    # MÓDULO 15C: Caza helada - aplicar Entorpecido al atacar
    apply_entorpecido_on_attack(group_a, group_b, logger, round_number, turn_index)
    
    # MÓDULO 15C: Como una joya - aplicar Entorpecido al atacante si es atacado
    apply_entorpecido_when_attacked_by_dwarf(group_b, group_a, logger, round_number, turn_index)
    
    # MÓDULO 15B: Metrópolis - aplicar Entorpecido al atacante
    apply_entorpecido_when_attacked(group_a, group_b, world, logger, round_number, turn_index)
    apply_entorpecido_when_attacked(group_b, group_a, world, logger, round_number, turn_index)
    
    # Registrar objetivo atacado para Caza helada
    record_attack_target(group_a, group_b.id)
    
    # Verificar inmunidad a Miedo por Guardián del Orden
    if is_immune_to_fear_by_guardian(group_a):
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_a.id,
            event_type="TRAIT_IMMUNITY_APPLIED",
            details={
                "trait": "Guardián del Orden",
                "state": "Miedo",
                "regla_afectada": "fear_immunity"
            }
        )
    
    if is_immune_to_fear_by_guardian(group_b):
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group_b.id,
            event_type="TRAIT_IMMUNITY_APPLIED",
            details={
                "trait": "Guardián del Orden",
                "state": "Miedo",
                "regla_afectada": "fear_immunity"
            }
        )
    
    # Determinar ganador (función pura)
    winner_id, loser_id, winner_power, loser_power = determine_winner(
        power_a, power_b, group_b.id, group_a.id
    )
    
    winner = group_a if winner_id == group_a.id else group_b
    loser = group_b if loser_id == group_b.id else group_a
    
    # Log resultado
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=winner.id,
        event_type="BATTLE_RESULT",
        details={
            "winner_id": winner.id,
            "loser_id": loser.id,
            "winner_power": winner_power,
            "loser_power": loser_power
        }
    )
    
    # Aplicar Miedo al oponente si ganador tiene Como las leyendas
    apply_fear_on_victory(winner, loser, logger, round_number, turn_index)
    
    # Aplicar Runa de guerra: si perdedor tiene el rasgo, aplica debuff al ganador
    apply_war_rune_debuff(winner, loser, logger, round_number, turn_index)
    
    # MÓDULO 15C: Acosador - aplicar Agotado+Vulnerable post combate
    apply_acoser_effects(winner, loser, logger, round_number, turn_index)
    
    # MÓDULO 15C: Caza helada - habilitar movimiento gratuito para el ganador
    if has_trait(winner, "La caza helada"):
        set_free_move_available(winner, True)
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=winner.id,
            event_type="TRAIT_FREE_MOVE_GRANTED",
            details={
                "trait": "La caza helada",
                "reason": "after_attack_victory"
            }
        )
    
    # Calcular participantes del perdedor para bajas
    loser_has_penalty = (StateType.VULNERABLE in loser.estados or 
                         StateType.EN_MARCHA in loser.estados)
    loser_participants = max(1, math.ceil(loser.poblacion * 
                                          get_combat_participation_percentage(loser, loser_has_penalty)))
    
    # MÓDULO 14/15A: Calcular bajas con overrides
    if has_trait(loser, "El más débil"):
        losses = calculate_goblin_losses(loser_participants)
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=loser.id,
            event_type="TRAIT_OVERRIDE_APPLIED",
            details={
                "trait": "El más débil",
                "regla_afectada": "calcular_bajas_en_combate",
                "original_value": "10/30/50%",
                "new_value": "50%"
            }
        )
    else:
        losses = calculate_combat_losses(
            loser_participants,
            winner,
            loser,
            rng,
            is_winner=True
        )
    
    actual_losses = min(losses, loser.poblacion)
    
    # Log si se aplicó override de Precisos
    if has_trait(winner, "Precisos") and not has_trait(loser, "El más débil"):
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=winner.id,
            event_type="TRAIT_OVERRIDE_APPLIED",
            details={
                "trait": "Precisos",
                "regla_afectada": "calcular_bajas_en_combate",
                "original_value": "10/30/50%",
                "new_value": "50%"
            }
        )
    
    # Log si se aplicó override de Duros
    if has_trait(loser, "Duros") and not has_trait(loser, "El más débil"):
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=loser.id,
            event_type="TRAIT_OVERRIDE_APPLIED",
            details={
                "trait": "Duros",
                "regla_afectada": "calcular_bajas_recibidas",
                "original_value": "10/30/50%",
                "new_value": "10%"
            }
        )
    
    # APLICAR BAJAS (modifica estado)
    loser.poblacion -= actual_losses
    
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=loser.id,
        event_type="BATTLE_LOSSES",
        details={
            "losses_absolute": actual_losses,
            "losses_percentage": (actual_losses / loser_participants) * 100 if loser_participants > 0 else 0,
            "remaining_population": loser.poblacion
        }
    )
    
    # Verificar muerte del grupo
    if loser.poblacion <= 0:
        # Manejar asentamientos huérfanos ANTES de remover el grupo
        orphaned_settlements = on_group_death_settlements(world, loser.id, logger, round_number)
        
        if orphaned_settlements:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=loser.id,
                event_type="SETTLEMENTS_ORPHANED",
                details={
                    "settlement_ids": orphaned_settlements,
                    "cause": "battle_losses",
                    "killed_by": winner.id
                }
            )
        
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=loser.id,
            event_type="GROUP_DEATH",
            details={
                "position": f"({loser.x},{loser.y})",
                "cause": "battle_losses",
                "killed_by": winner.id
            }
        )
        world.remove_group(loser.id)
        return winner, None
    
    # Calcular rebote (función pura)
    rebound_distance = calculate_rebound_distance(rng)
    
    # Determinar dirección de batalla
    if group_a.x == group_b.x and group_a.y == group_b.y:
        # Misma casilla: dirección aleatoria válida
        valid_dirs = get_valid_directions(loser.x, loser.y, world.width, world.height)
        battle_direction = rng.choice(valid_dirs) if valid_dirs else 'N'
    else:
        dx = loser.x - winner.x
        dy = loser.y - winner.y
        if abs(dx) > abs(dy):
            battle_direction = 'E' if dx > 0 else 'O'
        else:
            battle_direction = 'S' if dy > 0 else 'N'
    
    # APLICAR REBOTE (modifica estado)
    apply_rebound(loser, rebound_distance, battle_direction, world, rng,
                  logger, round_number, turn_index)
    
    return winner, loser


# ============================================================================
# Resolución de combate stack vs stack
# ============================================================================

def resolve_stack_combat(stack_a: List[Group], stack_b: List[Group],
                         world: World, rng: random.Random,
                         logger: Logger, round_number: int, turn_index: int) -> Tuple[List[Group], List[Group]]:
    """
    Resuelve combate entre dos stacks de grupos (mismo origen).
    MÓDULO 15A: Añade overrides de rasgos (Goblin, Miedo, Runa de guerra).
    MÓDULO 15B: Integra Metrópolis (Entorpecido al atacante)
    MÓDULO 15C: Integra nuevos rasgos (Caza helada, Acosador, Buscapleitos, etc.)
    
    Returns:
        (winner_stack, loser_stack) después de aplicar pérdidas
    """
    # Calcular fuerza total del stack
    a_total_pop = sum(g.poblacion for g in stack_a)
    b_total_pop = sum(g.poblacion for g in stack_b)
    
    a_avg_power = sum(g.poder_promedio * g.poblacion for g in stack_a) / a_total_pop if a_total_pop > 0 else 0
    b_avg_power = sum(g.poder_promedio * g.poblacion for g in stack_b) / b_total_pop if b_total_pop > 0 else 0
    
    # Verificar penalizaciones (si algún grupo en el stack tiene estado)
    a_has_penalty = any(StateType.VULNERABLE in g.estados or StateType.EN_MARCHA in g.estados for g in stack_a)
    b_has_penalty = any(StateType.VULNERABLE in g.estados or StateType.EN_MARCHA in g.estados for g in stack_b)
    
    a_participants = calculate_participants(a_total_pop, a_has_penalty)
    b_participants = calculate_participants(b_total_pop, b_has_penalty)
    
    a_power = a_avg_power * a_participants
    b_power = b_avg_power * b_participants
    
    # ========================================================================
    # MÓDULO 15A/15B/15C: Overrides de rasgos en combate de stacks
    # ========================================================================
    
    # Usar grupos representantes de cada stack
    rep_a = stack_a[0] if stack_a else None
    rep_b = stack_b[0] if stack_b else None
    
    if rep_a and rep_b:
        # Aplicar Miedo durante combate (El miedo no está en el músculo)
        apply_fear_during_combat(rep_a, rep_b, logger, round_number, turn_index)
        
        # MÓDULO 15A: Como una sombra - aplicar Sorpresa si están en En Marcha
        if StateType.EN_MARCHA in rep_b.estados:
            apply_surprise_when_attacked_during_marching(rep_b, rep_a, logger, round_number, turn_index)
        if StateType.EN_MARCHA in rep_a.estados:
            apply_surprise_when_attacked_during_marching(rep_a, rep_b, logger, round_number, turn_index)
        
        # MÓDULO 15C: Buscapleitos - aplicar bono a representantes
        buscapleitos_bonus_a = calculate_hostility_bonus(rep_a, rep_b)
        buscapleitos_bonus_b = calculate_hostility_bonus(rep_b, rep_a)
        
        if buscapleitos_bonus_a > 0:
            a_power = a_power * (1 + buscapleitos_bonus_a / 100.0)
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=rep_a.id,
                event_type="TRAIT_POWER_MODIFIER_APPLIED",
                details={
                    "trait": "Buscapleitos",
                    "bonus_percent": buscapleitos_bonus_a,
                    "modified_power": a_power,
                    "opponent_id": rep_b.id
                }
            )
        
        if buscapleitos_bonus_b > 0:
            b_power = b_power * (1 + buscapleitos_bonus_b / 100.0)
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=rep_b.id,
                event_type="TRAIT_POWER_MODIFIER_APPLIED",
                details={
                    "trait": "Buscapleitos",
                    "bonus_percent": buscapleitos_bonus_b,
                    "modified_power": b_power,
                    "opponent_id": rep_a.id
                }
            )
        
        # MÓDULO 15C: Aplicar efectos de combate a TODOS los pares de grupos entre stacks
        for group_a in stack_a:
            for group_b in stack_b:
                # Caza helada - aplicar Entorpecido
                apply_entorpecido_on_attack(group_a, group_b, logger, round_number, turn_index)
                
                # Como una joya - aplicar Entorpecido al atacante si es atacado
                apply_entorpecido_when_attacked_by_dwarf(group_b, group_a, logger, round_number, turn_index)
                
                # MÓDULO 15B: Metrópolis - aplicar Entorpecido al atacante
                apply_entorpecido_when_attacked(group_a, group_b, world, logger, round_number, turn_index)
                apply_entorpecido_when_attacked(group_b, group_a, world, logger, round_number, turn_index)
                
                # Registrar objetivo atacado
                record_attack_target(group_a, group_b.id)
        
        # Aplicar multiplicador por congelado
        freeze_a = get_freeze_power_penalty(world, rep_a.x, rep_a.y)
        freeze_b = get_freeze_power_penalty(world, rep_b.x, rep_b.y)
        a_power = a_power * freeze_a
        b_power = b_power * freeze_b
    
    # Determinar ganador
    if a_power > b_power:
        winner_stack, loser_stack = stack_a, stack_b
    elif b_power > a_power:
        winner_stack, loser_stack = stack_b, stack_a
    else:
        # Empate: gana el que tiene más población
        winner_stack = stack_a if a_total_pop >= b_total_pop else stack_b
        loser_stack = stack_b if winner_stack == stack_a else stack_a
    
    # ========================================================================
    # Aplicar efectos post-combate a TODO el stack ganador y perdedor
    # ========================================================================
    
    for winner_group in winner_stack:
        for loser_group in loser_stack:
            # Aplicar Miedo al oponente si ganador tiene Como las leyendas
            apply_fear_on_victory(winner_group, loser_group, logger, round_number, turn_index)
            
            # Aplicar Runa de guerra: si perdedor tiene el rasgo, aplica debuff al ganador
            apply_war_rune_debuff(winner_group, loser_group, logger, round_number, turn_index)
            
            # MÓDULO 15C: Acosador - aplicar Agotado+Vulnerable post combate
            apply_acoser_effects(winner_group, loser_group, logger, round_number, turn_index)
    
    # MÓDULO 15C: Caza helada - habilitar movimiento gratuito para TODOS los grupos del stack ganador
    for winner_group in winner_stack:
        if has_trait(winner_group, "La caza helada"):
            set_free_move_available(winner_group, True)
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=winner_group.id,
                event_type="TRAIT_FREE_MOVE_GRANTED",
                details={
                    "trait": "La caza helada",
                    "reason": "after_stack_attack_victory"
                }
            )
    
    # Aplicar pérdidas al stack perdedor
    loser_total_pop = sum(g.poblacion for g in loser_stack)
    loser_participants = calculate_participants(loser_total_pop,
        any(StateType.VULNERABLE in g.estados or StateType.EN_MARCHA in g.estados for g in loser_stack))
    
    # Calcular pérdidas con overrides (El más débil / Goblin)
    total_losses = 0
    has_goblin = any(has_trait(g, "El más débil") for g in loser_stack)
    loser_rep = loser_stack[0] if loser_stack else None
    
    if has_goblin:
        total_losses = calculate_goblin_losses(loser_participants)
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=loser_rep.id if loser_rep else -1,
            event_type="TRAIT_OVERRIDE_APPLIED",
            details={
                "trait": "El más débil",
                "regla_afectada": "calcular_bajas_en_combate_stack",
                "original_value": "10/30/50%",
                "new_value": "50%"
            }
        )
    else:
        total_losses = calculate_losses(loser_participants, rng)
    
    remaining_losses = min(total_losses, loser_total_pop)
    
    # Distribuir pérdidas proporcionalmente
    for group in loser_stack:
        if remaining_losses <= 0:
            break
        group_loss = min(remaining_losses, group.poblacion)
        group.poblacion -= group_loss
        remaining_losses -= group_loss
        
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=group.id,
            event_type="BATTLE_LOSSES",
            details={
                "losses_absolute": group_loss,
                "remaining_population": group.poblacion
            }
        )
        
        if group.poblacion <= 0:
            # Manejar asentamientos huérfanos ANTES de remover el grupo
            orphaned_settlements = on_group_death_settlements(world, group.id, logger, round_number)
            
            if orphaned_settlements:
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=group.id,
                    event_type="SETTLEMENTS_ORPHANED",
                    details={
                        "settlement_ids": orphaned_settlements,
                        "cause": "stack_battle_losses"
                    }
                )
            
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=group.id,
                event_type="GROUP_DEATH",
                details={
                    "position": f"({group.x},{group.y})",
                    "cause": "stack_battle_losses"
                }
            )
            world.remove_group(group.id)
    
    # Filtrar grupos muertos
    winner_stack = [g for g in winner_stack if g.poblacion > 0]
    loser_stack = [g for g in loser_stack if g.poblacion > 0]
    
    # Rebote del stack perdedor (si queda alguno)
    if loser_stack:
        first_loser = loser_stack[0]
        valid_dirs = get_valid_directions(first_loser.x, first_loser.y, world.width, world.height)
        if valid_dirs:
            battle_direction = rng.choice(valid_dirs)
            rebound_distance = calculate_rebound_distance(rng)
            
            for group in loser_stack:
                if group.poblacion > 0:
                    apply_rebound(group, rebound_distance, battle_direction,
                                world, rng, logger, round_number, turn_index)
    
    return winner_stack, loser_stack


# ============================================================================
# Orquestación de combate Grupo vs Ciudad
# ============================================================================

# Almacenamiento de bonificaciones de ataque por ciudad
_city_attack_bonuses: Dict[int, Dict[int, int]] = {}


def register_city_attack_bonus(attacker_id: int, settlement_id: int) -> None:
    """Registra un ataque de un grupo contra una ciudad para acumular bonus."""
    if attacker_id not in _city_attack_bonuses:
        _city_attack_bonuses[attacker_id] = {}
    
    bonus_dict = _city_attack_bonuses[attacker_id]
    current_bonus = bonus_dict.get(settlement_id, 0)
    
    if current_bonus < 4:
        bonus_dict[settlement_id] = current_bonus + 1


def get_city_attack_bonus(attacker_id: int, settlement_id: int) -> int:
    """Obtiene el porcentaje de bonus acumulado para un atacante contra una ciudad."""
    if attacker_id in _city_attack_bonuses:
        bonus_count = _city_attack_bonuses[attacker_id].get(settlement_id, 0)
        return bonus_count * 10
    return 0


def clear_city_attack_bonus(attacker_id: int, settlement_id: int = None) -> None:
    """Limpia el bonus de un atacante."""
    if attacker_id in _city_attack_bonuses:
        if settlement_id is None:
            del _city_attack_bonuses[attacker_id]
        else:
            _city_attack_bonuses[attacker_id].pop(settlement_id, None)
            if not _city_attack_bonuses[attacker_id]:
                del _city_attack_bonuses[attacker_id]


def _apply_city_destruction_move(world: World, attacker: Group, settlement: Settlement,
                                  logger: Logger, round_number: int, turn_index: int) -> None:
    """Aplica movimiento obligatorio del atacante a la casilla de ciudad destruida."""
    old_tile = world.get_tile(attacker.x, attacker.y)
    if old_tile:
        old_tile.remove_group(attacker.id)
    
    old_x, old_y = attacker.x, attacker.y
    attacker.x = settlement.x
    attacker.y = settlement.y
    
    new_tile = world.get_tile(settlement.x, settlement.y)
    if new_tile:
        new_tile.add_group(attacker.id)
    
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=attacker.id,
        event_type="GROUP_MOVED_INTO_RUINS",
        details={
            "group_id": attacker.id,
            "settlement_id": settlement.id,
            "from": f"({old_x},{old_y})",
            "to": f"({settlement.x},{settlement.y})"
        }
    )


def _apply_city_rebound(world: World, attacker: Group, settlement: Settlement,
                         rng: random.Random, logger: Logger, 
                         round_number: int, turn_index: int) -> None:
    """Aplica rebote de 1 casilla al atacante después de victoria."""
    dx = attacker.x - settlement.x
    dy = attacker.y - settlement.y
    
    if dx > 0:
        rebound_dir = 'E'
    elif dx < 0:
        rebound_dir = 'O'
    elif dy > 0:
        rebound_dir = 'S'
    elif dy < 0:
        rebound_dir = 'N'
    else:
        valid_dirs = get_valid_directions(attacker.x, attacker.y, world.width, world.height)
        rebound_dir = rng.choice(valid_dirs) if valid_dirs else 'N'
    
    apply_rebound(attacker, 1, rebound_dir, world, rng, logger, round_number, turn_index)


def _apply_attacker_losses(attacker: Group, losses: int, logger: Logger,
                            round_number: int, turn_index: int) -> None:
    """Aplica pérdidas al atacante cuando pierde."""
    old_population = attacker.poblacion
    attacker.poblacion = max(0, attacker.poblacion - losses)
    
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=attacker.id,
        event_type="CITY_BATTLE_LOSSES",
        details={
            "attacker_id": attacker.id,
            "losses": losses,
            "old_population": old_population,
            "new_population": attacker.poblacion
        }
    )


def _disable_city_upgrades(settlement: Settlement, new_level: int,
                           logger: Logger, round_number: int, turn_index: int,
                           attacker_id: int) -> None:
    """Desactiva mejoras de ciudad que ya no cumplen el nivel requerido."""
    disabled_upgrades = calculate_disabled_upgrades(settlement, new_level)
    
    if disabled_upgrades:
        for upgrade in disabled_upgrades:
            if upgrade in settlement.mejoras:
                settlement.mejoras.remove(upgrade)
        
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=attacker_id,
            event_type="CITY_UPGRADES_DISABLED",
            details={
                "settlement_id": settlement.id,
                "disabled_upgrades": [u.value for u in disabled_upgrades],
                "new_level": new_level
            }
        )


def resolve_city_battle(
    world: World,
    attacker_id: int,
    settlement_id: int,
    rng: random.Random,
    logger: Logger,
    round_number: int,
    turn_index: int,
    has_siege_trait: bool = False
) -> Dict[str, Any]:
    """
    Resuelve una batalla entre un grupo y una ciudad.
    Función de ORQUESTACIÓN - modifica estado y registra logs.
    """
    attacker = world.get_group(attacker_id)
    settlement = world.get_settlement(settlement_id)
    
    if not attacker or not attacker.alive:
        return {"success": False, "reason": "attacker_dead"}
    
    if not settlement or settlement.ruinas:
        return {"success": False, "reason": "settlement_ruins"}
    
    if not can_attack_from_position(attacker.x, attacker.y, settlement.x, settlement.y):
        return {"success": False, "reason": "not_adjacent"}
    
    tile_attacker = world.get_tile(attacker.x, attacker.y)
    if tile_attacker and is_water_tile(tile_attacker.terreno):
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=attacker_id,
            event_type="CITY_BATTLE_BLOCKED",
            details={
                "reason": "attacker_on_water",
                "attacker_id": attacker_id,
                "settlement_id": settlement_id
            }
        )
        return {"success": False, "reason": "attacker_on_water"}
    
    defending_group = None
    groups_on_tile = world.get_groups_on_tile(settlement.x, settlement.y)
    for group in groups_on_tile:
        if group.id != attacker_id and group.alive:
            defending_group = group
            break
    
    participants = calculate_siege_participants(attacker.poblacion, attacker, has_siege_trait)
    
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=attacker.id,
        event_type="CITY_BATTLE_PARTICIPANTS",
        details={
            "participants": participants,
            "total_population": attacker.poblacion,
            "trait_override": "Asediadores" if has_siege_trait else None,
            "percentage": 40 if has_siege_trait else 30
        }
    )
    
    if participants == 0:
        return {"success": False, "reason": "no_participants"}
    
    bonus_percent = get_city_attack_bonus(attacker_id, settlement_id)
    
    result = calculate_city_battle(
        attacker_population=attacker.poblacion,
        attacker_power_avg=attacker.poder_promedio,
        attacker_participants=participants,
        bonus_percent=bonus_percent,
        settlement_points=settlement.puntos_ciudad,
        settlement_level=settlement.nivel,
        rng=rng,
        defender_power_avg=defending_group.poder_promedio if defending_group else 0.0,
        defender_population=defending_group.poblacion if defending_group else 0,
        attacker_wins_tie=False
    )
    
    result.attacker_id = attacker_id
    result.settlement_id = settlement_id
    if defending_group:
        result.defender_group_id = defending_group.id
    
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=attacker_id,
        event_type="CITY_BATTLE_START",
        details={
            "attacker_id": attacker_id,
            "settlement_id": settlement_id,
            "attacker_participants": result.attacker_participants,
            "attacker_power": round(result.attacker_power, 2),
            "city_defense_power": result.city_defense_power,
            "bonus_percent": result.bonus_percent,
            "defender_group": result.defender_group_id
        }
    )
    
    if result.attacker_won:
        old_level = settlement.nivel
        
        if result.city_destroyed:
            settlement.destroy()
            
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=attacker_id,
                event_type="CITY_DESTROYED",
                details={
                    "attacker_id": attacker_id,
                    "settlement_id": settlement_id,
                    "old_level": old_level,
                    "location": f"({settlement.x},{settlement.y})"
                }
            )
            
            _apply_city_destruction_move(world, attacker, settlement, logger, round_number, turn_index)
        else:
            new_level = result.new_city_level
            settlement.nivel = new_level
            settlement.puntos_ciudad = calculate_new_city_points_after_degradation(
                settlement.puntos_ciudad, old_level, new_level
            )
            
            _disable_city_upgrades(settlement, new_level, logger, round_number, turn_index, attacker_id)
            
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=attacker_id,
                event_type="CITY_DEGRADED",
                details={
                    "attacker_id": attacker_id,
                    "settlement_id": settlement_id,
                    "old_level": old_level,
                    "new_level": new_level
                }
            )
            
            _apply_city_rebound(world, attacker, settlement, rng, logger, round_number, turn_index)
        
        register_city_attack_bonus(attacker_id, settlement_id)
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=attacker_id,
            event_type="CITY_ATTACK_BONUS_UPDATED",
            details={
                "attacker_id": attacker_id,
                "settlement_id": settlement_id,
                "bonus_percent": get_city_attack_bonus(attacker_id, settlement_id)
            }
        )
        
        return {
            "success": True,
            "attacker_won": True,
            "city_destroyed": result.city_destroyed,
            "old_level": old_level,
            "new_level": result.new_city_level if not result.city_destroyed else 0,
            "attacker_losses": 0
        }
    else:
        losses = calculate_siege_losses_when_losing(participants, attacker, rng, has_siege_trait)
        
        if has_siege_trait:
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=attacker.id,
                event_type="TRAIT_OVERRIDE_APPLIED",
                details={
                    "trait": "Asediadores",
                    "regla_afectada": "calcular_bajas_ataque_ciudad",
                    "original_value": "10/30/50%",
                    "new_value": "10%"
                }
            )
        
        actual_losses = min(losses, attacker.poblacion)
        attacker.poblacion -= actual_losses
        
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=attacker_id,
            event_type="CITY_BATTLE_LOSSES",
            details={
                "attacker_id": attacker_id,
                "losses": actual_losses,
                "remaining_population": attacker.poblacion
            }
        )
        
        if attacker.poblacion <= 0:
            orphaned_settlements = on_group_death_settlements(world, attacker_id, logger, round_number)
            
            if orphaned_settlements:
                logger.log_event(
                    round_num=round_number,
                    turn_index=turn_index,
                    group_id=attacker_id,
                    event_type="SETTLEMENTS_ORPHANED",
                    details={
                        "settlement_ids": orphaned_settlements,
                        "cause": "city_battle_losses",
                        "settlement_id": settlement_id
                    }
                )
            
            logger.log_event(
                round_num=round_number,
                turn_index=turn_index,
                group_id=attacker_id,
                event_type="GROUP_DEATH",
                details={
                    "position": f"({attacker.x},{attacker.y})",
                    "cause": "city_battle_losses",
                    "settlement_id": settlement_id
                }
            )
            world.remove_group(attacker_id)
            clear_city_attack_bonus(attacker_id, settlement_id)
        else:
            valid_dirs = get_valid_directions(attacker.x, attacker.y, world.width, world.height)
            if valid_dirs:
                battle_direction = rng.choice(valid_dirs)
                apply_rebound(attacker, result.rebound_distance, battle_direction,
                             world, rng, logger, round_number, turn_index)
        
        logger.log_event(
            round_num=round_number,
            turn_index=turn_index,
            group_id=attacker_id,
            event_type="CITY_BATTLE_RESULT",
            details={
                "attacker_id": attacker_id,
                "settlement_id": settlement_id,
                "result": "LOSS",
                "losses": actual_losses,
                "rebound_distance": result.rebound_distance
            }
        )
        
        return {
            "success": True,
            "attacker_won": False,
            "attacker_losses": actual_losses,
            "attacker_died": attacker.poblacion <= 0,
            "rebound_distance": result.rebound_distance
        }


def repair_city(
    world: World,
    group_id: int,
    settlement_id: int,
    logger: Logger,
    round_number: int,
    turn_index: int,
    repair_points: int = 100
) -> bool:
    """Repara una ciudad (R16)."""
    group = world.get_group(group_id)
    settlement = world.get_settlement(settlement_id)
    
    if not group or not group.alive:
        return False
    
    if not settlement or settlement.ruinas:
        return False
    
    if settlement.dueño_grupo_id != group_id:
        return False
    
    if group.x != settlement.x or group.y != settlement.y:
        return False
    
    old_points = settlement.puntos_ciudad
    settlement.puntos_ciudad += repair_points
    
    max_points_for_level = settlement.nivel * 1000
    
    fully_repaired = False
    if settlement.puntos_ciudad >= max_points_for_level:
        settlement.puntos_ciudad = max_points_for_level
        fully_repaired = True
    
    logger.log_event(
        round_num=round_number,
        turn_index=turn_index,
        group_id=group_id,
        event_type="CITY_REPAIRED",
        details={
            "group_id": group_id,
            "settlement_id": settlement_id,
            "repair_points": repair_points,
            "old_points": old_points,
            "new_points": settlement.puntos_ciudad,
            "level": settlement.nivel,
            "max_points": max_points_for_level,
            "fully_repaired": fully_repaired
        }
    )
    
    return True