#include <stdio.h>

int main() {
    FILE *a = fopen("first.txt", "w");
    FILE *b = fopen("second.txt", "w");

    fprintf(a, "first\n");
    fprintf(b, "second\n");
}