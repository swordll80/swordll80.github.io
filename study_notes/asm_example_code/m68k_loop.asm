; Motorola 68000: add 1..d0 into d1. Syntax is intentionally explicit.
        section .text
        xdef    sum_to_n
sum_to_n:
        moveq   #0,d1
        moveq   #1,d2
loop:
        cmp.l   d0,d2
        bhi     done
        add.l   d2,d1
        addq.l  #1,d2
        bra     loop
done:
        rts
