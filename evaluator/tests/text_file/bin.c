#include <stdio.h>

int main() {
    FILE *f = fopen("test.txt", "wb+");
    char val = 180;
    fwrite(&val, 1, 1, f);
}