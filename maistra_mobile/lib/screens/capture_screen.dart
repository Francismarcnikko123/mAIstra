import 'dart:io';
import 'package:flutter/material.dart';
import '../models/captured_page.dart';
import '../models/question_choice.dart';
import '../utils/page_capture.dart';
import '../utils/verdict.dart';
import '../widgets/verdict_view.dart';
import 'batch_review_screen.dart';

/// Screen 2: capture the pages of one answer. The chosen question stays in
/// the app bar for the whole session.
class CaptureScreen extends StatefulWidget {
  final QuestionChoice question;

  const CaptureScreen({super.key, required this.question});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  // Pages kept so far — shown and submitted from the review screen.
  final List<CapturedPage> _pages = [];

  // The page just scanned, waiting for Keep page / Retake.
  File? _pendingFile;
  CapturedPage? _pending;
  bool _busy = false;

  bool get _showingPending => _pendingFile != null;

  Future<void> _scan() async {
    setState(() => _busy = true);
    try {
      final page = await scanPage(
        onScanned: (file) {
          if (mounted) setState(() => _pendingFile = file);
        },
      );
      if (!mounted) return;
      setState(() {
        _pending = page;
        if (page == null) _pendingFile = null;
      });
    } catch (e) {
      // e.g. the quality check failed on a corrupt photo: don't leave the
      // "Checking photo quality…" view with both buttons disabled.
      if (!mounted) return;
      setState(() {
        _pending = null;
        _pendingFile = null;
      });
      _showError("Couldn't check that photo. Please scan the page again.");
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _importFromGallery() async {
    setState(() => _busy = true);
    try {
      final pages = await importFromGallery();
      if (!mounted || pages.isEmpty) return;
      setState(() => _pages.addAll(pages));
      await _openReview();
    } catch (e) {
      if (mounted) _showError('Could not process the photos: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _keepPending() {
    final page = _pending;
    if (page == null || page.verdict == Verdict.retake) return;
    setState(() {
      _pages.add(page);
      _pending = null;
      _pendingFile = null;
    });
  }

  void _retakePending() {
    setState(() {
      _pending = null;
      _pendingFile = null;
    });
    _scan();
  }

  Future<void> _openReview() async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) =>
            BatchReviewScreen(question: widget.question, pages: _pages),
      ),
    );
    // Pages may have been removed or retaken in review.
    if (mounted) setState(() {});
  }

  void _showError(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: _pages.isEmpty && !_showingPending,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        final navigator = Navigator.of(context);
        if (await _confirmLeave()) navigator.pop();
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(
            widget.question.shortLabel,
            overflow: TextOverflow.ellipsis,
          ),
        ),
        body: SafeArea(
          child: _showingPending ? _buildPendingView() : _buildScanView(),
        ),
      ),
    );
  }

  Future<bool> _confirmLeave() async {
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Discard these pages?'),
        content: const Text(
          'Going back to the question list removes the pages you have not submitted.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep capturing'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Discard'),
          ),
        ],
      ),
    );
    return result ?? false;
  }

  Widget _buildScanView() {
    final theme = Theme.of(context);
    final kept = _pages.length;

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Spacer(),
          Icon(
            Icons.document_scanner_outlined,
            size: 64,
            color: theme.colorScheme.primary,
          ),
          const SizedBox(height: 24),
          Text(
            widget.question.fullLabel,
            style: theme.textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w700,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Text(
            kept == 0
                ? 'Place the page on a flat surface and scan it.'
                : '$kept ${kept == 1 ? 'page' : 'pages'} kept',
            style: theme.textTheme.bodyLarge?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),
          const Spacer(),
          FilledButton.icon(
            onPressed: _busy ? null : _scan,
            icon: const Icon(Icons.camera_alt_outlined),
            label: Text(kept == 0 ? 'Scan page' : 'Scan next page'),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: _busy ? null : _importFromGallery,
            icon: _busy
                ? const SizedBox.square(
                    dimension: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.photo_library_outlined),
            label: Text(_busy ? 'Processing…' : 'Add from gallery'),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: _busy || kept == 0 ? null : _openReview,
            icon: const Icon(Icons.arrow_forward),
            label: const Text('Done — review pages'),
          ),
        ],
      ),
    );
  }

  Widget _buildPendingView() {
    final page = _pending;
    final isRetake = page?.verdict == Verdict.retake;

    return Column(
      children: [
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.file(
                page?.file ?? _pendingFile!,
                fit: BoxFit.contain,
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: page == null
              ? const Row(
                  children: [
                    SizedBox.square(
                      dimension: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                    SizedBox(width: 8),
                    Text('Checking photo quality…'),
                  ],
                )
              : VerdictBanner(result: page.quality),
        ),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: page == null ? null : _retakePending,
                  icon: const Icon(Icons.camera_alt_outlined),
                  label: const Text('Retake'),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: FilledButton.icon(
                  // A RETAKE page can never be kept.
                  onPressed: page == null || isRetake ? null : _keepPending,
                  icon: const Icon(Icons.check),
                  label: const Text('Keep page'),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
