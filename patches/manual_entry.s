# Hook CH's native team-wait initializer, called after its movement finishes.
# A TagGrab request automatically starts MH's movement. Other three requests
# execute the original initializer without starting or replacing their attacks.
ENTER
mr 31,3
lwz 30,0x2c(31)
lwz 0,0x2250(30)
cmpwi 0,380
bne manual_wait_native
li 3,27
CALL GET_HAND
cmpwi 3,0
beq manual_wait_abort
mr 29,3
lwz 28,0x2c(29)
lbz 0,0x221f(28)
andi. 0,0,0x10
bne manual_wait_abort
lwz 8,0x10(28)
addi 0,8,-341
cmplwi 0,1
ble manual_start_master
addi 0,8,-344
cmplwi 0,1
ble manual_wait_abort
# MH is still finishing another move. Keep CH's arrival callback active so it
# retries on the next collision tick, rather than entering an unserviced wait.
LEAVE

manual_start_master:
lwz 8,0x10c(28)
lwz 8,4(8)
lwz 9,0x13c(8)
lwz 10,0x140(8)
stw 9,0x30(1)
stw 10,0x34(1)
li 0,0
stw 0,0x38(1)
mr 3,29
PTR 4,start_pair
addi 5,1,0x30
CALL MASTER_MOVE

# Native CH state 384 is installed before any later MH arrival callback can
# run. Preserve the incoming GObj and replay the overwritten mflr instruction.
manual_wait_native:
mr 3,31
LEAVE_HOOK
mflr 0
b runtime_end
manual_wait_abort:
mr 3,31
CALL CRAZY_IDLE
LEAVE
