// main.c
int main() {
    int a = 10;       // Type I (addi)
    int b = 20;       // Type I (addi)
    int c = 0;

    c = a + b;        // Type R (add)

    if (c == 30) {    // Type B (beq/bne)
        c = 1;
    } else {
        c = 2;
    }

    return 0;
}