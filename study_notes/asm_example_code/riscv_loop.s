# RISC-V: sum integers 1..a0 and return the result in a0.
.text
.globl sum_to_n
.type sum_to_n, @function
sum_to_n:
    li      t0, 0
    li      t1, 1
sum_loop:
    bgt     t1, a0, sum_done
    add     t0, t0, t1
    addi    t1, t1, 1
    j       sum_loop
sum_done:
    mv      a0, t0
    ret
