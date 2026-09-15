import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:edge_detection/edge_detection.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;
import '../models/captured_page.dart';
import '../utils/quality_check.dart';

class BatchReviewScreen extends StatefulWidget {
  final List<CapturedPage> pages;

  const BatchReviewScreen({super.key, required this.pages});

  @override
  State<BatchReviewScreen> createState() => _BatchReviewScreenState();
}

class _BatchReviewScreenState extends State<BatchReviewScreen> {
  @override
  Widget build(BuildContext context) {
    final goodCount = widget.pages
        .where((p) => p.quality.decision == QualityDecision.pass)
        .length;
    final fixedCount = widget.pages
        .where((p) => p.quality.decision == QualityDecision.fixable)
        .length;
    final badCount = widget.pages
        .where((p) => p.quality.decision == QualityDecision.retake)
        .length;
    final selectedCount = widget.pages.where((p) => p.accepted).length;

    return Scaffold(
      backgroundColor: const Color(0xFFF5F5F5),
      appBar: AppBar(
        backgroundColor: const Color(0xFFB71C1C),
        title: const Text(
          'Batch Review',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        centerTitle: true,
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: Column(
        children: [
          // Summary bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            color: Colors.white,
            child: Row(
              children: [
                _SummaryBadge(count: goodCount, label: 'Good', color: Colors.green),
                const SizedBox(width: 8),
                if (fixedCount > 0) ...[
                  _SummaryBadge(count: fixedCount, label: 'Fixed', color: Colors.orange),
                  const SizedBox(width: 8),
                ],
                _SummaryBadge(count: badCount, label: 'Bad', color: Colors.red),
                const Spacer(),
                Text(
                  '$selectedCount / ${widget.pages.length} selected',
                  style: const TextStyle(color: Colors.grey, fontSize: 13),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          // Page list
          Expanded(
            child: widget.pages.isEmpty
                ? const Center(
                    child: Text(
                      'No pages scanned yet.',
                      style: TextStyle(color: Colors.grey),
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: widget.pages.length,
                    itemBuilder: (context, i) => _PageCard(
                      page: widget.pages[i],
                      index: i,
                      onToggle: () => setState(
                          () => widget.pages[i].accepted = !widget.pages[i].accepted),
                      onPreview: () => _showPreview(context, widget.pages[i], i),
                      onDelete: () => setState(() => widget.pages.removeAt(i)),
                      onRecrop: () => _recrop(i),
                    ),
                  ),
          ),
          // Bottom bar
          SafeArea(
            child: Container(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
              decoration: BoxDecoration(
                color: Colors.white,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.08),
                    blurRadius: 8,
                    offset: const Offset(0, -2),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.pop(context),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        side: const BorderSide(color: Color(0xFFB71C1C)),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Text(
                        'Back',
                        style: TextStyle(color: Color(0xFFB71C1C), fontSize: 16),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    flex: 2,
                    child: ElevatedButton.icon(
                      onPressed: selectedCount > 0
                          ? () => Navigator.pop(context, true)
                          : null,
                      icon: const Icon(Icons.check, color: Colors.white),
                      label: Text(
                        selectedCount > 0
                            ? 'Confirm $selectedCount Page(s)'
                            : 'Select pages to confirm',
                        style: const TextStyle(color: Colors.white, fontSize: 15),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFB71C1C),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        disabledBackgroundColor: Colors.grey.shade300,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _recrop(int index) async {
    final page = widget.pages[index];
    final dir = await getTemporaryDirectory();
    final saveTo = p.join(
      dir.path,
      'recrop_${DateTime.now().millisecondsSinceEpoch}.jpg',
    );
    final inputPath = page.originalPath ?? page.file.path;
    final ok = await EdgeDetection.recropImage(
      inputPath: inputPath,
      saveTo: saveTo,
    );
    if (!ok) return;
    final file = File(saveTo);
    if (!await file.exists()) return;
    final bytes = await file.readAsBytes();
    final quality = await compute(checkQuality, bytes);
    setState(() {
      widget.pages[index] = CapturedPage(
        file: file,
        quality: quality,
        accepted: quality.passed,
        originalPath: page.originalPath,
      );
    });
  }

  void _showPreview(BuildContext context, CapturedPage page, int index) {
    showDialog(
      context: context,
      builder: (_) => Dialog(
        backgroundColor: Colors.black,
        insetPadding: const EdgeInsets.all(12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                const SizedBox(width: 12),
                Text(
                  'Page ${index + 1}',
                  style: const TextStyle(color: Colors.white, fontSize: 16),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close, color: Colors.white),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
            Image.file(page.file, fit: BoxFit.contain),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}

// ─── Summary badge ───────────────────────────────────────────────────────────

class _SummaryBadge extends StatelessWidget {
  final int count;
  final String label;
  final Color color;

  const _SummaryBadge({
    required this.count,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            label == 'Good' ? Icons.check_circle : Icons.cancel,
            size: 14,
            color: color,
          ),
          const SizedBox(width: 4),
          Text(
            '$count $label',
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.bold,
              fontSize: 13,
            ),
          ),
        ],
      ),
    );
  }
}

// ─── Page card ───────────────────────────────────────────────────────────────

class _PageCard extends StatelessWidget {
  final CapturedPage page;
  final int index;
  final VoidCallback onToggle;
  final VoidCallback onPreview;
  final VoidCallback onDelete;
  final VoidCallback onRecrop;

  const _PageCard({
    required this.page,
    required this.index,
    required this.onToggle,
    required this.onPreview,
    required this.onDelete,
    required this.onRecrop,
  });

  @override
  Widget build(BuildContext context) {
    final decision = page.quality.decision;
    final qualityColor = decision == QualityDecision.pass
        ? Colors.green
        : decision == QualityDecision.fixable
            ? Colors.orange
            : Colors.red;
    final qualityLabel = decision == QualityDecision.pass
        ? 'GOOD'
        : decision == QualityDecision.fixable
            ? 'FIXED'
            : 'BAD';
    final qualityIcon = decision == QualityDecision.pass
        ? Icons.check_circle
        : decision == QualityDecision.fixable
            ? Icons.auto_fix_high
            : Icons.cancel;

    return Card(
      elevation: 2,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: page.accepted ? Colors.green : Colors.grey.shade300,
          width: page.accepted ? 2.0 : 1.0,
        ),
      ),
      child: InkWell(
        onTap: onPreview,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Thumbnail with quality badge
              Stack(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Image.file(
                      page.file,
                      width: 80,
                      height: 110,
                      fit: BoxFit.cover,
                    ),
                  ),
                  Positioned(
                    top: 4,
                    left: 4,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: qualityColor,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(qualityIcon, color: Colors.white, size: 10),
                          const SizedBox(width: 2),
                          Text(
                            qualityLabel,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 9,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(width: 12),
              // Info column
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          'Page ${index + 1}',
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 15,
                          ),
                        ),
                        if (page.accepted) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 6,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.green.shade50,
                              borderRadius: BorderRadius.circular(4),
                              border: Border.all(color: Colors.green),
                            ),
                            child: const Text(
                              'Selected',
                              style: TextStyle(
                                color: Colors.green,
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ],
                        const Spacer(),
                        GestureDetector(
                          onTap: onDelete,
                          child: const Icon(
                            Icons.delete_outline,
                            color: Colors.red,
                            size: 20,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    if (page.quality.issues.isEmpty)
                      const Text(
                        '✓ All quality checks passed',
                        style: TextStyle(color: Colors.green, fontSize: 12),
                      )
                    else
                      ...page.quality.issues.map(
                        (issue) => Padding(
                          padding: const EdgeInsets.only(bottom: 3),
                          child: Text(
                            '• $issue',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey.shade700,
                            ),
                          ),
                        ),
                      ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: onToggle,
                            icon: Icon(
                              page.accepted
                                  ? Icons.remove_circle_outline
                                  : Icons.add_circle_outline,
                              size: 14,
                            ),
                            label: Text(
                              page.accepted ? 'Remove' : 'Include',
                              style: const TextStyle(fontSize: 12),
                            ),
                            style: OutlinedButton.styleFrom(
                              foregroundColor:
                                  page.accepted ? Colors.red : Colors.green,
                              side: BorderSide(
                                color: page.accepted ? Colors.red : Colors.green,
                              ),
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 6,
                              ),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(8),
                              ),
                              minimumSize: Size.zero,
                              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: onRecrop,
                            icon: const Icon(Icons.crop, size: 14),
                            label: const Text(
                              'Recrop',
                              style: TextStyle(fontSize: 12),
                            ),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: const Color(0xFFB71C1C),
                              side: const BorderSide(color: Color(0xFFB71C1C)),
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 6,
                              ),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(8),
                              ),
                              minimumSize: Size.zero,
                              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
