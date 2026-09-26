import 'package:flutter/material.dart';
import '../models/captured_page.dart';
import '../models/question_choice.dart';
import '../services/submission_uploader.dart';
import '../theme/app_theme.dart';
import '../utils/page_capture.dart';
import '../utils/verdict.dart';
import '../widgets/verdict_view.dart';
import 'submitted_screen.dart';

/// Screen 3: review every page of this answer before submitting. A RETAKE
/// page carries its own error and actions, and blocks submit.
class BatchReviewScreen extends StatefulWidget {
  final QuestionChoice question;

  /// Shared with the capture screen, so removals and retakes carry back.
  final List<CapturedPage> pages;
  final SubmissionUploader? uploader;

  const BatchReviewScreen({
    super.key,
    required this.question,
    required this.pages,
    this.uploader,
  });

  @override
  State<BatchReviewScreen> createState() => _BatchReviewScreenState();
}

class _BatchReviewScreenState extends State<BatchReviewScreen> {
  late final SubmissionUploader _uploader =
      widget.uploader ?? SubmissionUploader();
  bool _busy = false;
  String? _uploadError;
  // Created on the first Submit and kept for retries: one batch_id per
  // answer, and pages already saved are not sent again.
  UploadBatch? _batch;

  bool _isSaved(CapturedPage page) => _batch?.isSaved(page) ?? false;

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  List<CapturedPage> get _pages => widget.pages;

  int _count(Verdict v) => _pages.where((p) => p.verdict == v).length;

  String? get _blockedReason {
    if (_pages.isEmpty) return 'Add at least one page to submit.';
    final retakes = _count(Verdict.retake);
    if (retakes == 0) return null;
    return retakes == 1
        ? 'Retake or remove the page marked Retake to submit.'
        : 'Retake or remove the $retakes pages marked Retake to submit.';
  }

