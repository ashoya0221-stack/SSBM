# Position-independent runtime. Expanded by tools/build_gecko.py for Keystone PPC32.
# MH coordinates both hands; persistent clock lives inside this payload.
# Do not use extra move-union words: normal boss cleanup treats them as item pointers.

# Replaces stfs f0,0x34(r1) in MH's fourth combo branch.
stfs 0,0x34(1)
ENTER
mr 3,28
PTR 4,start_pair
addi 5,1,0x8c
CALL MASTER_MOVE
LEAVE_HOOK
b runtime_end

start_pair:
ENTER
mr 31,3
lwz 30,0x2c(31)
li 3,28
CALL GET_HAND
cmpwi 3,0
beq start_cancel
mr 29,3
lwz 28,0x2c(29)
lwz 0,0x10(28)
cmpwi 0,384
bne start_cancel
lwz 0,0x2250(28)
cmpwi 0,380
bne start_cancel
lbz 0,0x221f(28)
andi. 0,0,0x10
bne start_cancel
mr 3,29
li 4,380
bl start_hand
mr 3,31
li 4,385
bl start_hand
stw 29,0x1a5c(30)
stw 31,0x1a5c(28)
PTR 27,pair_state
li 0,0
addi 8,27,victim_slots-pair_state
stw 0,0(8)
stw 0,4(8)
stw 0,8(8)
stw 0,12(8)
bl reset_pair_clock
b start_done
start_cancel:
mr 3,31
CALL MASTER_IDLE
start_done:
LEAVE

start_hand:
ENTER
mr 31,3
mr 29,4
lwz 30,0x2c(31)
lwz 27,4(30)
lwz 8,0x10c(30)
lwz 8,0xc(8)
PTR 9,empty_script
addi 10,9,grab_mh-empty_script
addi 11,9,tag_anim-empty_script
cmpwi 27,28
beq install_ch
stw 10,0x1fd4(8)
stw 9,0x1fec(8)
lis 8,0x803d
ori 8,8,0x2104
b install_callbacks
install_ch:
addi 10,10,grab_ch-grab_mh
stw 10,0x1f5c(8)
stw 9,0x1f74(8)
lis 8,0x803d
ori 8,8,0x282c
install_callbacks:
stw 11,0(8)
stw 11,0x20(8)
stw 11,0x40(8)
li 0,0
stw 0,0x1a58(30)
stw 0,0x2360(30)
stw 0,0x2200(30)
stw 0,0x2204(30)
stw 0,0x2348(30)
stw 0,0x80(30)
stw 0,0x84(30)
stw 0,0x88(30)
mr 3,31
mr 4,29
bl change_state
mr 3,30
li 4,128
lis 7,0x8015
ori 7,7,0x50d8
cmpwi 27,28
bne register_grab
li 4,256
lis 7,0x8015
ori 7,7,0xab94
register_grab:
PTR 5,on_grab
li 6,0
CALL INIT_GRAB
LEAVE

# Keep native acceptance open until this hand has captured two distinct victims.
on_grab:
ENTER
bl attach_captured
lwz 10,0x1a58(8)
lwz 0,0(9)
cmpw 0,10
beq grabbed_done
cmpwi 0,0
beq grabbed_first
stw 10,4(9)
lbz 0,0x221e(8)
andi. 0,0,0xfd
stb 0,0x221e(8)
b grabbed_flag
grabbed_first:
stw 10,0(9)
grabbed_flag:
li 0,1
stw 0,0x2360(8)
grabbed_done:
LEAVE

# r3 stays the hand; r8 = Fighter; r9 = two payload-owned victim slots.
get_slots:
mflr 11
lwz 8,0x2c(3)
lwz 10,4(8)
addi 10,10,-27
slwi 10,10,3
PTR 9,victim_slots
add 9,9,10
mtlr 11
blr

