"""
main.py - Punto de entrada del simulador
Ejecuta la simulación con los parámetros configurados.
"""

import random
import sys
import argparse
from datetime import datetime

from world import World, TerrainType
from logger import Logger
from engine import Engine
from initial_groups import create_initial_groups, print_groups_summary


def create_initial_world() -> World:
    """
    Crea el mundo inicial con distribución de terrenos básica.
    
    Distribución:
    - Tierra: 70% (centro)
    - Agua: 20% (bordes laterales)
    - Montaña: 10% (zonas dispersas)
    - Costa: Transición agua-tierra (no se asigna directamente)
    """
    world = World(seed=42)
    
    # Configuración manual simple para pruebas
    # Agua en bordes izquierdo y derecho
    for x in range(1, 5):
        for y in range(1, 31):
            tile = world.get_tile(x, y)
            if tile:
                tile.terreno = TerrainType.AGUA
    
    for x in range(37, 41):
        for y in range(1, 31):
            tile = world.get_tile(x, y)
            if tile:
                tile.terreno = TerrainType.AGUA
    
    # Montañas en zonas específicas
    mountain_zones = [
        (18, 22), (19, 23), (20, 22),  # Zona Gigante Montaña
        (8, 25), (9, 26), (8, 24),     # Zona Gólem
        (30, 15), (31, 14), (32, 15),   # Zona Enanos
    ]
    
    for x, y in mountain_zones:
        tile = world.get_tile(x, y)
        if tile:
            tile.terreno = TerrainType.MONTAÑA
    
    return world


def print_simulation_header(max_rounds: int, seed: int) -> None:
    """Imprime cabecera de la simulación."""
    print("\n" + "=" * 80)
    print("SIMULADOR POR TURNOS - EJECUTANDO")
    print("=" * 80)
    print(f"Rondas máximas: {max_rounds}")
    print(f"Semilla RNG: {seed}")
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")


def print_simulation_footer(logger: Logger, world: World) -> None:
    """Imprime resumen final de la simulación."""
    print("\n" + "=" * 80)
    print("SIMULACIÓN COMPLETADA")
    print("=" * 80)
    
    stats = world.get_stats()
    print(f"Total grupos finales: {stats['total_groups']}")
    print(f"Total asentamientos: {stats['total_settlements']}")
    print(f"Total población: {stats['total_population']:.0f}")
    print(f"Total poder: {stats['total_power']:.0f}")
    
    print(f"Eventos registrados: {len(logger.events)}")
    print(f"Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")


def main():
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(description="Simulador por turnos")
    parser.add_argument("--rounds", "-r", type=int, default=10,
                        help="Número de rondas a simular (default: 10)")
    parser.add_argument("--seed", "-s", type=int, default=None,
                        help="Semilla para RNG (default: aleatoria)")
    parser.add_argument("--output", "-o", type=str, default="simulation_log.json",
                        help="Archivo de salida para logs (default: simulation_log.json)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Modo verbose (imprime información detallada)")
    
    args = parser.parse_args()
    
    # Configurar semilla
    seed = args.seed if args.seed is not None else random.randint(1, 999999)
    rng = random.Random(seed)
    
    # Crear mundo y logger
    world = create_initial_world()
    logger = Logger()
    
    # Crear grupos iniciales
    initial_groups = create_initial_groups(next_id=1)
    
    if args.verbose:
        print_groups_summary(initial_groups)
    
    # Añadir grupos al mundo
    for group in initial_groups:
        world.add_group(group, current_round=0)
    
    # Verificar que se añadieron correctamente
    print(f"Grupos añadidos al mundo: {world.group_count}")
    
    # Inicializar y ejecutar engine
    engine = Engine(world, rng, logger)
    
    print_simulation_header(args.rounds, seed)
    
    try:
        engine.run_simulation(max_rounds=args.rounds)
    except KeyboardInterrupt:
        print("\n\n[INTERRUPCIÓN] Simulación detenida por el usuario.")
    except Exception as e:
        print(f"\n\n[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Exportar logs
        if args.output.endswith('.json'):
            logger.export_json(args.output)
        elif args.output.endswith('.csv'):
            logger.export_csv(args.output)
        else:
            logger.export_json(args.output + ".json")
        
        print_simulation_footer(logger, world)
        
        if args.verbose:
            # Mostrar algunos eventos importantes
            print("\n--- EVENTOS DESTACADOS ---")
            battle_events = logger.get_events_by_type("BATTLE_START")
            print(f"Combates iniciados: {len(battle_events)}")
            
            death_events = logger.get_events_by_type("GROUP_DEATH")
            print(f"Grupos muertos: {len(death_events)}")
            
            birth_events = logger.get_events_by_type("BIRTHS_EVENT_START")
            print(f"Nacimientos eventos: {len(birth_events)}")


if __name__ == "__main__":
    # Configuración directa para pruebas
    import random
    from world import World
    from logger import Logger
    from engine import Engine
    from initial_groups import create_initial_groups
    
    seed = 42
    rounds = 25
    
    world = World(seed=seed)
    logger = Logger()
    rng = random.Random(seed)
    
    for group in create_initial_groups():
        world.add_group(group, current_round=0)
    
    print(f"Grupos añadidos al mundo: {world.group_count}")
    print(f"Rondas: {rounds}, Semilla: {seed}")
    
    engine = Engine(world, rng, logger)
    
    try:
        engine.run_simulation(max_rounds=rounds)
        print("✅ SIMULACIÓN COMPLETADA")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    stats = world.get_stats()
    print(f"\n--- RESULTADOS ---")
    print(f"Grupos finales: {stats['total_groups']}")
    print(f"Asentamientos: {stats['total_settlements']}")
    print(f"Población total: {stats['total_population']:.0f}")
    print(f"Eventos: {len(logger.events)}")
    
    logger.export_json(f"simulation_log_{rounds}.json")