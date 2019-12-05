int main() {
  for(int i = 120; i < 130; i++) {
    write(1, &i, sizeof(i));
  }
}