# Change only animation and callbacks; command scripts are initialized normally.
change_state:
ENTER
mr 31,3
li 0,0
stw 0,0x30(1)
lis 0,0x3f80
stw 0,0x34(1)
lfs 1,0x30(1)
lfs 2,0x34(1)
lfs 3,0x30(1)
li 5,0
li 6,0
CALL CHANGE_STATE
mr 3,31
CALL ANIM_INIT
LEAVE

# MH is the single coordinator. CH never advances phase or emits damage on its own.
tag_anim:
ENTER
mr 31,3
lwz 30,0x2c(31)
lwz 0,4(30)
cmpwi 0,28
beq secondary_tick
li 3,28
CALL GET_HAND
mr 29,3
cmpwi 29,0
beq finish_pair
lwz 28,0x2c(29)
lbz 0,0x221f(28)
andi. 0,0,0x10
bne finish_pair
lwz 8,0x10(28)
lwz 9,0x10(30)
addi 9,9,-5
cmpw 8,9
bne finish_pair
PTR 27,pair_state
lwz 8,0(27)
addi 8,8,1
stw 8,0(27)
cmpwi 8,900
bge finish_pair
lwz 0,0x10(30)
cmpwi 0,385
beq pair_grab
cmpwi 0,386
beq pair_squeeze
b pair_fail

secondary_tick:
li 3,27
CALL GET_HAND
cmpwi 3,0
beq finish_secondary
lwz 8,0x2c(3)
lwz 0,0x10(8)
cmpwi 0,385
blt finish_dead_master
cmpwi 0,387
ble tick_done
finish_dead_master:
bl cleanup_hand
finish_secondary:
mr 3,31
bl cleanup_hand
b tick_done

pair_grab:
lwz 8,0(27)
cmpwi 8,180
bge pair_grab_finished
mr 3,31
mr 4,29
bl both_done
cmpwi 3,0
beq tick_done
pair_grab_finished:
mr 3,31
bl valid_victim
mr 26,3
mr 3,29
bl valid_victim
or. 0,26,3
beq pair_miss
mr 3,31
li 4,386
bl begin_squeeze_hand
mr 3,29
li 4,381
bl begin_squeeze_hand
bl reset_pair_clock
mr 3,31
CALL BOSS_LAUGH
b tick_done
pair_miss:
mr 3,31
CALL CLEAR_HITBOXES
mr 3,29
CALL CLEAR_HITBOXES
mr 3,31
li 4,387
bl change_state
mr 3,29
li 4,382
bl change_state
bl reset_pair_clock
mr 3,31
li 4,225
bl play_sfx
b tick_done

pair_squeeze:
# Actor tick counts diverge under hitlag. Use the native animation frame instead.
lfs 0,0x894(30)
fctiwz 0,0
stfd 0,0x30(1)
lwz 26,0x34(1)
lwz 8,4(27)
cmpw 26,8
ble tick_done
stw 26,4(27)
bl sync_partner
pulse_due:
lwz 8,8(27)
cmpwi 8,5
bge throw_due
slwi 8,8,2
addi 9,27,pulse_frames-pair_state
lwzx 8,9,8
cmpw 26,8
blt throw_due
mr 3,31
bl emit_pummel
mr 3,29
bl emit_pummel
mr 3,31
lis 4,4
ori 4,4,0xe212
bl play_sfx
lwz 8,8(27)
addi 8,8,1
stw 8,8(27)
li 0,HITLAG_DAMAGE
stw 0,0x1914(30)
stw 0,0x1914(28)
throw_due:
lwz 8,16(27)
cmpwi 8,0
bne pair_recovery
cmpwi 26,THROW_FRAME
blt tick_done
mr 3,31
li 4,9
bl play_sfx
mr 3,31
bl throw_victim
mr 3,29
bl throw_victim
li 0,1
stw 0,16(27)
pair_recovery:
mr 3,31
mr 4,29
bl both_done
cmpwi 3,0
beq tick_done
b finish_pair
pair_fail:
lwz 8,0(27)
cmpwi 8,200
bge finish_pair
mr 3,31
mr 4,29
bl both_done
cmpwi 3,0
beq tick_done
finish_pair:
cmpwi 29,0
beq finish_master
mr 3,29
bl cleanup_hand
finish_master:
mr 3,31
bl cleanup_hand
tick_done:
LEAVE

