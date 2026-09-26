import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/question_choice.dart';

class QuestionRepository {
  final SupabaseClient _client;

  QuestionRepository([SupabaseClient? client])
    : _client = client ?? Supabase.instance.client;

  /// Questions that have a section and a number and whose model answer has
  /// passed validation. Unsectioned or unvalidated questions never reach the
  /// phone.
  Future<List<QuestionChoice>> fetchReadyQuestions() async {
    final rows = await _client
        .from('question_section_items')
        .select(
          'number, '
          'question_sections!inner(name, position), '
          'questions!inner(id, question_name, can_publish)',
        )
        .eq('questions.can_publish', true);
    return rows.map(QuestionChoice.fromRow).toList();
  }
}
