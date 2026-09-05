int sum_to(int maximum) {
    int accumulator = 0;
    for (int current = 1; current <= maximum; current++) {
        accumulator += current;
    }
    return accumulator;
}
