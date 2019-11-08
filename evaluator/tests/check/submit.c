#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
  int a = atoi(argv[1]);
  int b = atoi(argv[2]);

  printf("%d\n", rand() % 10);

  return 0;
}
