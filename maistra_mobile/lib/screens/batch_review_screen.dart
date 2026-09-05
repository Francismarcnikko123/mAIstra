import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:cunning_document_scanner/cunning_document_scanner.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../utils/batch_review.dart';
import '../utils/quality_check.dart';

class BatchReviewScreen extends StatefulWidget {
  final BatchReview review;
  const BatchReviewScreen({super.key, required this.review});

  @override
  State<BatchReviewScreen> createState() => _BatchReviewScreenState();
}

class _BatchReviewScreenState extends State<BatchReviewScreen> {
  bool _isUploading = false;
  bool _isProcessing = false;

  Future<void> _retake(BatchItem item) async {
    List<String>? pictures;
    try {
      pictures = await CunningDocumentScanner.getPictures(noOfPages: 1);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Scanner error: $e'), backgroundColor: Colors.red),
        );
      }
      return;
    }
    if (pictures == null || pictures.isEmpty || !mounted) return;
    final path = pictures.first;

    setState(() => _isProcessing = true);
    final bytes = await File(path).readAsBytes();
    final result = await compute(checkQuality, bytes);
    setState(() {
      widget.review.replace(item, BatchItem(path: path, result: result));
      _isProcessing = false;
    });
  }

  Future<void> _acceptSelected() async {
    final toUpload = widget.review.selectedGoodItems;
    if (toUpload.isEmpty) return;

    setState(() => _isUploading = true);
    final supabase = Supabase.instance.client;

    try {
      for (final item in toUpload) {
        final bytes = await File(item.path).readAsBytes();
        final fileName = 'submission_${DateTime.now().millisecondsSinceEpoch}.jpg';
        await supabase.storage.from('handwritten-submissions').uploadBinary(fileName, bytes);
        final imageUrl = supabase.storage
            .from('handwritten-submissions')
            .getPublicUrl(fileName);
        await supabase.from('submissions').insert({
          'image_url': imageUrl,
          'status': 'pending',
        });
        widget.review.discard(item);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload failed: $e'), backgroundColor: Colors.red),
        );
      }
      setState(() => _isUploading = false);
      return;
    }

    setState(() => _isUploading = false);
    if (widget.review.isEmpty && mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final good = widget.review.goodItems;
    final bad = widget.review.badItems;
    final selectedCount = widget.review.selectedGoodItems.length;

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: const Color(0xFFB71C1C),
        title: const Text('Review Batch',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        centerTitle: true,
      ),
      body: _isProcessing
          ? const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(),
                  SizedBox(height: 12),
                  Text('Checking image quality...'),
                ],
              ),
            )
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (good.isNotEmpty) ...[
                  Text('Good Quality (${good.length})',
                      style: const TextStyle(
                          fontSize: 16, fontWeight: FontWeight.bold, color: Colors.green)),
                  const SizedBox(height: 8),
                  ...good.map((item) => _GoodItemCard(
                        item: item,
                        onToggle: () => setState(() => widget.review.toggleSelected(item)),
                        onRecrop: () => _retake(item),
                      )),
                  const SizedBox(height: 24),
                ],
                if (bad.isNotEmpty) ...[
                  Text('Bad Quality (${bad.length})',
                      style: const TextStyle(
                          fontSize: 16, fontWeight: FontWeight.bold, color: Colors.red)),
                  const SizedBox(height: 8),
                  ...bad.map((item) => _BadItemCard(
                        item: item,
                        onRetake: () => _retake(item),
                        onDelete: () => setState(() => widget.review.discard(item)),
                      )),
                ],
              ],
            ),
      bottomNavigationBar: good.isNotEmpty
          ? SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: ElevatedButton(
                  onPressed: (_isUploading || selectedCount == 0) ? null : _acceptSelected,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFB71C1C),
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  child: _isUploading
                      ? const CircularProgressIndicator(color: Colors.white)
                      : Text('Accept Selected ($selectedCount)',
                          style: const TextStyle(color: Colors.white, fontSize: 16)),
                ),
              ),
            )
          : null,
    );
  }
}

void _openFullScreen(BuildContext context, String path) {
  Navigator.of(context).push(MaterialPageRoute(
    builder: (_) => Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(backgroundColor: Colors.black, foregroundColor: Colors.white),
      body: Center(
        child: InteractiveViewer(
          child: Image.file(File(path)),
        ),
      ),
    ),
  ));
}

class _GoodItemCard extends StatelessWidget {
  final BatchItem item;
  final VoidCallback onToggle;
  final VoidCallback onRecrop;

  const _GoodItemCard({
    required this.item,
    required this.onToggle,
    required this.onRecrop,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: GestureDetector(
          onTap: () => _openFullScreen(context, item.path),
          child: Image.file(File(item.path), width: 56, height: 56, fit: BoxFit.cover),
        ),
        title: const Text('Image quality is good',
            style: TextStyle(color: Colors.green, fontSize: 13)),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextButton(onPressed: onRecrop, child: const Text('Re-crop')),
            Checkbox(value: item.selected, onChanged: (_) => onToggle()),
          ],
        ),
      ),
    );
  }
}

class _BadItemCard extends StatelessWidget {
  final BatchItem item;
  final VoidCallback onRetake;
  final VoidCallback onDelete;

  const _BadItemCard({
    required this.item,
    required this.onRetake,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: GestureDetector(
          onTap: () => _openFullScreen(context, item.path),
          child: Image.file(File(item.path), width: 56, height: 56, fit: BoxFit.cover),
        ),
        title: Text(item.result.issues.join('\n'),
            style: const TextStyle(color: Colors.red, fontSize: 12)),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextButton(onPressed: onRetake, child: const Text('Retake')),
            IconButton(onPressed: onDelete, icon: const Icon(Icons.delete_outline)),
          ],
        ),
      ),
    );
  }
}
