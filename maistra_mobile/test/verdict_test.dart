import 'package:flutter_test/flutter_test.dart';
import 'package:maistra_mobile/utils/quality_check.dart';
import 'package:maistra_mobile/utils/verdict.dart';

const _metrics = QualityMetrics(
  blurScore: 1000,
  darkClipFraction: 0,
  brightClipFraction: 0,
  contrastScore: 100,
  shadowScore: 0,
  skewAngleDeg: 0,
);

QualityResult _result(
  QualityDecision d, [
  List<String> issues = const [],
  bool autoFixed = false,
]) => QualityResult(
  decision: d,
  issues: issues,
  metrics: _metrics,
  autoFixed: autoFixed,
);

void main() {
  group('verdictOf / gateResultValue', () {
    test('maps each gate decision', () {
      expect(verdictOf(_result(QualityDecision.pass)), Verdict.pass);
      expect(verdictOf(_result(QualityDecision.fixable)), Verdict.fixable);
      expect(verdictOf(_result(QualityDecision.retake)), Verdict.retake);
    });

    test('an auto-corrected PASS is stored as FIXABLE', () {
      final r = _result(QualityDecision.pass, const [], true);
      expect(gateResultValue(verdictOf(r)), 'FIXABLE');
    });

    test('stored values are upper case', () {
      expect(gateResultValue(Verdict.pass), 'PASS');
      expect(gateResultValue(Verdict.retake), 'RETAKE');
    });
  });

  group('verdictCopy', () {
    test('PASS reads as the spec copy', () {
      final c = verdictCopy(_result(QualityDecision.pass));
      expect(c.heading, 'Photo is good');
      expect(c.sentence, 'Nothing needs changing.');
    });

    test('splits a gate issue string into heading and sentence', () {
      final c = verdictCopy(_result(
        QualityDecision.retake,
        ['Too blurry — hold the camera steady'],
      ));
      expect(c.heading, 'Too blurry');
      expect(c.sentence, 'Hold the camera steady.');
      expect(c.more, isEmpty);
    });

    test('RETAKE leads with the retake issue, not an earlier fixable one', () {
      final c = verdictCopy(_result(QualityDecision.retake, [
        'Low contrast / faded ink — contrast will be auto-enhanced',
        'Extreme shadow across page — reposition or use even lighting',
      ]));
      expect(c.heading, 'Extreme shadow across page');
      expect(c.more.single,
          'Low contrast / faded ink: contrast will be auto-enhanced.');
    });

    test('corrected page with no remaining issues gets a generic sentence',
        () {
      final c = verdictCopy(_result(QualityDecision.pass, const [], true));
      expect(c.heading, 'Auto-corrected');
      expect(c.sentence, isNotEmpty);
    });

    test('issue with no separator falls back to a verdict heading', () {
      final c = verdictCopy(_result(QualityDecision.retake, ['Unreadable']));
      expect(c.heading, 'Retake this page');
      expect(c.sentence, 'Unreadable.');
    });
  });
}
