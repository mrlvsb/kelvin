#include <stdio.h>

int main() {
    char line[128];
    fgets(line, sizeof(line), stdin);
    printf("%s", line);
    return 0;
}
