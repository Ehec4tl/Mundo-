@@
-from typing import List, Tuple, Dict, Any, Optional
+from typing import List, Tuple, Dict, Any, Optional
@@
 def can_build_puente(group: 'Group', world: 'World', direction: str) -> Tuple[bool, str]:
@@
-    return True, "", (bridge_x, bridge_y)
+    return True, "", (bridge_x, bridge_y)
@@
 def build_puente(group: 'Group', world: 'World', direction: str,
                 round_number: int, rng: random.Random) -> BuildResult:
@@
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
-        converted_tile=(bridge_x, bridge_y, None)
+        converted_tile=(bridge_x, bridge_y, None)
     )
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
