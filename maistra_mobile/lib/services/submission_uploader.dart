import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/captured_page.dart';
import '../models/question_choice.dart';
import '../utils/batch_id.dart';
import '../utils/verdict.dart';

/// One answer's upload: its `batch_id` and the pages already saved. The
/// review screen keeps it across retries, so a submit that failed halfway
/// resends only the missing pages, under the same `batch_id`, instead of
/// creating a second copy of the answer.
class UploadBatch {
  final String batchId;
  final Set<String> _saved = {};

  UploadBatch([String? batchId]) : batchId = batchId ?? newBatchId();

  bool isSaved(CapturedPage page) => _saved.contains(page.file.path);
  void markSaved(CapturedPage page) => _saved.add(page.file.path);
  int get savedCount => _saved.length;
}

class SubmissionUploader {
  final SupabaseClient? _client;

  SubmissionUploader([SupabaseClient? client]) : _client = client;

  SupabaseClient get _db => _client ?? Supabase.instance.client;

  /// Uploads every page of one answer not yet saved in [batch], all linked
  /// to [question] and sharing `batch.batchId`. Callers must not pass a
  /// RETAKE page; the review screen blocks submit first.
  Future<void> submit(
    QuestionChoice question,
    List<CapturedPage> pages,
    UploadBatch batch,
  ) async {
    assert(pages.every((p) => verdictOf(p.quality) != Verdict.retake));
    final stamp = DateTime.now().millisecondsSinceEpoch;
    for (var i = 0; i < pages.length; i++) {
      final page = pages[i];
      if (batch.isSaved(page)) continue;
      final imageUrl = await uploadImage(page, 'submission_${stamp}_$i.jpg');
      await insertRow(submissionRow(imageUrl, question, page, batch.batchId));
      batch.markSaved(page);
    }
  }

  /// Stores the photo and returns its public URL. A retry uses a new file
  /// name, so a photo left behind by a failed attempt never blocks it.
  Future<String> uploadImage(CapturedPage page, String fileName) async {
    final bytes = await page.file.readAsBytes();
    final bucket = _db.storage.from('handwritten-submissions');
    await bucket.uploadBinary(fileName, bytes);
    return bucket.getPublicUrl(fileName);
  }

  Future<void> insertRow(Map<String, dynamic> row) async {
    await _db.from('submissions').insert(row);
  }

  /// The `submissions` insert for one page. `extracted_text`, `verified_text`
  /// and `answers` stay empty: the OCR worker only reads unread pending pages.
  static Map<String, dynamic> submissionRow(
    String imageUrl,
    QuestionChoice question,
    CapturedPage page,
    String batchId,
  ) => {
    'image_url': imageUrl,
    'question_id': question.id,
    'gate_result': gateResultValue(verdictOf(page.quality)),
    'batch_id': batchId,
    'status': 'pending',
  };
}
