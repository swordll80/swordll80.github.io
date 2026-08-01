#include <stdio.h>

static void increment_all(int *values, size_t count) {
    for (size_t i = 0; i < count; ++i) {
        values[i] += 1;
    }
}

int main(void) {
    int values[] = {10, 20, 30, 40};
    size_t count = sizeof(values) / sizeof(values[0]);

    increment_all(values, count);
    for (size_t i = 0; i < count; ++i) {
        printf("values[%zu] = %d, address = %p\n",
               i, values[i], (void *)&values[i]);
    }
    return 0;
}
