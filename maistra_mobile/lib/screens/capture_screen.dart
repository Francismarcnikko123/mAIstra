import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:cunning_document_scanner/cunning_document_scanner.dart';
import '../utils/quality_check.dart';
import '../utils/batch_review.dart';
import 'batch_review_screen.dart';

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  bool _isProcessingBatch = false;

  Future<void> _scanDocument() async {
    try {
      final pictures = await CunningDocumentScanner.getPictures(noOfPages: 20);
      if (pictures == null || pictures.isEmpty) return;
      await _processPages(pictures);
    } catch (e) {
      setState(() => _isProcessingBatch = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Scanner error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _pickFromGallery() async {
    try {
      final pictures = await CunningDocumentScanner.getPictures(
        isGalleryImportAllowed: true,
        noOfPages: 20,
      );
      if (pictures == null || pictures.isEmpty) return;
      await _processPages(pictures);
    } catch (e) {
      setState(() => _isProcessingBatch = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _processPages(List<String> paths) async {
    setState(() => _isProcessingBatch = true);

    final items = <BatchItem>[];
    for (final path in paths) {
      final bytes = await File(path).readAsBytes();
      final result = await compute(checkQuality, bytes);
      items.add(BatchItem(path: path, result: result));
    }

    setState(() => _isProcessingBatch = false);

    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => BatchReviewScreen(review: BatchReview(items)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: const Color(0xFFB71C1C),
        title: const Text('mAIstra',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        centerTitle: true,
      ),
      body: _isProcessingBatch ? _buildProcessingView() : _buildScanView(),
    );
  }

  Widget _buildScanView() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.document_scanner, size: 100, color: Color(0xFFB71C1C)),
          const SizedBox(height: 24),
          const Text('Capture Handwritten C Code',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          const Text('Place the paper on a flat surface and scan',
              style: TextStyle(fontSize: 14, color: Colors.grey)),
          const SizedBox(height: 40),
          ElevatedButton.icon(
            onPressed: _scanDocument,
            icon: const Icon(Icons.document_scanner, color: Colors.white),
            label: const Text('Scan Document',
                style: TextStyle(color: Colors.white, fontSize: 16)),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFB71C1C),
              padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 16),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
          ),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: _pickFromGallery,
            icon: const Icon(Icons.photo_library, color: Color(0xFFB71C1C)),
            label: const Text('Upload from Gallery',
                style: TextStyle(color: Color(0xFFB71C1C), fontSize: 16)),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 16),
              side: const BorderSide(color: Color(0xFFB71C1C)),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProcessingView() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(color: Color(0xFFB71C1C)),
          SizedBox(height: 24),
          Text('Checking image quality…',
              style: TextStyle(fontSize: 16, color: Colors.grey)),
        ],
      ),
    );
  }
}
