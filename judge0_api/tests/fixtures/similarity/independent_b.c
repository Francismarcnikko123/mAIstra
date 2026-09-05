int sum_to(int limit) {
    if (limit <= 0) {
        return 0;
    }
    return (limit * (limit + 1)) / 2;
}