  Future<void> _retake(CapturedPage page) async {
    setState(() => _busy = true);
    try {
      final fresh = await scanPage();
      if (fresh == null || !mounted) return;
      setState(() => _replace(page, fresh));
    } catch (e) {
      _showError("Couldn't check that photo. Please take it again.");
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _recrop(CapturedPage page) async {
    setState(() => _busy = true);
    try {
      final fresh = await recropPage(page);
      if (fresh == null || !mounted) return;
      setState(() => _replace(page, fresh));
    } catch (e) {
      _showError("Couldn't recrop that page. Try again or retake it.");
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _replace(CapturedPage old, CapturedPage fresh) {
    final i = _pages.indexOf(old);
    if (i >= 0) _pages[i] = fresh;
  }

  void _remove(CapturedPage page) {
    setState(() => _pages.remove(page));
  }

  Future<void> _submit() async {
    if (_blockedReason != null) return;
    setState(() {
      _busy = true;
      _uploadError = null;
    });
    try {
      final count = _pages.length;
      final batch = _batch ??= UploadBatch();
      await _uploader.submit(widget.question, List.of(_pages), batch);
      if (!mounted) return;
      _pages.clear();
      Navigator.pushAndRemoveUntil(
        context,
        MaterialPageRoute(
          builder: (_) => SubmittedScreen(
            question: widget.question,
            pageCount: count,
            submittedAt: DateTime.now(),
          ),
        ),
        (_) => false,
      );
    } catch (e) {
      if (mounted) {
        setState(
          () => _uploadError = (_batch?.savedCount ?? 0) > 0
              ? '${_batch!.savedCount} of ${_pages.length} pages were sent before the upload failed. '
                    'Check your connection and tap Submit again to send the rest.'
              : 'Upload failed. Check your connection and try again. ($e)',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final blocked = _blockedReason;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.question.shortLabel,
          overflow: TextOverflow.ellipsis,
        ),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Row(
              children: [
                Text(
                  '${_pages.length} ${_pages.length == 1 ? 'page' : 'pages'}',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const Spacer(),
                Wrap(
                  spacing: 8,
                  children: [
                    for (final v in Verdict.values)
                      if (_count(v) > 0)
                        VerdictChip(verdict: v, count: _count(v)),
                  ],
                ),
              ],
            ),
          ),
          const Divider(),
          Expanded(
            child: _pages.isEmpty
                ? Center(
                    child: Text(
                      'No pages yet. Go back to scan one.',
                      style: theme.textTheme.bodyLarge?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  )
                : ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: _pages.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 16),
                    itemBuilder: (context, i) {
                      final page = _pages[i];
                      return _PageCard(
                        key: ValueKey(page.file.path),
                        page: page,
                        index: i,
                        // A page already saved to the database can't be
                        // changed or removed from this answer any more.
                        enabled: !_busy && !_isSaved(page),
                        onPreview: () => _showPreview(page, i),
                        onRetake: () => _retake(page),
                        onRecrop: () => _recrop(page),
                        onRemove: () => _remove(page),
                      );
                    },
                  ),
          ),
          const Divider(),
          SafeArea(
            top: false,
            minimum: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (_uploadError != null || blocked != null) ...[
                  Row(
                    children: [
                      Icon(
                        Icons.info_outline,
                        size: 20,
                        color: _uploadError != null
                            ? theme.colorScheme.error
                            : theme.colorScheme.onSurfaceVariant,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _uploadError ?? blocked!,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: _uploadError != null
                                ? theme.colorScheme.error
                                : theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                ],
                FilledButton.icon(
                  onPressed: _busy || blocked != null ? null : _submit,
                  icon: _busy
                      ? const SizedBox.square(
                          dimension: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.cloud_upload_outlined),
                  label: Text(_busy ? 'Submitting…' : 'Submit answer'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _showPreview(CapturedPage page, int index) {
    showDialog(
      context: context,
      builder: (context) => Dialog(
        backgroundColor: Colors.black,
        insetPadding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                const SizedBox(width: 16),
                Text(
                  'Page ${index + 1}',
                  style: const TextStyle(color: Colors.white, fontSize: 16),
                ),
                const Spacer(),
                IconButton(
                  tooltip: 'Close',
                  icon: const Icon(Icons.close, color: Colors.white),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
            Flexible(child: Image.file(page.file, fit: BoxFit.contain)),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}

// ─── Page card ───────────────────────────────────────────────────────────────

class _PageCard extends StatelessWidget {
  final CapturedPage page;
  final int index;
  final bool enabled;
  final VoidCallback onPreview;
  final VoidCallback onRetake;
  final VoidCallback onRecrop;
  final VoidCallback onRemove;

  const _PageCard({
    super.key,
    required this.page,
    required this.index,
    required this.enabled,
    required this.onPreview,
    required this.onRetake,
    required this.onRecrop,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isRetake = page.verdict == Verdict.retake;
    final retakeColor = VerdictColors.of(context).retake;

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: BorderSide(
          color: isRetake ? retakeColor : theme.colorScheme.outlineVariant,
          width: isRetake ? 2 : 1,
        ),
      ),
      clipBehavior: Clip.antiAlias,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                InkWell(
                  onTap: onPreview,
                  borderRadius: BorderRadius.circular(8),
                  child: Semantics(
                    button: true,
                    label: 'Preview page ${index + 1}',
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: Image.file(
                        page.file,
                        width: 72,
                        height: 96,
                        fit: BoxFit.cover,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Page ${index + 1}',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 8),
                      VerdictBanner(result: page.quality, dense: true),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                if (isRetake) ...[
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: enabled ? onRetake : null,
                      icon: const Icon(Icons.camera_alt_outlined),
                      label: const Text('Retake'),
                    ),
                  ),
                  const SizedBox(width: 8),
                ],
                if (page.originalPath != null) ...[
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: enabled ? onRecrop : null,
                      icon: const Icon(Icons.crop),
                      label: const Text('Recrop'),
                    ),
                  ),
                  const SizedBox(width: 8),
                ],
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: enabled ? onRemove : null,
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('Remove'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
