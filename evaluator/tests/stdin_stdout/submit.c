#include <stdio.h>

int main() {
    char line[128];
    fgets(line, sizeof(line), stdin);
    for(int i = 0; i < strlen(line); i++) {
      if(line[i] >= 'a' && line[i] <= 'z') {
        line[i] += 'A' - 'a';
      }
    }
    printf("%s", line);
    return 0;
}
