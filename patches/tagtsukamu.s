# Position-independent runtime. Expanded by tools/build_gecko.py for Keystone PPC32.
# r31 = current GObj, r30 = Fighter, r27 = kind (27 MH, 28 CH).
# Only the three restored states use mv+8 (Fighter+0x2348) as a timer.

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
PTR 10,grab_mh
PTR 11,tag_anim
cmpwi 27,28
beq install_ch
stw 10,0x1fd4(8)
stw 9,0x1fec(8)
lis 8,0x803d
ori 8,8,0x2104
b install_callbacks
install_ch:
PTR 10,grab_ch
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
lwz 3,0x2c(31)
li 0,0
stw 0,0x2348(3)
LEAVE

tag_anim:
ENTER
mr 31,3
lwz 30,0x2c(31)
lwz 27,4(30)
lwz 8,0x2348(30)
addi 8,8,1
stw 8,0x2348(30)
cmpwi 8,420
bge abort_tag
li 3,28
cmpwi 27,28
bne find_partner
li 3,27
find_partner:
CALL GET_HAND
cmpwi 3,0
beq abort_tag
lwz 8,0x2c(3)
lbz 0,0x221f(8)
andi. 0,0,0x10
bne abort_tag
lwz 0,0x10(8)
cmpwi 27,28
beq check_mh_death
cmpwi 0,385
beq abort_tag
cmpwi 0,386
beq abort_tag
b dispatch_state
check_mh_death:
cmpwi 0,344
beq abort_tag
cmpwi 0,345
beq abort_tag
dispatch_state:
lwz 0,0x10(30)
li 8,385
cmpwi 27,28
bne dispatch_compare
li 8,380
dispatch_compare:
cmpw 0,8
beq grab_anim
addi 8,8,1
cmpw 0,8
beq squeeze_anim
b fail_anim

grab_anim:
lwz 0,0x2348(30)
cmpwi 0,180
bge finish_grab
mr 3,31
CALL ANIM_REMAINING
cmpwi 3,0
bne tick_done
finish_grab:
mr 3,31
CALL CLEAR_HITBOXES
lbz 0,0x221e(30)
andi. 0,0,0xfd
stb 0,0x221e(30)
mr 3,31
bl valid_victim
cmpwi 3,0
beq go_fail
mr 3,31
li 4,386
cmpwi 27,28
bne begin_squeeze
li 4,381
begin_squeeze:
bl change_state
li 0,1
stw 0,0x2360(30)
mr 3,30
li 4,511
CALL SET_GRAB_MASK
PTR 8,throw_mh
cmpwi 27,28
bne init_throw_data
PTR 8,throw_ch
init_throw_data:
stw 8,0x18(1)
mr 3,31
addi 4,1,0x10
CALL SET_THROW_DATA
b tick_done
go_fail:
li 0,0
stw 0,0x2360(30)
stw 0,0x1a58(30)
mr 3,31
li 4,387
cmpwi 27,28
bne begin_fail
li 4,382
begin_fail:
bl change_state
b tick_done

squeeze_anim:
lwz 0,0x2360(30)
cmpwi 0,0
beq after_throw
mr 3,31
bl valid_victim
cmpwi 3,0
beq abort_tag
lwz 0,0x2348(30)
cmpwi 0,PUMMEL_1
beq spawn_pummel
cmpwi 0,PUMMEL_2
beq spawn_pummel
cmpwi 0,PUMMEL_3
beq spawn_pummel
cmpwi 0,PUMMEL_4
beq spawn_pummel
cmpwi 0,PUMMEL_5
beq spawn_pummel
cmpwi 0,CLEAR_1
beq clear_pummel
cmpwi 0,CLEAR_2
beq clear_pummel
cmpwi 0,CLEAR_3
beq clear_pummel
cmpwi 0,CLEAR_4
beq clear_pummel
cmpwi 0,CLEAR_5
beq clear_pummel
cmpwi 0,THROW_TICK
blt tick_done
mr 3,31
bl throw_victim
b tick_done
spawn_pummel:
mr 3,31
CALL CLEAR_HITBOXES
PTR 8,pummel_mh
cmpwi 27,28
bne create_pummel
PTR 8,pummel_ch
create_pummel:
stw 8,0x18(1)
mr 3,31
addi 4,1,0x10
CALL CREATE_HITBOX
b tick_done
clear_pummel:
mr 3,31
CALL CLEAR_HITBOXES
b tick_done
after_throw:
mr 3,31
CALL ANIM_REMAINING
cmpwi 3,0
beq abort_tag
lwz 0,0x2348(30)
cmpwi 0,300
bge abort_tag
b tick_done
fail_anim:
mr 3,31
CALL ANIM_REMAINING
cmpwi 3,0
beq abort_tag
lwz 0,0x2348(30)
cmpwi 0,180
blt tick_done

abort_tag:
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
beq return_ch
CALL MASTER_IDLE
b tick_done
return_ch:
CALL CRAZY_IDLE
tick_done:
LEAVE

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
