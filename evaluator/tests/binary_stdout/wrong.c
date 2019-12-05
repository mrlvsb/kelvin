int main() {
  for(int i = 0; i < 10; i++) {
    write(1, &i, sizeof(i));
  }
}