both_done:
stwu 1,-0x20(1)
mflr 0
stw 0,0x24(1)
stw 4,8(1)
CALL ANIM_REMAINING
cmpwi 3,0
bne not_done
lwz 3,8(1)
CALL ANIM_REMAINING
cmpwi 3,0
bne not_done
li 3,1
b done_result
not_done:
li 3,0
done_result:
lwz 0,0x24(1)
mtlr 0
addi 1,1,0x20
blr

# r27 is the payload state base, established by start_pair or tag_anim.
reset_pair_clock:
li 0,0
stw 0,0(27)
stw 0,8(27)
stw 0,16(27)
li 0,-1
stw 0,4(27)
stw 0,12(27)
blr

begin_squeeze_hand:
ENTER
mr 31,3
mr 29,4
lwz 30,0x2c(31)
CALL CLEAR_HITBOXES
lbz 0,0x221e(30)
andi. 0,0,0xfd
stb 0,0x221e(30)
mr 3,31
mr 4,29
bl change_state
mr 3,31
bl valid_victim
cmpwi 3,0
beq no_grab_mask
li 4,511
b set_grab_mask
no_grab_mask:
li 4,0
set_grab_mask:
mr 3,30
CALL SET_GRAB_MASK
addi 8,27,throw_mh-pair_state
lwz 0,4(30)
cmpwi 0,28
bne set_throw_data
addi 8,8,throw_ch-throw_mh
set_throw_data:
stw 8,0x18(1)
mr 3,31
addi 4,1,0x10
CALL SET_THROW_DATA
LEAVE

# Apply to owned victims directly; the invisible captive's hurtbox need not
# overlap the palm's spatial hitbox. The visitor keeps both capture slots intact.
emit_pummel:
li 4,2
b visit_victims

play_sfx:
lwz 3,0x2c(3)
li 5,127
li 6,64
TAIL PLAY_SFX

cleanup_hand:
ENTER
mr 31,3
lwz 30,0x2c(31)
lwz 27,4(30)
lwz 8,0x10(30)
li 9,385
cmpwi 27,28
bne cleanup_range
li 9,380
cleanup_range:
subf 9,9,8
cmplwi 9,2
ble cleanup_active
cmpwi 27,28
beq cleanup_ch_death
cmpwi 8,344
beq cleanup_dead
cmpwi 8,345
beq cleanup_dead
b cleanup_done
cleanup_ch_death:
cmpwi 8,385
beq cleanup_dead
cmpwi 8,386
bne cleanup_done
cleanup_dead:
mr 3,31
bl release_victim
li 0,0
stw 0,0x2360(30)
stw 0,0x1a58(30)
b cleanup_done
cleanup_active:
mr 3,31
bl release_victim
mr 3,31
CALL CLEAR_HITBOXES
li 0,0
stw 0,0x2360(30)
stw 0,0x1a58(30)
stw 0,0x1a5c(30)
lbz 0,0x221e(30)
andi. 0,0,0xfd
stb 0,0x221e(30)
mr 3,30
li 4,0
CALL SET_GRAB_MASK
mr 3,31
cmpwi 27,28
beq cleanup_ch_idle
CALL MASTER_IDLE
b cleanup_done
cleanup_ch_idle:
CALL CRAZY_IDLE
cleanup_done:
LEAVE

# Match CH to MH after unequal hitlag; events still execute only once on MH.
sync_partner:
stwu 1,-0x40(1)
mflr 0
stw 0,0x44(1)
lfs 0,0x894(28)
fctiwz 0,0
stfd 0,0x30(1)
lwz 8,0x34(1)
subf 8,26,8
cmpwi 8,-1
blt seek_partner
cmpwi 8,1
ble sync_done
seek_partner:
lfs 1,0x894(30)
li 0,0
stw 0,0x30(1)
lfs 3,0x30(1)
lis 0,0x3f80
stw 0,0x34(1)
lfs 2,0x34(1)
mr 3,29
CALL ANIM_SEEK
mr 3,29
CALL ANIM_EVALUATE
sync_done:
lwz 0,0x44(1)
mtlr 0
addi 1,1,0x40
blr

