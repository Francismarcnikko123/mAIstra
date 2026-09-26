import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/captured_page.dart';
import '../models/question_choice.dart';
import '../utils/verdict.dart';

class SubmissionUploader {
  final SupabaseClient _client;

  SubmissionUploader([SupabaseClient? client])
    : _client = client ?? Supabase.instance.client;

  /// Uploads every page of one answer, all linked to [question]. Callers
  /// must not pass a RETAKE page; the review screen blocks submit first.
  Future<void> submit(QuestionChoice question, List<CapturedPage> pages) async {
    assert(pages.every((p) => verdictOf(p.quality) != Verdict.retake));
    final batch = DateTime.now().millisecondsSinceEpoch;
    for (var i = 0; i < pages.length; i++) {
      final page = pages[i];
      final bytes = await page.file.readAsBytes();
      final fileName = 'submission_${batch}_$i.jpg';
      await _client.storage
          .from('handwritten-submissions')
          .uploadBinary(fileName, bytes);
      final imageUrl = _client.storage
          .from('handwritten-submissions')
          .getPublicUrl(fileName);
      await _client.from('submissions').insert({
        'image_url': imageUrl,
        'question_id': question.id,
        'gate_result': gateResultValue(verdictOf(page.quality)),
        'status': 'pending',
      });
    }
  }
}
