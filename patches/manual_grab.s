# Manual edition only. Register the catch from the animation frame as well as
# the resident command stream. Native CollPos (priority 9) updates its world
# position before native GrabColl (priority 12) performs eligibility/overlap.
# Do not award captures by distance or write a victim's ownership here.
# Run from each hand's tag_anim callback. This does not rely on the native
# Fighter accessory-callback dispatch gate; synchronize both owned victims.
sync_captured_slots:
ENTER
mr 31,3
bl get_slots
mr 27,9
lwz 3,0(27)
cmpwi 3,0
beq sync_second_victim
bl sync_captured_fighter
sync_second_victim:
lwz 3,4(27)
cmpwi 3,0
beq sync_slots_done
bl sync_captured_fighter
sync_slots_done:
LEAVE

manual_grab_tick:
ENTER
mr 31,3
lwz 30,0x2c(31)
lwz 0,4(30)
lwz 8,0x10(30)
cmpwi 0,28
beq manual_ch_state
cmpwi 8,385
bne manual_grab_done
PTR 29,grab_mh
addi 29,29,20
b manual_grab_frame
manual_ch_state:
cmpwi 8,380
bne manual_grab_done
PTR 29,grab_ch
addi 29,29,4
manual_grab_frame:
lfs 0,0x894(30)
fctiwz 0,0
stfd 0,0x30(1)
lwz 8,0x34(1)
cmpwi 8,GRAB_START
blt manual_grab_close
cmpwi 8,GRAB_END
bge manual_grab_close
mr 3,31
bl get_slots
lwz 0,4(9)
cmpwi 0,0
bne manual_grab_close
# Other move setup may clear the acceptance bit. Restore it while a slot is
# free; keep INIT_GRAB's native callbacks and the native victim filters.
lbz 0,0x221e(30)
ori 0,0,2
stb 0,0x221e(30)
lwz 0,0x914(30)
cmpwi 0,0
bne manual_grab_rearm
stw 29,0x38(1)
mr 3,31
addi 4,1,0x30
CALL CREATE_HITBOX
manual_grab_rearm:
# Native target selection caches ALL overlapping candidates, even though it
# accepts only the nearest one. Clear that history while a second slot is free.
# Already held victims remain excluded by their native 0x1ff capture mask.
addi 3,30,0x914
CALL RESET_HIT_VICTIMS
b manual_grab_done
manual_grab_close:
lbz 0,0x221e(30)
andi. 0,0,0xfd
stb 0,0x221e(30)
mr 3,31
CALL CLEAR_HITBOXES
manual_grab_done:
LEAVE
# Called instead of Fighter_procPlayer's PLAYER_SET_SLOT_POS call.
# r3/r4/r5 are the original player slot, sub-fighter, and Fighter position;
# r6 is the current Fighter FP and r7 is this runtime's base address.
# Only Fighters still present in either hand's capture slots are redirected.
override_nametag_position:
ENTER
mr 31,6
mr 30,3
mr 29,4
mr 28,5
mr 27,7
addi 26,27,victim_slots
li 8,4
nametag_scan:
lwz 9,0(26)
cmpwi 9,0
beq nametag_next
lwz 9,0x2c(9)
cmpw 9,31
beq nametag_captured
nametag_next:
addi 26,26,4
addi 8,8,-1
cmpwi 8,0
bne nametag_scan
b nametag_original
nametag_captured:
# P4 is Crazy Hand. Use its current animated root/palm world position.
li 3,3
CALL PLAYER_GET_ENTITY
cmpwi 3,0
beq nametag_original
lwz 3,0x2c(3)
lwz 3,0x5e8(3)
lwz 3,0x120(3)
li 4,0
addi 5,1,0x30
CALL JOINT_WORLD
mr 3,30
mr 4,29
addi 5,1,0x30
CALL PLAYER_SET_SLOT_POS
b nametag_done
nametag_original:
# Non-captured Fighters and a missing P4 object keep the native coordinates.
mr 3,30
mr 4,29
mr 5,28
CALL PLAYER_SET_SLOT_POS
nametag_done:
LEAVE
