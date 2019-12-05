#include <stdio.h>

int main() {
    FILE* f = fopen("test.txt", "w");
    fprintf(f, "hello file!\nfoo bar\n");
    fclose(f);
    return 0;
}
