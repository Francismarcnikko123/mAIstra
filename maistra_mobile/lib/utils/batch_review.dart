import 'quality_check.dart';

class BatchItem {
  String path;
  QualityResult result;
  bool selected;

  BatchItem({required this.path, required this.result, this.selected = true});
}

class BatchReview {
  final List<BatchItem> items;

  BatchReview(this.items);

  List<BatchItem> get goodItems => items.where((i) => i.result.passed).toList();
  List<BatchItem> get badItems => items.where((i) => !i.result.passed).toList();
  List<BatchItem> get selectedGoodItems =>
      goodItems.where((i) => i.selected).toList();
  bool get isEmpty => items.isEmpty;

  void discard(BatchItem item) => items.remove(item);
  void toggleSelected(BatchItem item) => item.selected = !item.selected;

  void replace(BatchItem oldItem, BatchItem newItem) {
    final index = items.indexOf(oldItem);
    if (index != -1) items[index] = newItem;
  }
}
