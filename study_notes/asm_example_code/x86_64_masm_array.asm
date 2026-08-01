; MASM/ml64: sum four 32-bit array elements with base + index addressing.
EXTERN ExitProcess:PROC

.data
values DWORD 3, 1, 4, 1

.code
main PROC
    sub     rsp, 28h
    lea     rdx, values
    xor     eax, eax
    xor     ecx, ecx             ; index = 0
sum_loop:
    add     eax, DWORD PTR [rdx + rcx * 4]
    inc     ecx
    cmp     ecx, 4
    jl      sum_loop
    mov     ecx, eax             ; return sum as process exit code
    call    ExitProcess
main ENDP
END
