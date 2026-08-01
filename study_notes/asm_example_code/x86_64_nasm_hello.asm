; NASM win64 syntax: external call and global entry symbol.
default rel
extern ExitProcess
global main

section .text
main:
    sub     rsp, 28h
    xor     ecx, ecx
    call    ExitProcess
    add     rsp, 28h
    ret
