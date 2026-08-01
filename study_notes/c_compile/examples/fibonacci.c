#include <stdio.h>

static unsigned long long fibonacci(unsigned int n) {
    unsigned long long a = 0;
    unsigned long long b = 1;

    for (unsigned int i = 0; i < n; ++i) {
        unsigned long long next = a + b;
        a = b;
        b = next;
    }
    return a;
}

int main(void) {
    for (unsigned int i = 0; i < 12; ++i) {
        printf("F(%u) = %llu\n", i, fibonacci(i));
    }
    return 0;
}
