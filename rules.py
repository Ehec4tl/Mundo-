@@
 from typing import List, Tuple, Dict, Any, Optional
@@
 class BuildResult:
@@
 def can_build_empalizada(group: 'Group', world: 'World') -> Tuple[bool, str]:
@@
-    tile = world.get_tile(group.x, group.y)
-    
-    if not tile:
-        return False, "invalid_tile"
-    
-    if tile.has_structure:
-        return False, "tile_already_has_structure"
-    
-    if tile.has_settlement:
-        # Actualmente no permitimos construir sobre ciudad sin reglas adicionales
-        return False, "cannot_build_on_city"
-    
-    return True, ""
+    tile = world.get_tile(group.x, group.y)
+
+    if not tile:
+        return False, "invalid_tile"
+
+    if tile.has_structure:
+        return False, "tile_already_has_structure"
+
+    # Si hay ciudad en la casilla, aplicar límite: nivel * 2 (radius=1)
+    if tile.has_settlement:
+        settlement = world.get_settlement(tile.settlement_id)
+        if settlement and not settlement.ruinas:
+            max_structures = settlement.nivel * 2
+            current = _count_structures_near_settlement(settlement, world, radius=1)
+            if current >= max_structures:
+                return False, "max_structures_reached_for_city"
+            return False, "cannot_build_on_city"
+
+    return True, ""
@@
 def can_build_bastion(group: 'Group', world: 'World') -> Tuple[bool, str]:
@@
-    tile = world.get_tile(group.x, group.y)
-    if not tile:
-        return False, "invalid_tile"
-    if tile.has_structure:
-        return False, "tile_already_has_structure"
-    if tile.has_settlement:
-        return False, "cannot_build_on_city"
-    return True, ""
+    tile = world.get_tile(group.x, group.y)
+    if not tile:
+        return False, "invalid_tile"
+    if tile.has_structure:
+        return False, "tile_already_has_structure"
+    if tile.has_settlement:
+        settlement = world.get_settlement(tile.settlement_id)
+        if settlement and not settlement.ruinas:
+            max_structures = settlement.nivel * 2
+            current = _count_structures_near_settlement(settlement, world, radius=1)
+            if current >= max_structures:
+                return False, "max_structures_reached_for_city"
+            return False, "cannot_build_on_city"
+    return True, ""
@@
 def can_build_puente(group: 'Group', world: 'World', direction: str) -> Tuple[bool, str]:
@@
-    target_tile = world.get_tile(tx, ty)
-    if not target_tile:
-        return False, "invalid_target"
-    if target_tile.has_structure:
-        return False, "target_has_structure"
-    if target_tile.terreno != TerrainType.AGUA:
-        return False, "target_not_water"
-    return True, ""
+    target_tile = world.get_tile(tx, ty)
+    if not target_tile:
+        return False, "invalid_target"
+    if target_tile.has_structure:
+        return False, "target_has_structure"
+    if target_tile.terreno != TerrainType.AGUA:
+        return False, "target_not_water"
+
+    if target_tile.has_settlement:
+        settlement = world.get_settlement(target_tile.settlement_id)
+        if settlement and not settlement.ruinas:
+            max_structures = settlement.nivel * 2
+            current = _count_structures_near_settlement(settlement, world, radius=1)
+            if current >= max_structures:
+                return False, "max_structures_reached_for_city"
+            return False, "cannot_build_on_city"
+
+    return True, ""
+
+
+def _count_structures_near_settlement(settlement: 'Settlement', world: 'World', radius: int = 1) -> int:
+    """
+    Cuenta estructuras en la vecindad manhattan de 'radius' alrededor de la ciudad.
+    Por defecto radius=1 (tile central + adyacentes N,S,E,O).
+    """
+    if settlement is None:
+        return 0
+    count = 0
+    sx, sy = settlement.x, settlement.y
+    for dx in range(-radius, radius + 1):
+        for dy in range(-radius, radius + 1):
+            if abs(dx) + abs(dy) > radius:
+                continue
+            nx, ny = sx + dx, sy + dy
+            if not world.is_valid_coordinates(nx, ny):
+                continue
+            tile = world.get_tile(nx, ny)
+            if tile and getattr(tile, 'has_structure', False):
+                count += 1
+    return count
