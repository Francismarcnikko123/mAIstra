import 'package:flutter_test/flutter_test.dart';
import 'package:maistra_mobile/utils/batch_review.dart';
import 'package:maistra_mobile/utils/quality_check.dart';

QualityResult _good() => QualityResult(passed: true, issues: []);
QualityResult _bad(String issue) => QualityResult(passed: false, issues: [issue]);

void main() {
  group('BatchReview', () {
    test('splits items into good and bad by result.passed', () {
      final good = BatchItem(path: 'good.jpg', result: _good());
      final bad = BatchItem(path: 'bad.jpg', result: _bad('Too dark'));
      final review = BatchReview([good, bad]);

      expect(review.goodItems, [good]);
      expect(review.badItems, [bad]);
    });

    test("toggleSelected flips only that item's selected flag", () {
      final a = BatchItem(path: 'a.jpg', result: _good());
      final b = BatchItem(path: 'b.jpg', result: _good());
      final review = BatchReview([a, b]);

      review.toggleSelected(a);

      expect(a.selected, false);
      expect(b.selected, true);
    });

    test('selectedGoodItems returns only checked good items', () {
      final checkedGood = BatchItem(path: 'a.jpg', result: _good());
      final uncheckedGood =
          BatchItem(path: 'b.jpg', result: _good(), selected: false);
      final bad = BatchItem(path: 'c.jpg', result: _bad('Blurry'));
      final review = BatchReview([checkedGood, uncheckedGood, bad]);

      expect(review.selectedGoodItems, [checkedGood]);
    });

    test('discard removes the item from the batch', () {
      final item = BatchItem(path: 'a.jpg', result: _good());
      final review = BatchReview([item]);

      review.discard(item);

      expect(review.items, isEmpty);
      expect(review.isEmpty, true);
    });

    test('replace swaps an item and re-buckets it by the new result', () {
      final oldItem = BatchItem(path: 'a.jpg', result: _bad('Blurry'));
      final review = BatchReview([oldItem]);
      final newItem = BatchItem(path: 'a-retaken.jpg', result: _good());

      review.replace(oldItem, newItem);

      expect(review.badItems, isEmpty);
      expect(review.goodItems, [newItem]);
    });

    test('isEmpty is false when items remain', () {
      final review = BatchReview([BatchItem(path: 'a.jpg', result: _good())]);
      expect(review.isEmpty, false);
    });
  });
}
