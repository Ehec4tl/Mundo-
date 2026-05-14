@@
 def execute_action(group: Group, action: str, world: World, rng: random.Random,
                    logger: Logger, round_number: int, turn_index: int) -> None:
@@
-    from models import StateType
+    from models import StateType
+
+    # Bloquear todas las acciones diferentes a movimiento si está En Marcha (R9.8)
+    if StateType.EN_MARCHA in group.estados:
+        if not action.startswith("MOVE_"):
+            logger.log_event(
+                round_num=round_number,
+                turn_index=turn_index,
+                group_id=group.id,
+                event_type="ACTION_BLOCKED_BY_STATE",
+                details={
+                    "action": action,
+                    "state": "En Marcha",
+                    "reason": "only_movement_allowed_when_on_march"
+                }
+            )
+            group.last_action_was_grow = False
+            return
@@
