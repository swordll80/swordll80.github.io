; MASM/ml64: smallest Windows x64 console program.
EXTERN ExitProcess:PROC

.code
main PROC
    sub     rsp, 28h             ; shadow space + stack alignment
    xor     ecx, ecx             ; ExitProcess(0)
    call    ExitProcess
main ENDP
END
