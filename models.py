from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from enum import Enum


class TerrainType(Enum):
    """Tipos de terreno disponibles en el mapa"""
    TIERRA = "Tierra"
    MONTAÑA = "Montaña"
    AGUA = "Agua"
    COSTA = "Costa"


class StateType(Enum):
    """
    Estados que pueden afectar a los grupos.
    EXACTAMENTE los 13 estados del manual R25.
    """
    AGOTADO = "Agotado"
    EN_MARCHA = "En Marcha"
    VULNERABLE = "Vulnerable"
    ESTABLECIENDO = "Estableciendo"
    SOBREPOBLACION = "Sobrepoblación"
    MAREADO = "Mareado"
    SORPRESA = "Sorpresa"
    FORTALEZA = "Fortaleza"
    ENTORPECIDO = "Entorpecido"
    INSPIRADOS = "Inspirados"
    MIEDO = "Miedo"
    TERRORIFICO = "Terroífico"
    DESMORALIZADO = "Desmoralizado"
    DEBUFF_PODER = "Debuff Poder"  # NUEVO: Para Runa de guerra


# Añadir después de StateType.DEBUFF_PODER

class TileEffectType(Enum):
    """Efectos persistentes en casillas"""
    CONGELADO = "Congelado"  # -10% poder por 3 turnos


@dataclass
class TileEffect:
    """Efecto persistente en una casilla"""
    tipo: TileEffectType
    x: int
    y: int
    duracion_restante: int  # turnos que quedan
    aplicado_por_grupo_id: int
    ronda_aplicacion: int

class StructureType(Enum):
    """Tipos de estructuras construibles"""
    EMPALIZADA = "Empalizada"
    BASTION = "Bastión"
    PUENTE = "Puente"
    CIUDAD_FORTALEZA = "Ciudad Fortaleza"


class CityUpgrade(Enum):
    """Mejoras de ciudad (no físicas en el tile)"""
    HOSPITAL = "Hospital"
    CARRETERAS = "Carreteras"
    VIVIENDAS_MEJORES = "Viviendas mejores"
    LUGAR_EMBLEMATICO = "Lugar emblemático"


@dataclass
class Group:
    """
    Grupo de personajes de la misma subraza que actúan juntos.
    """
    id: int
    raza: str
    subraza: str
    x: int
    y: int
    poblacion: int
    poder_promedio: float
    estados: Dict[StateType, int] = field(default_factory=dict)
    asentamiento_id: Optional[int] = None
    grupo_original_id: Optional[int] = None
    reputacion: Dict[int, int] = field(default_factory=dict)
    acted_this_round: bool = False
    created_in_round: int = 0  # Ronda en que fue creado (para inmunidad R12.2)
    last_action_was_grow: bool = False  # Para detectar Crecer dos veces seguidas (R25)
    traits: Set[str] = field(default_factory=set)  # Conjunto de rasgos pasivos
    _was_attacked_last_turn: bool = False  # Para Reflejos Felinos
    _power_multiplier: float = 1.0  # Para Runa de guerra
    # En la clase Group, añadir:
    _free_move_available: bool = False  # Para Caza helada - movimiento gratuito
    
    @property
    def poder_total(self) -> float:
        """Calcula poder total automáticamente según población y poder promedio"""
        return self.poblacion * self.poder_promedio * getattr(self, '_power_multiplier', 1.0)
    
    @property
    def alive(self) -> bool:
        """Determina si el grupo está vivo según su población"""
        return self.poblacion > 0
    
    def __post_init__(self):
        """Validaciones básicas"""
        if self.poblacion < 0:
            raise ValueError(f"La población no puede ser negativa: {self.poblacion}")
        if self.poder_promedio < 0:
            raise ValueError(f"El poder promedio no puede ser negativo: {self.poder_promedio}")
        if not (1 <= self.x <= 40 and 1 <= self.y <= 30):
            raise ValueError(f"Coordenadas fuera de rango: ({self.x}, {self.y})")
    # MÓDULO 15C: Tracking para rasgos
    _last_attacked_target_id: Optional[int] = None  # Para Caza helada
    _fortaleza_construidas: int = 0  # Para Como una joya (límite 10)
    _free_move_used_this_turn: bool = False  # Para acción gratuita

