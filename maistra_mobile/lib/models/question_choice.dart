/// A validated, sectioned question a student can capture an answer for.
class QuestionChoice {
  final String id;
  final String name;
  final String sectionName;
  final int sectionPosition;
  final int number;

  const QuestionChoice({
    required this.id,
    required this.name,
    required this.sectionName,
    required this.sectionPosition,
    required this.number,
  });

  /// `Q2 · Sum of two numbers` — shown in the capture app bar.
  String get shortLabel => 'Q$number · $name';

  /// `Basic · Q2 · Sum of two numbers` — the label used on the web too.
  String get fullLabel => '$sectionName · $shortLabel';

  /// Parses one row of the picker query in `QuestionRepository`.
  factory QuestionChoice.fromRow(Map<String, dynamic> row) {
    final section = row['question_sections'] as Map<String, dynamic>;
    final question = row['questions'] as Map<String, dynamic>;
    return QuestionChoice(
      id: question['id'] as String,
      name: (question['question_name'] as String).trim(),
      sectionName: (section['name'] as String).trim(),
      sectionPosition: (section['position'] as num?)?.toInt() ?? 0,
      number: (row['number'] as num).toInt(),
    );
  }
}

class QuestionSection {
  final String name;
  final List<QuestionChoice> questions;

  const QuestionSection(this.name, this.questions);
}

/// Groups by section (section position, then name) and sorts each section
/// by question number.
List<QuestionSection> groupBySection(Iterable<QuestionChoice> choices) {
  final bySection = <String, List<QuestionChoice>>{};
  for (final c in choices) {
    bySection.putIfAbsent(c.sectionName, () => []).add(c);
  }
  final sections = bySection.entries.map((e) {
    final qs = List<QuestionChoice>.of(e.value)
      ..sort((a, b) => a.number.compareTo(b.number));
    return QuestionSection(e.key, qs);
  }).toList();
  sections.sort((a, b) {
    final byPos = a.questions.first.sectionPosition.compareTo(
      b.questions.first.sectionPosition,
    );
    return byPos != 0 ? byPos : a.name.compareTo(b.name);
  });
  return sections;
}
