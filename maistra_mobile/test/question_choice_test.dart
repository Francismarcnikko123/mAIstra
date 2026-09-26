import 'package:flutter_test/flutter_test.dart';
import 'package:maistra_mobile/models/question_choice.dart';

QuestionChoice _q(String section, int pos, int number, [String? name]) =>
    QuestionChoice(
      id: '$section-$number',
      name: name ?? 'Question $number',
      sectionName: section,
      sectionPosition: pos,
      number: number,
    );

void main() {
  test('labels match the web format', () {
    final q = _q('Basic', 0, 2, 'Sum of two numbers');
    expect(q.shortLabel, 'Q2 · Sum of two numbers');
    expect(q.fullLabel, 'Basic · Q2 · Sum of two numbers');
  });

  test('groups by section position and sorts by number', () {
    final sections = groupBySection([
      _q('Loops', 1, 3),
      _q('Basic', 0, 2),
      _q('Loops', 1, 1),
      _q('Basic', 0, 1),
    ]);
    expect(sections.map((s) => s.name), ['Basic', 'Loops']);
    expect(sections[1].questions.map((q) => q.number), [1, 3]);
  });

  test('sections with equal position sort by name', () {
    final sections = groupBySection([_q('Zeta', 0, 1), _q('Alpha', 0, 1)]);
    expect(sections.map((s) => s.name), ['Alpha', 'Zeta']);
  });

  test('empty input gives no sections', () {
    expect(groupBySection(const []), isEmpty);
  });

  test('fromRow parses the picker query shape', () {
    final q = QuestionChoice.fromRow({
      'number': 4,
      'question_sections': {'name': 'Basic ', 'position': 2},
      'questions': {
        'id': 'abc',
        'question_name': 'Count vowels',
        'can_publish': true,
      },
    });
    expect(q.fullLabel, 'Basic · Q4 · Count vowels');
    expect(q.sectionPosition, 2);
  });
}
