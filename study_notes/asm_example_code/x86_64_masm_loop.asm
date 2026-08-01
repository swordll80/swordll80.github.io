; MASM/ml64: count from 0 to 9 using compare and conditional jump.
EXTERN ExitProcess:PROC

.code
main PROC
    sub     rsp, 28h
    xor     eax, eax             ; counter = 0
count_loop:
    inc     eax
    cmp     eax, 10
    jl      count_loop
    xor     ecx, ecx
    call    ExitProcess
main ENDP
END
