# Manual-mode lookup for ordinary Versus players.
# Input r3 is the fighter kind requested by the shared tagtsukamu runtime:
# 27 = Master Hand in player slot P3 (zero-based slot 2)
# 28 = Crazy Hand in player slot P4 (zero-based slot 3).
# Return the corresponding HSD_GObj in r3, matching the old GET_HAND ABI.

get_hand_manual:
ENTER
cmpwi 3,27
beq manual_slot_master
cmpwi 3,28
beq manual_slot_crazy
li 3,0
b manual_slot_done

manual_slot_master:
li 3,2
CALL PLAYER_GET_ENTITY
b manual_slot_done

manual_slot_crazy:
li 3,3
CALL PLAYER_GET_ENTITY

manual_slot_done:
LEAVE