@dataclass
class Settlement:
    """
    Asentamiento (pueblo/ciudad/fortaleza) independiente del grupo.
    """
    id: int
    nivel: int
    x: int
    y: int
    puntos_ciudad: int
    fundado_en_ronda: int
    dueño_grupo_id: Optional[int] = None
    ruinas: bool = False
    mejoras: List[CityUpgrade] = field(default_factory=list)
    raza: str = ""      # Raza del asentamiento (hereda del fundador)
    subraza: str = ""   # Subraza del asentamiento
    
    # NUEVOS ATRIBUTOS PARA MÓDULO 13: Radio de influencia (Regla 21)
    influence_radius: List[Tuple[int, int]] = field(default_factory=list)  # Máscara de casillas influenciadas
    created_round: int = 0  # Ronda de fundación (para antigüedad)
    
    def __post_init__(self):
        """Mantiene consistencia: ruinas implica nivel 0"""
        if self.ruinas and self.nivel != 0:
            raise ValueError(f"Si ruinas=True, nivel debe ser 0. Nivel actual: {self.nivel}")
        if not self.ruinas and self.nivel <= 0:
            raise ValueError(f"Si no es ruinas, nivel debe ser mayor a 0. Nivel actual: {self.nivel}")
        if self.nivel < 0:
            raise ValueError(f"El nivel no puede ser negativo: {self.nivel}")
        if self.puntos_ciudad < 0:
            raise ValueError(f"Los puntos de ciudad no pueden ser negativos: {self.puntos_ciudad}")
        if not (1 <= self.x <= 40 and 1 <= self.y <= 30):
            raise ValueError(f"Coordenadas fuera de rango: ({self.x}, {self.y})")
    
    def destroy(self):
        """Convierte el asentamiento en ruinas"""
        self.ruinas = True
        self.nivel = 0
        self.mejoras.clear()  # Limpiar mejoras al destruirse
        self.influence_radius = []  # R21.7: Ruinas no tienen radio
    
    def add_upgrade(self, upgrade: CityUpgrade) -> bool:
        """Añade una mejora si no existe ya"""
        if upgrade not in self.mejoras:
            self.mejoras.append(upgrade)
            return True
        return False
    
    def has_upgrade(self, upgrade: CityUpgrade) -> bool:
        """Verifica si tiene una mejora específica"""
        return upgrade in self.mejoras
    
    def get_max_structures(self) -> int:
        """Calcula límite máximo de estructuras (mejoras) según nivel"""
        return self.nivel * 2
    
    def get_available_slots(self) -> int:
        """Calcula slots disponibles para mejoras"""
        return self.get_max_structures() - len(self.mejoras)
    
    def update_influence_mask(self, mask: List[Tuple[int, int]]) -> None:
        """
        Actualiza la máscara de influencia del asentamiento.
        R21.4: Almacena la máscara irregular final.
        """
        self.influence_radius = mask


@dataclass
class Structure:
    """
    Estructura construida en una casilla.
    """
    tipo: StructureType
    x: int
    y: int
    grupo_constructor_id: int
    ronda_construccion: int
    
    def __post_init__(self):
        if not self.tipo:
            raise ValueError("El tipo de estructura no puede estar vacío")
        if not isinstance(self.tipo, StructureType):
            raise ValueError(f"Tipo inválido: {self.tipo}")


@dataclass
class Tile:
    """
    Casilla individual del mapa.
    """
    x: int
    y: int
    terreno: TerrainType
    estructura: Optional[Structure] = None
    settlement_id: Optional[int] = None
    group_ids: List[int] = field(default_factory=list)
    
    def __post_init__(self):
        """Validaciones básicas"""
        if not (1 <= self.x <= 40 and 1 <= self.y <= 30):
            raise ValueError(f"Coordenadas fuera de rango: ({self.x}, {self.y})")
        if not isinstance(self.terreno, TerrainType):
            raise ValueError(f"Terreno inválido: {self.terreno}")
    
    def add_group(self, group_id: int):
        """Agrega un grupo a la casilla si no está ya presente"""
        if group_id not in self.group_ids:
            self.group_ids.append(group_id)
    
    def remove_group(self, group_id: int):
        """Remueve un grupo de la casilla"""
        if group_id in self.group_ids:
            self.group_ids.remove(group_id)
    
    def has_group(self, group_id: int) -> bool:
        """Verifica si un grupo está en la casilla"""
        return group_id in self.group_ids
    
    @property
    def has_settlement(self) -> bool:
        """Indica si la casilla tiene un asentamiento"""
        return self.settlement_id is not None
    
    @property
    def has_structure(self) -> bool:
        """Indica si la casilla tiene una estructura"""
        return self.estructura is not None
    
    @property
    def group_count(self) -> int:
        """Número de grupos en la casilla"""
        return len(self.group_ids)