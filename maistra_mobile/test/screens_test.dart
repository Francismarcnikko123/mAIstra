import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:maistra_mobile/models/captured_page.dart';
import 'package:maistra_mobile/models/question_choice.dart';
import 'package:maistra_mobile/screens/batch_review_screen.dart';
import 'package:maistra_mobile/screens/question_picker_screen.dart';
import 'package:maistra_mobile/services/question_repository.dart';
import 'package:maistra_mobile/theme/app_theme.dart';
import 'package:maistra_mobile/utils/quality_check.dart';

class _FakeRepo implements QuestionRepository {
  final List<QuestionChoice> choices;
  _FakeRepo(this.choices);

  @override
  Future<List<QuestionChoice>> fetchReadyQuestions() async => choices;
}

const _question = QuestionChoice(
  id: 'q2',
  name: 'Sum of two numbers',
  sectionName: 'Basic',
  sectionPosition: 0,
  number: 2,
);

CapturedPage _page(String name, QualityDecision d, [List<String>? issues]) =>
    CapturedPage(
      file: File(name),
      quality: QualityResult(
        decision: d,
        issues: issues ?? const [],
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

Widget _app(Widget home) =>
    MaterialApp(theme: buildAppTheme(Brightness.light), home: home);

FilledButton _button(WidgetTester tester, String label) => tester
    .widget<FilledButton>(find.ancestor(
      of: find.text(label),
      matching: find.byWidgetPredicate((w) => w is FilledButton),
    ));

void main() {
  group('QuestionPickerScreen', () {
    testWidgets('shows the empty state with a disabled start button',
        (tester) async {
      await tester.pumpWidget(
          _app(QuestionPickerScreen(repository: _FakeRepo(const []))));
      await tester.pumpAndSettle();

      expect(find.text('No questions ready'), findsOneWidget);
      expect(
        find.text('Ask your teacher to validate a question in the web dashboard.'),
        findsOneWidget,
      );
      expect(_button(tester, 'Start capturing').onPressed, isNull);
    });

    testWidgets('start is enabled only after choosing a question',
        (tester) async {
      await tester.pumpWidget(
          _app(QuestionPickerScreen(repository: _FakeRepo(const [_question]))));
      await tester.pumpAndSettle();

      expect(find.text('Basic'), findsOneWidget);
      expect(_button(tester, 'Start capturing').onPressed, isNull);

      await tester.tap(find.text('Sum of two numbers'));
      await tester.pump();
      expect(_button(tester, 'Start capturing').onPressed, isNotNull);
    });
  });

  group('BatchReviewScreen', () {
    testWidgets('a RETAKE page blocks submit with an inline reason',
        (tester) async {
      final pages = [
        _page('a.jpg', QualityDecision.pass),
        _page('b.jpg', QualityDecision.retake,
            ['Too blurry — hold the camera steady']),
      ];
      await tester.pumpWidget(
          _app(BatchReviewScreen(question: _question, pages: pages)));

      expect(find.text('Q2 · Sum of two numbers'), findsOneWidget);
      expect(find.text('Too blurry'), findsOneWidget);
      expect(find.text('Retake or remove the page marked Retake to submit.'),
          findsOneWidget);
      expect(_button(tester, 'Submit answer').onPressed, isNull);

      // Removing the bad page unblocks submit.
      await tester.tap(find.text('Remove').last);
      await tester.pump();
      expect(pages, hasLength(1));
      expect(_button(tester, 'Submit answer').onPressed, isNotNull);
    });

    testWidgets('no pages blocks submit', (tester) async {
      await tester.pumpWidget(
          _app(BatchReviewScreen(question: _question, pages: [])));
      expect(find.text('Add at least one page to submit.'), findsOneWidget);
      expect(_button(tester, 'Submit answer').onPressed, isNull);
    });
  });
}
