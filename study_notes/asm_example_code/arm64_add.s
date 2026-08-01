// GNU AArch64 syntax: integer addition and return from a leaf function.
.text
.global add_two
.type add_two, %function
add_two:
    add     w0, w0, w1
    ret
.size add_two, .-add_two
