@@
     # ========================================================================
     # Acción CONSTRUIR
     # ========================================================================
     if action.startswith("BUILD_"):
         from rules import (
             build_empalizada, build_bastion, build_puente, build_city_fortaleza,
             BuildResult, can_build_empalizada, can_build_bastion, can_build_puente
         )
+        # Bloquear si el grupo está AGOTADO (R8.4 y R25.4)
+        if StateType.AGOTADO in group.estados:
+            logger.log_event(
+                round_num=round_number,
+                turn_index=turn_index,
+                group_id=group.id,
+                event_type="ACTION_BLOCKED_BY_STATE",
+                details={
+                    "action": action,
+                    "state": "Agotado",
+                    "reason": "exhausted_state_active"
+                }
+            )
+            group.last_action_was_grow = False
+            return
@@
-        # Aplicar resultado
-        if result.success and result.structure:
-            world.add_structure(result.structure)
-            
-            if result.converted_tile:
-                x, y, _ = result.converted_tile
-                world.convert_water_to_land(x, y)
-            
-            if result.settlement_updates:
-                for sid, settlement in result.settlement_updates.items():
-                    world.update_settlement(settlement)
-        
-        logger.log_event(
-            round_num=round_number,
-            turn_index=turn_index,
-            group_id=group.id,
-            event_type="BUILD_FAILED",
-            details={"action": action, "reason": "not_implemented_yet"}
-        )
+        # Aplicar resultado
+        if result and result.success:
+            if result.structure:
+                world.add_structure(result.structure)
+            
+            if result.converted_tile:
+                x, y, _ = result.converted_tile
+                world.convert_water_to_land(x, y)
+            
+            if result.settlement_updates:
+                for sid, settlement in result.settlement_updates.items():
+                    world.update_settlement(settlement)
+
+            logger.log_event(
+                round_num=round_number,
+                turn_index=turn_index,
+                group_id=group.id,
+                event_type="BUILD_SUCCESS",
+                details={"action": action, "result": "success"}
+            )
+        else:
+            logger.log_event(
+                round_num=round_number,
+                turn_index=turn_index,
+                group_id=group.id,
+                event_type="BUILD_FAILED",
+                details={"action": action, "reason": getattr(result, 'details', 'unknown')}
+            )
         group.last_action_was_grow = False
         return
