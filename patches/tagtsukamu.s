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

on_grab:
lwz 3,0x2c(3)
li 0,1
stw 0,0x2360(3)
lbz 0,0x221e(3)
andi. 0,0,0xfd
stb 0,0x221e(3)
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
blt finish_secondary
cmpwi 0,387
ble tick_done
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
clear_due:
lwz 8,12(27)
cmpwi 8,0
blt pulse_due
cmpw 26,8
blt pulse_due
mr 3,31
CALL CLEAR_HITBOXES
mr 3,29
CALL CLEAR_HITBOXES
li 0,-1
stw 0,12(27)
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
addi 8,26,ACTIVE_FRAMES
stw 8,12(27)
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

emit_pummel:
ENTER
mr 31,3
bl valid_victim
cmpwi 3,0
beq emit_done
lwz 8,0x2c(31)
lwz 0,4(8)
addi 8,27,pummel_mh-pair_state
cmpwi 0,28
bne create_pummel
addi 8,8,pummel_ch-pummel_mh
create_pummel:
stw 8,0x18(1)
mr 3,31
addi 4,1,0x10
CALL CREATE_HITBOX
emit_done:
LEAVE

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

# Returns victim GObj only if its reciprocal captor is this hand.
valid_victim:
lwz 8,0x2c(3)
lwz 9,0x1a58(8)
cmpwi 9,0
beq invalid_victim
lwz 10,0x2c(9)
cmpwi 10,0
beq invalid_victim
lwz 10,0x1a58(10)
cmpw 10,3
bne invalid_victim
mr 3,9
blr
invalid_victim:
li 3,0
blr

release_victim:
ENTER
bl valid_victim
cmpwi 3,0
beq release_done
lwz 8,0x2c(3)
lbz 0,0x221e(8)
andi. 0,0,0x7f
stb 0,0x221e(8)
lfs 0,0x2c(8)
fneg 0,0
stfs 0,0x2c(8)
CALL CAPTURE_CUT
release_done:
LEAVE

throw_victim:
ENTER
mr 31,3
lwz 30,0x2c(31)
bl valid_victim
cmpwi 3,0
beq throw_done
mr 29,3
lwz 28,0x2c(29)
lwz 0,4(30)
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
lfs 0,0x1844(28)
fneg 0,0
stfs 0,0x1844(28)
mr 3,29
li 4,0
li 5,0
CALL LAUNCH_VICTIM
li 0,0
stw 0,0x2360(30)
stw 0,0x1a58(30)
stw 0,0x1a5c(30)
throw_done:
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
empty_script:
.long 0
grab_mh:
GRAB_DATA_MH
grab_ch:
GRAB_DATA_CH
pummel_mh:
PUMMEL_DATA_MH
pummel_ch:
PUMMEL_DATA_CH
throw_mh:
THROW_DATA_MH
throw_ch:
THROW_DATA_CH
runtime_end:
nop