# The native scan overwrites Fighter.victim_gobj while seeking victim #2.
# Look up persistent slots, verify reciprocal ownership, and restore a primary.
valid_victim:
mflr 12
bl get_slots
mtlr 12
lwz 10,0(9)
cmpwi 10,0
beq try_second
lwz 11,0x2c(10)
lwz 11,0x1a58(11)
cmpw 11,3
beq valid_found
try_second:
lwz 10,4(9)
cmpwi 10,0
beq invalid_victim
lwz 11,0x2c(10)
lwz 11,0x1a58(11)
cmpw 11,3
bne invalid_victim
valid_found:
stw 10,0x1a58(8)
mr 3,10
blr
invalid_victim:
li 3,0
blr

release_victim:
li 4,0
b visit_victims
throw_victim:
li 4,1
visit_victims:
ENTER
mr 31,3
mr 29,4
bl get_slots
mr 30,8
mr 28,9
li 27,2
visit_loop:
lwz 26,0(28)
cmpwi 29,2
beq visit_keep_slot
li 0,0
stw 0,0(28)
visit_keep_slot:
cmpwi 26,0
beq visit_next
lwz 8,0x2c(26)
lwz 0,0x1a58(8)
cmpw 0,31
bne visit_next
stw 26,0x1a58(30)
stw 26,0x1a5c(30)
mr 3,31
mr 4,26
cmpwi 29,2
beq visit_pummel
cmpwi 29,0
bne visit_throw
bl release_one
b visit_next
visit_throw:
bl throw_one
b visit_next
visit_pummel:
bl pummel_one
visit_next:
addi 28,28,4
addi 27,27,-1
cmpwi 27,0
bne visit_loop
cmpwi 29,2
beq visit_preserve_capture
li 0,0
stw 0,0x2360(30)
stw 0,0x1a58(30)
stw 0,0x1a5c(30)
b visit_done
visit_preserve_capture:
mr 3,31
bl valid_victim
visit_done:
LEAVE

# r3 = hand, r4 = victim. Use US 1.00 native damage/HUD and flower routines.
pummel_one:
ENTER
mr 31,3
mr 29,4
lwz 30,0x2c(31)
lwz 28,0x2c(29)
PTR 26,pummel_params_mh
lwz 0,4(30)
cmpwi 0,28
bne pummel_parameters
addi 26,26,pummel_params_ch-pummel_params_mh
pummel_parameters:
lwz 27,4(26)
lfs 1,0(26)
mr 3,28
CALL TAKE_DAMAGE
mr 3,31
mr 4,29
lfs 1,0(26)
CALL RECORD_HIT
lwz 8,0x1918(28)
cmpw 8,27
bge pummel_hitlag_set
stw 27,0x1918(28)
pummel_hitlag_set:
lwz 0,12(26)
cmpwi 0,15
bne pummel_feedback
# US 1.00 takes integer damage in r4 (not the 1.02 float argument).
mr 3,29
mr 4,27
CALL APPLY_FLOWER
pummel_feedback:
mr 3,29
lwz 4,8(26)
bl play_sfx
lwz 3,0x5e8(30)
lwz 3,0x120(3)
li 4,0
addi 5,1,0x30
CALL JOINT_WORLD
mr 3,29
addi 4,1,0x30
mr 5,27
PTR 8,hit_effect_floats
lfs 1,0(8)
lfs 2,4(8)
CALL HIT_EFFECT
LEAVE

release_one:
ENTER
mr 3,4
lwz 8,0x2c(3)
lbz 0,0x221e(8)
andi. 0,0,0x7f
stb 0,0x221e(8)
lfs 0,0x2c(8)
fneg 0,0
stfs 0,0x2c(8)
CALL CAPTURE_CUT
LEAVE

