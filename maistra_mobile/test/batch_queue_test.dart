import 'package:flutter_test/flutter_test.dart';
import 'package:maistra_mobile/utils/batch_queue.dart';

void main() {
  group('BatchQueue', () {
    test('starts at the first item with position 1', () {
      final batch = BatchQueue(['a.jpg', 'b.jpg', 'c.jpg']);
      expect(batch.current, 'a.jpg');
      expect(batch.position, 1);
      expect(batch.total, 3);
      expect(batch.isDone, false);
    });

    test('advance moves to the next item', () {
      final batch = BatchQueue(['a.jpg', 'b.jpg', 'c.jpg']);
      batch.advance();
      expect(batch.current, 'b.jpg');
      expect(batch.position, 2);
      expect(batch.isDone, false);
    });

    test('isDone becomes true after advancing past the last item', () {
      final batch = BatchQueue(['a.jpg', 'b.jpg']);
      batch.advance();
      batch.advance();
      expect(batch.isDone, true);
    });

    test('a single-item batch is done after one advance', () {
      final batch = BatchQueue(['only.jpg']);
      expect(batch.isDone, false);
      batch.advance();
      expect(batch.isDone, true);
    });
  });
}
