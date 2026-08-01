#include <stdio.h>

static int xor_bit(int left, int right) {
    return (left != right) ? 1 : 0;
}

int main(void) {
    puts("left right | xor");
    puts("-----------------");
    for (int left = 0; left <= 1; ++left) {
        for (int right = 0; right <= 1; ++right) {
            printf("  %d    %d   |  %d\n", left, right, xor_bit(left, right));
        }
    }
    return 0;
}
