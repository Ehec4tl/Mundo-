from typing import List, Dict, Any
import json
import csv


class Logger:
    """
    Logger mínimo para registrar eventos de la simulación.
    """
    
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
    
    def log_event(self, round_num: int, turn_index: int, group_id: int, 
                  event_type: str, details: Dict[str, Any]) -> None:
        """
        Registra un evento en el log.
        SIN timestamp - solo los campos especificados.
        
        Args:
            round_num: Número de ronda
            turn_index: Índice del turno dentro de la ronda
            group_id: ID del grupo involucrado
            event_type: Tipo de evento (ej: "MOVIMIENTO", "COMBATE", etc.)
            details: Detalles adicionales del evento (debe ser dict)
        """
        event = {
            'round': round_num,
            'turn_index': turn_index,
            'group_id': group_id,
            'event_type': event_type,
            'details': details
        }
        self.events.append(event)
    
    def export_json(self, filepath: str) -> None:
        """
        Exporta los eventos a un archivo JSON.
        
        Args:
            filepath: Ruta del archivo de salida
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.events, f, indent=2, ensure_ascii=False)
    
    def export_csv(self, filepath: str) -> None:
        """
        Exporta los eventos a un archivo CSV.
        
        Args:
            filepath: Ruta del archivo de salida
        """
        if not self.events:
            return
        
        # Obtener todas las columnas posibles
        fieldnames = ['round', 'turn_index', 'group_id', 'event_type']
        
        # Agregar campos de details dinámicamente
        details_keys = set()
        for event in self.events:
            details_keys.update(event['details'].keys())
        
        fieldnames.extend(sorted(details_keys))
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for event in self.events:
                row = {
                    'round': event['round'],
                    'turn_index': event['turn_index'],
                    'group_id': event['group_id'],
                    'event_type': event['event_type']
                }
                # Agregar detalles
                for key, value in event['details'].items():
                    row[key] = value
                
                writer.writerow(row)
    
    def clear(self) -> None:
        """Limpia todos los eventos del log"""
        self.events.clear()
    
    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Obtiene eventos filtrados por tipo"""
        return [e for e in self.events if e['event_type'] == event_type]
    
    def get_events_by_group(self, group_id: int) -> List[Dict[str, Any]]:
        """Obtiene eventos filtrados por grupo"""
        return [e for e in self.events if e['group_id'] == group_id]