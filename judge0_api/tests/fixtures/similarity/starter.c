int clamp_positive(int value) {
    if (value < 0) {
        return 0;
    }
    return value;
}
