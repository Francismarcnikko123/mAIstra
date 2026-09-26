class BatchQueue {
  final List<String> paths;
  int _index = 0;

  BatchQueue(this.paths) : assert(paths.isNotEmpty);

  String get current => paths[_index];
  int get position => _index + 1;
  int get total => paths.length;
  bool get isDone => _index >= paths.length;

  void advance() {
    _index++;
  }
}
