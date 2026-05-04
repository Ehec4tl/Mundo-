from typing import List, Dict, Optional, Tuple
from models import Tile, TerrainType, Group, Settlement, Structure, StructureType, TileEffect


class World:
    """
    Mundo que contiene el mapa de 40x30 casillas y gestiona grupos y asentamientos.
    """
    
    def __init__(self, seed: Optional[int] = None):
        """
        Inicializa el mundo con un mapa vacío.
        
        Args:
            seed: Semilla para reproducibilidad (almacenada para uso futuro, no se aplica globalmente)
        """
        # Almacenar semilla para futuro pero NO llamar a random.seed()
        self.seed = seed
        self.width = 40
        self.height = 30
        self._grid: Dict[Tuple[int, int], Tile] = {}
        self._groups: Dict[int, Group] = {}
        self._settlements: Dict[int, Settlement] = {}
        self._tile_effects: Dict[Tuple[int, int], List[TileEffect]] = {}  # MÓDULO 15B
        
        # Construir el mapa vacío (todos Tierra por defecto)
        self._build_empty_map()
    
    def _build_empty_map(self):
        """Construye el mapa con todas las casillas en Tierra por defecto"""
        for x in range(1, self.width + 1):
            for y in range(1, self.height + 1):
                self._grid[(x, y)] = Tile(
                    x=x,
                    y=y,
                    terreno=TerrainType.TIERRA
                )
    
    def get_tile(self, x: int, y: int) -> Optional[Tile]:
        """
        Obtiene una casilla por coordenadas.
        
        Args:
            x: Coordenada X (1-40)
            y: Coordenada Y (1-30)
            
        Returns:
            Tile si está dentro de los límites, None en caso contrario
        """
        if self.is_valid_coordinates(x, y):
            return self._grid[(x, y)]
        return None
    
    def set_tile(self, x: int, y: int, tile: Tile) -> bool:
        """
        Establece una casilla en el mapa.
        
        Args:
            x: Coordenada X (1-40)
            y: Coordenada Y (1-30)
            tile: Casilla a establecer
            
        Returns:
            True si se estableció correctamente, False si coordenadas inválidas
        """
        if self.is_valid_coordinates(x, y):
            tile.x = x
            tile.y = y
            self._grid[(x, y)] = tile
            return True
        return False
    
    def is_valid_coordinates(self, x: int, y: int) -> bool:
        """Verifica si las coordenadas están dentro de los límites del mapa"""
        return 1 <= x <= self.width and 1 <= y <= self.height
    
    def get_neighbors(self, x: int, y: int) -> Dict[str, Optional[Tile]]:
        """
        Obtiene los vecinos N, S, E, O de una casilla.
        
        Args:
            x: Coordenada X (1-40)
            y: Coordenada Y (1-30)
            
        Returns:
            Diccionario con claves 'N', 'S', 'E', 'O' y valores Tile o None
        """
        neighbors = {
            'N': self.get_tile(x, y - 1),
            'S': self.get_tile(x, y + 1),
            'E': self.get_tile(x + 1, y),
            'O': self.get_tile(x - 1, y)
        }
        return neighbors
    
    def get_valid_neighbors(self, x: int, y: int) -> List[Tile]:
        """
        Obtiene solo los vecinos válidos (dentro del mapa).
        
        Args:
            x: Coordenada X (1-40)
            y: Coordenada Y (1-30)
            
        Returns:
            Lista de tiles vecinos válidos
        """
        neighbors = self.get_neighbors(x, y)
        return [tile for tile in neighbors.values() if tile is not None]
    
    def add_group(self, group: Group, current_round: int = 0) -> bool:
        """
        Agrega un grupo al mundo y lo coloca en su casilla.
        Los IDs deben venir definidos desde fuera (NO auto-asignación).
    
        Args:
            group: Grupo a agregar (debe tener ID asignado)
            current_round: Ronda actual (para registrar created_in_round)
        
        Returns:
            True si se agregó correctamente, False si coordenadas inválidas o ID duplicado
        """
        if not self.is_valid_coordinates(group.x, group.y):
            return False
    
        # Verificar que el ID no exista ya
        if group.id in self._groups:
            return False
    
        # Registrar ronda de creación si no está ya establecida
        if group.created_in_round == 0:
            group.created_in_round = current_round
    
        # Guardar grupo
        self._groups[group.id] = group
    
        # Agregar a la casilla
        tile = self.get_tile(group.x, group.y)
        if tile:
            tile.add_group(group.id)
    
        return True
    
    def remove_group(self, group_id: int) -> bool:
        """
        Remueve un grupo del mundo.
        
        Args:
            group_id: ID del grupo a remover
            
        Returns:
            True si se removió correctamente, False si no existe
        """
        if group_id not in self._groups:
            return False
        
        group = self._groups[group_id]
        
        # Remover de la casilla
        tile = self.get_tile(group.x, group.y)
        if tile:
            tile.remove_group(group_id)
        
        # Eliminar del diccionario
        del self._groups[group_id]
        
        return True
    
    def add_structure(self, structure: Structure) -> bool:
        """Agrega una estructura al mundo"""
        tile = self.get_tile(structure.x, structure.y)
        if not tile:
            return False
        
        if tile.has_structure:
            return False
        
        tile.estructura = structure
        return True
    
    def remove_structure(self, x: int, y: int) -> bool:
        """Remueve una estructura del mundo"""
        tile = self.get_tile(x, y)
        if not tile or not tile.has_structure:
            return False
        
        tile.estructura = None
        return True
    
    def get_structure_at(self, x: int, y: int) -> Optional[Structure]:
        """Obtiene estructura en coordenadas"""
        tile = self.get_tile(x, y)
        return tile.estructura if tile else None
    
    def convert_water_to_land(self, x: int, y: int) -> bool:
        """Convierte casilla de agua a tierra (para Puente)"""
        tile = self.get_tile(x, y)
        if not tile or tile.terreno != TerrainType.AGUA:
            return False
        
        tile.terreno = TerrainType.TIERRA
        return True
    
    def update_settlement(self, settlement: Settlement) -> bool:
        """Actualiza un asentamiento existente"""
        if settlement.id not in self._settlements:
            return False
        
        self._settlements[settlement.id] = settlement
        return True
    
    def add_settlement(self, settlement: Settlement) -> bool:
        """
        Agrega un asentamiento al mundo y lo registra en su casilla.
        
        Args:
            settlement: Asentamiento a agregar (debe tener ID asignado)
            
        Returns:
            True si se agregó correctamente, False si coordenadas inválidas o ID duplicado
        """
        if not self.is_valid_coordinates(settlement.x, settlement.y):
            return False
        
        # Verificar que el ID no exista ya
        if settlement.id in self._settlements:
            return False
        
        # Guardar asentamiento
        self._settlements[settlement.id] = settlement
        
        # Registrar en la casilla
        tile = self.get_tile(settlement.x, settlement.y)
        if tile:
            tile.settlement_id = settlement.id
        
        return True
    
    def remove_settlement(self, settlement_id: int) -> bool:
        """
        Remueve un asentamiento del mundo.
        
        Args:
            settlement_id: ID del asentamiento a remover
            
        Returns:
            True si se removió correctamente, False si no existe
        """
        if settlement_id not in self._settlements:
            return False
        
        settlement = self._settlements[settlement_id]
        
        # Remover de la casilla
        tile = self.get_tile(settlement.x, settlement.y)
        if tile:
            tile.settlement_id = None
        
        # Eliminar del diccionario
        del self._settlements[settlement_id]
        
        return True
    
    def get_group(self, group_id: int) -> Optional[Group]:
        """Obtiene un grupo por su ID"""
        return self._groups.get(group_id)
    
    def get_settlement(self, settlement_id: int) -> Optional[Settlement]:
        """Obtiene un asentamiento por su ID"""
        return self._settlements.get(settlement_id)
    
    def get_settlement_by_coords(self, x: int, y: int) -> Optional[Settlement]:
        """Obtiene un asentamiento por sus coordenadas"""
        for settlement in self._settlements.values():
            if settlement.x == x and settlement.y == y:
                return settlement
        return None
    
    def move_group_to(self, group_id: int, new_x: int, new_y: int) -> bool:
        """
        Mueve un grupo a nuevas coordenadas actualizando tiles.
    
        Args:
            group_id: ID del grupo a mover
            new_x: Nueva coordenada X
            new_y: Nueva coordenada Y
        
        Returns:
            True si se movió correctamente, False si el grupo no existe o coordenadas inválidas
        """
        group = self.get_group(group_id)
        if not group:
            return False
    
        if not self.is_valid_coordinates(new_x, new_y):
            return False
    
        # Remover de tile actual
        old_tile = self.get_tile(group.x, group.y)
        if old_tile:
            old_tile.remove_group(group_id)
    
        # Actualizar coordenadas del grupo
        group.x = new_x
        group.y = new_y
    
        # Añadir a nuevo tile
        new_tile = self.get_tile(new_x, new_y)
        if new_tile:
            new_tile.add_group(group_id)
            return True
        
        return False
    
    def get_groups_on_tile(self, x: int, y: int) -> List[Group]:
        """Obtiene todos los grupos en una casilla específica"""
        tile = self.get_tile(x, y)
        if not tile:
            return []
        
        groups = []
        for group_id in tile.group_ids:
            group = self.get_group(group_id)
            if group:
                groups.append(group)
        return groups
    
    def get_all_groups(self) -> List[Group]:
        """Obtiene todos los grupos en el mundo"""
        return list(self._groups.values())
    
    def get_all_settlements(self) -> List[Settlement]:
        """Obtiene todos los asentamientos en el mundo"""
        return list(self._settlements.values())
    
    @property
    def group_count(self) -> int:
        """Número total de grupos en el mundo"""
        return len(self._groups)
    
    @property
    def settlement_count(self) -> int:
        """Número total de asentamientos en el mundo"""
        return len(self._settlements)
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas básicas del mundo"""
        total_population = sum(group.poblacion for group in self._groups.values())
        total_power = sum(group.poder_total for group in self._groups.values())
        
        return {
            'total_groups': self.group_count,
            'total_settlements': self.settlement_count,
            'total_population': total_population,
            'total_power': total_power
        }
    
    def get_orphan_settlements(self) -> List[Settlement]:
        """
        Obtiene todos los asentamientos huérfanos (sin dueño vivo).
        
        Un asentamiento es huérfano si:
        - No está en ruinas
        - No tiene dueño (dueño_grupo_id is None)
        - O su dueño está muerto (grupo no existe o no está vivo)
        
        Returns:
            Lista de asentamientos huérfanos
        """
        orphan_settlements = []
        
        for settlement in self._settlements.values():
            if settlement.ruinas:
                continue
            
            # Verificar si es huérfano
            if settlement.dueño_grupo_id is None:
                orphan_settlements.append(settlement)
            else:
                owner = self.get_group(settlement.dueño_grupo_id)
                if owner is None or not owner.alive:
                    orphan_settlements.append(settlement)
        
        return orphan_settlements
    
    # ========================================================================
    # MÓDULO 13: Métodos para gestión de radios de influencia (Regla 21)
    # ========================================================================
    
    def get_settlements_by_age(self) -> List[Settlement]:
        """
        Obtiene asentamientos ordenados por antigüedad (fundado_en_ronda ascendente).
        R21.3: Prevalece el asentamiento más antiguo.
        
        Returns:
            Lista de asentamientos ordenados del más antiguo al más nuevo
        """
        settlements = self.get_all_settlements()
        return sorted(settlements, key=lambda s: s.fundado_en_ronda)
    
    def recalculate_all_influences(self, logger=None, round_number: int = 0) -> None:
        """
        Recalcula todas las máscaras de influencia después de cambios.
        R21.4: Evalúa casilla por casilla aplicando prioridad por antigüedad.
        
        Args:
            logger: Logger opcional para registrar eventos
            round_number: Ronda actual para logs
        """
        from rules import apply_older_settlement_priority
        settlements = self.get_all_settlements()
        final_masks = apply_older_settlement_priority(settlements, logger, round_number)
        
        for settlement in settlements:
            if settlement.id in final_masks:
                settlement.influence_radius = final_masks[settlement.id]
    
    def is_within_any_influence(self, x: int, y: int) -> Tuple[bool, Optional[int]]:
        """
        Verifica si una casilla está dentro del radio de algún asentamiento activo.
        R21.2: No se pueden fundar nuevos asentamientos dentro del radio de otro.
        
        Args:
            x, y: Coordenadas a verificar
        
        Returns:
            (is_inside, blocking_settlement_id)
        """
        for settlement in self.get_all_settlements():
            if settlement.ruinas:
                continue
            if hasattr(settlement, 'influence_radius') and (x, y) in settlement.influence_radius:
                return True, settlement.id
        return False, None
    
    def can_found_settlement_at(self, x: int, y: int) -> Tuple[bool, Optional[int]]:
        """
        R21.2: Verifica si se puede fundar un asentamiento en las coordenadas dadas.
        
        Args:
            x, y: Coordenadas a verificar
        
        Returns:
            (can_found, blocking_settlement_id)
        """
        is_inside, blocking_id = self.is_within_any_influence(x, y)
        return (not is_inside, blocking_id if is_inside else None)
    
    # ========================================================================
    # MÓDULO 15B: Gestión de efectos persistentes en tiles
    # ========================================================================
    
    def add_tile_effect(self, effect: TileEffect) -> bool:
        """
        Agrega un efecto persistente a una casilla.
        
        Args:
            effect: Efecto a agregar (debe tener x, y, tipo, duracion_restante)
            
        Returns:
            True si se agregó correctamente
        """
        key = (effect.x, effect.y)
        if key not in self._tile_effects:
            self._tile_effects[key] = []
        
        # Reemplazar si ya existe del mismo tipo
        for i, existing in enumerate(self._tile_effects[key]):
            if existing.tipo == effect.tipo:
                self._tile_effects[key][i] = effect
                return True
        
        self._tile_effects[key].append(effect)
        return True
    
    def remove_tile_effect(self, x: int, y: int, effect_type: str) -> bool:
        """
        Remueve un efecto de una casilla.
        
        Args:
            x, y: Coordenadas
            effect_type: Tipo de efecto a remover (usando effect.tipo.value)
            
        Returns:
            True si se removió algún efecto
        """
        key = (x, y)
        if key in self._tile_effects:
            original_count = len(self._tile_effects[key])
            self._tile_effects[key] = [e for e in self._tile_effects[key] 
                                        if e.tipo.value != effect_type]
            if not self._tile_effects[key]:
                del self._tile_effects[key]
            return len(self._tile_effects.get(key, [])) < original_count
        return False
    
    def has_tile_effect_at(self, x: int, y: int, effect_type: str) -> bool:
        """
        Verifica si hay un efecto activo en la casilla.
        
        Args:
            x, y: Coordenadas
            effect_type: Tipo de efecto a verificar
            
        Returns:
            True si existe el efecto
        """
        key = (x, y)
        if key not in self._tile_effects:
            return False
        return any(e.tipo.value == effect_type for e in self._tile_effects[key])
    
    def decrement_tile_effects(self, round_number: int, logger=None) -> None:
        """
        Decrementa duración de efectos y elimina los expirados.
        
        Args:
            round_number: Ronda actual para logs
            logger: Logger opcional para registrar expiraciones
        """
        expired = []
        
        for key, effects in self._tile_effects.items():
            for effect in effects:
                effect.duracion_restante -= 1
                if effect.duracion_restante <= 0:
                    expired.append((key, effect))
        
        for key, effect in expired:
            self.remove_tile_effect(key[0], key[1], effect.tipo.value)
            if logger:
                logger.log_event(
                    round_num=round_number,
                    turn_index=-1,
                    group_id=-1,
                    event_type="tile_effect_expired",
                    details={
                        "effect_type": effect.tipo.value,
                        "position": f"({effect.x},{effect.y})"
                    }
                )
    
    def get_tile_effects(self, x: int, y: int) -> List[TileEffect]:
        """
        Obtiene todos los efectos en una casilla.
        
        Args:
            x, y: Coordenadas
            
        Returns:
            Lista de efectos (copia para evitar modificación externa)
        """
        return self._tile_effects.get((x, y), []).copy()