throw_one:
ENTER
mr 31,3
lwz 30,0x2c(31)
mr 29,4
lwz 28,0x2c(29)
lwz 0,4(30)
mr 3,29
cmpwi 0,28
beq ch_thrown
CALL MH_THROWN
b apply_throw
ch_thrown:
CALL CH_THROWN
apply_throw:
mr 3,30
li 4,0
CALL SET_GRAB_MASK
mr 3,31
mr 4,29
CALL APPLY_THROW
# Detach beneath the grabbing palm, using its animated bone position.
lwz 3,0x5e8(30)
lwz 3,0x120(3)
li 4,0
addi 5,1,0x30
CALL JOINT_WORLD
PTR 8,slam_drop
lfs 0,0(8)
lfs 1,0x38(30)
fmuls 0,0,1
lfs 1,0x34(1)
fsubs 1,1,0
stfs 1,0x34(1)
lwz 8,0x30(1)
lwz 9,0x34(1)
li 0,0
stw 8,0xb0(28)
stw 9,0xb4(28)
stw 0,0xb8(28)
# Set collision history at the new release point; do not sweep from the palm.
stw 8,0x6f4(28)
stw 9,0x6f8(28)
stw 0,0x6fc(28)
stw 8,0x70c(28)
stw 9,0x710(28)
stw 0,0x714(28)
mr 3,29
li 4,0
li 5,0
CALL LAUNCH_VICTIM
PTR 8,slam_collision
stw 8,0x21a8(28)
LEAVE

# Native stage collision decides contact, including moving/sloped platforms.
# Only the first floor contact launches upward; normal collision resumes after it.
slam_collision:
ENTER
mr 31,3
CALL GROUND_PROBE
cmpwi 3,0
beq slam_no_floor
mr 3,31
CALL GROUND_IMPACT
lwz 30,0x2c(31)
li 0,90
stw 0,0x1848(30)
mr 3,30
CALL SET_AIRBORNE
mr 3,31
li 4,0
li 5,1
CALL LAUNCH_VICTIM
slam_no_floor:
LEAVE

# Data use no absolute relocations. Pummel following word sets victim-only filter.
# watchdog, last animation frame, pulse index, clear deadline, throw done
pair_state:
.long 0
.long -1
.long 0
.long -1
.long 0
pulse_frames:
.long PUMMEL_1
.long PUMMEL_2
.long PUMMEL_3
.long PUMMEL_4
.long PUMMEL_5
victim_slots:
.long 0
.long 0
.long 0
.long 0
slam_drop:
.long SLAM_DROP_BITS
empty_script:
.long 0
grab_mh:
GRAB_DATA_MH
grab_ch:
GRAB_DATA_CH
pummel_params_mh:
PUMMEL_PARAMS_MH
pummel_params_ch:
PUMMEL_PARAMS_CH
hit_effect_floats:
.long 0
.long 0x3f800000
throw_mh:
THROW_DATA_MH
throw_ch:
THROW_DATA_CH
runtime_end:
nop
b runtime_exit

# Attach the captured fighter's model root to the hand's TransN2 bone.
# Its native accessory callback updates Fighter.cur_pos from the attached root,
# so the name tag follows the actual fighter rather than remaining at spawn.
attach_captured:
stwu 1,-0x40(1)
mflr 0
stw 0,0x44(1)
bl get_slots
lwz 10,0x1a58(8)
stw 8,0x28(1)
stw 9,0x2c(1)
stw 10,0x30(1)
cmpwi 10,0
beq attach_captured_done
lwz 11,0x2c(10)
mr 3,11
mr 4,8
CALL ATTACH_VICTIM
lwz 10,0x30(1)
lwz 11,0x2c(10)
lis 12,0x800d
ori 12,12,0xb018
stw 12,0x21b0(11)
attach_captured_done:
lwz 8,0x28(1)
lwz 9,0x2c(1)
lwz 10,0x30(1)
lwz 0,0x44(1)
mtlr 0
addi 1,1,0x40
blr
runtime_exit:
nop
