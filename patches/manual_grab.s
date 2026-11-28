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
