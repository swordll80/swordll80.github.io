# MIPS: load two constants, add them, and return through the standard register.
.text
.globl add_two
.ent add_two
add_two:
    li      $t0, 7
    li      $t1, 5
    addu    $v0, $t0, $t1
    jr      $ra
    nop
.end add_two
