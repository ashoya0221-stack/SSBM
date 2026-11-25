# Manual-mode lookup for ordinary Versus players.
# Input r3 is the requested fighter kind: 27 = Master Hand, 28 = Crazy Hand.
# Examine P3's actual fighter kind first. If it is not the requested hand,
# fall back to P4. This avoids assuming the two hand roles are always ordered
# as P3=Master and P4=Crazy in the live Versus slots.
# Both slots are expected to contain the two hand fighters.
# Return the corresponding HSD_GObj in r3, matching the old GET_HAND ABI.

get_hand_manual:
ENTER
mr 28,3
li 3,2
CALL PLAYER_GET_ENTITY
cmpwi 3,0
beq manual_slot_p4
lwz 29,0x2c(3)
lwz 0,4(29)
cmpw 0,28
beq manual_slot_done

manual_slot_p4:
li 3,3
CALL PLAYER_GET_ENTITY

manual_slot_done:
LEAVE
