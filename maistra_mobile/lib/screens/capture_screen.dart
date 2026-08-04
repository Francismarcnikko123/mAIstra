import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:cunning_document_scanner/cunning_document_scanner.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../utils/quality_check.dart';

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  File? _scannedImage;
  bool _isUploading = false;
  bool _isCheckingQuality = false;
  QualityResult? _qualityResult;

  final supabase = Supabase.instance.client;

  Future<void> _scanDocument() async {
    try {
      final pictures = await CunningDocumentScanner.getPictures(noOfPages: 1);
      if (pictures == null || pictures.isEmpty) return;

      setState(() {
        _isCheckingQuality = true;
        _qualityResult = null;
        _scannedImage = null;
      });

      final rawFile = File(pictures.first);
      final rawBytes = await rawFile.readAsBytes();

      // Quality check on raw scan (blur, darkness, overexposure)
      final rawResult = await compute(checkQuality, rawBytes);

      // Background normalization in background isolate
      final processedBytes = await compute(processDocument, rawBytes.toList());
      final processedPath =
          '${rawFile.parent.path}/processed_${rawFile.uri.pathSegments.last}';
      final processedFile = File(processedPath);
      await processedFile.writeAsBytes(processedBytes);

      // Re-check the processed image too — this is what OCR actually
      // receives, so defects introduced by normalization must not slip
      // through just because the raw scan looked fine.
      final processedResult = await compute(checkQuality, processedBytes);
      final combinedResult = combineQualityResults(rawResult, processedResult);

      setState(() {
        _scannedImage = processedFile; // normalized image shown and uploaded
        _qualityResult = combinedResult;
        _isCheckingQuality = false;
      });
    } catch (e) {
      setState(() => _isCheckingQuality = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Scanner error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _saveToDatabase() async {
    if (_scannedImage == null) return;
    setState(() => _isUploading = true);

    try {
      final fileName = 'submission_${DateTime.now().millisecondsSinceEpoch}.jpg';

      await supabase.storage
          .from('handwritten-submissions')
          .upload(fileName, _scannedImage!);

      final imageUrl = supabase.storage
          .from('handwritten-submissions')
          .getPublicUrl(fileName);

      await supabase.from('submissions').insert({
        'image_url': imageUrl,
        'status': 'pending',
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Saved successfully!'), backgroundColor: Colors.green),
        );
        setState(() {
          _scannedImage = null;
          _qualityResult = null;
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      setState(() => _isUploading = false);
    }
  }

  void _discard() {
    setState(() {
      _scannedImage = null;
      _qualityResult = null;
    });
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
      body: _scannedImage == null && !_isCheckingQuality
          ? _buildScanView()
          : _buildPreviewView(),
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
        ],
      ),
    );
  }

  Widget _buildPreviewView() {
    return Column(
      children: [
        Expanded(
          child: Container(
            width: double.infinity,
            margin: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.grey.shade300),
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: _scannedImage != null
                  ? Image.file(_scannedImage!, fit: BoxFit.contain)
                  : const SizedBox(),
            ),
          ),
        ),

        if (_isCheckingQuality)
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16),
            child: Row(children: [
              SizedBox(width: 16, height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2)),
              SizedBox(width: 8),
              Text('Checking image quality...'),
            ]),
          ),

        if (!_isCheckingQuality && _qualityResult != null)
          Container(
            width: double.infinity,
            margin: const EdgeInsets.symmetric(horizontal: 16),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: _qualityResult!.passed ? Colors.green.shade50 : Colors.red.shade50,
              border: Border.all(
                  color: _qualityResult!.passed ? Colors.green : Colors.red),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Icon(
                    _qualityResult!.passed ? Icons.check_circle : Icons.warning,
                    color: _qualityResult!.passed ? Colors.green : Colors.red,
                    size: 18,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    _qualityResult!.passed ? 'Image quality is good' : 'Quality issues detected',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: _qualityResult!.passed ? Colors.green : Colors.red,
                    ),
                  ),
                ]),
                ..._qualityResult!.issues.map((issue) => Padding(
                  padding: const EdgeInsets.only(top: 4, left: 26),
                  child: Text('• $issue', style: const TextStyle(fontSize: 13)),
                )),
              ],
            ),
          ),

        const SizedBox(height: 12),

        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          child: Row(children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _isUploading || _isCheckingQuality ? null : _discard,
                icon: const Icon(Icons.close, color: Colors.red),
                label: const Text('Discard',
                    style: TextStyle(color: Colors.red, fontSize: 16)),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  side: const BorderSide(color: Colors.red),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: ElevatedButton.icon(
                onPressed: _isUploading || _isCheckingQuality ||
                    (_qualityResult != null && !_qualityResult!.passed)
                    ? null
                    : _saveToDatabase,
                icon: _isUploading
                    ? const SizedBox(width: 20, height: 20,
                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                    : const Icon(Icons.check, color: Colors.white),
                label: Text(_isUploading ? 'Saving...' : 'Accept',
                    style: const TextStyle(color: Colors.white, fontSize: 16)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFB71C1C),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ),
          ]),
        ),
      ],
    );
  }
}
