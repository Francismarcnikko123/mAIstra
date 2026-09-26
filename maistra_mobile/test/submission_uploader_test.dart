import 'dart:io';
import 'dart:math';
import 'package:flutter_test/flutter_test.dart';
import 'package:maistra_mobile/models/captured_page.dart';
import 'package:maistra_mobile/models/question_choice.dart';
import 'package:maistra_mobile/services/submission_uploader.dart';
import 'package:maistra_mobile/utils/batch_id.dart';
import 'package:maistra_mobile/utils/quality_check.dart';

const _question = QuestionChoice(
  id: 'q-sum',
  name: 'Sum of two numbers',
  sectionName: 'Basic',
  sectionPosition: 0,
  number: 1,
);

CapturedPage _page(QualityDecision d, {bool autoFixed = false}) => CapturedPage(
  file: File('page.jpg'),
  quality: QualityResult(
    decision: d,
    issues: const [],
    autoFixed: autoFixed,
    metrics: const QualityMetrics(
      blurScore: 0,
      darkClipFraction: 0,
      brightClipFraction: 0,
      contrastScore: 0,
      shadowScore: 0,
      skewAngleDeg: 0,
    ),
  ),
);

final _uuidV4 = RegExp(
  r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
);

void main() {
  group('newBatchId', () {
    test('is a version-4 UUID Postgres accepts', () {
      for (var i = 0; i < 200; i++) {
        expect(newBatchId(), matches(_uuidV4));
      }
    });

    test('is different for every submit', () {
      final ids = {for (var i = 0; i < 500; i++) newBatchId()};
      expect(ids, hasLength(500));
    });

    test('is reproducible with a seeded random source', () {
      expect(newBatchId(Random(7)), newBatchId(Random(7)));
    });
  });

  group('submissionRow', () {
    test('every page of one submit carries the same batch_id', () {
      final batchId = newBatchId();
      final rows = [
        SubmissionUploader.submissionRow(
          'u1',
          _question,
          _page(QualityDecision.pass),
          batchId,
        ),
        SubmissionUploader.submissionRow(
          'u2',
          _question,
          _page(QualityDecision.fixable),
          batchId,
        ),
      ];
      expect(rows.map((r) => r['batch_id']).toSet(), {batchId});
      expect(rows.map((r) => r['question_id']).toSet(), {'q-sum'});
    });

    test('sends only what the phone owns; OCR fields stay empty', () {
      final row = SubmissionUploader.submissionRow(
        'https://example.test/p.jpg',
        _question,
        _page(QualityDecision.pass, autoFixed: true),
        'batch',
      );
      expect(row, {
        'image_url': 'https://example.test/p.jpg',
        'question_id': 'q-sum',
        'gate_result': 'FIXABLE',
        'batch_id': 'batch',
        'status': 'pending',
      });
    });
  });
}
