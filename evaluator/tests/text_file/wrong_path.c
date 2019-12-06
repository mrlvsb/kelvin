#include <stdio.h>

int main() {
    FILE* f = fopen("test2.txt", "w");
    fprintf(f, "hello file!\nfoo bar\n");
    fclose(f);
    return 0;
}
