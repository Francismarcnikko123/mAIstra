import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:cunning_document_scanner/cunning_document_scanner.dart';
import 'package:image_picker/image_picker.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../utils/quality_check.dart';

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  File? _rawImage;
  bool _isUploading = false;
  bool _isCheckingQuality = false;
  QualityResult? _qualityResult;

  final supabase = Supabase.instance.client;

  Future<void> _scanDocument() async {
    try {
      final pictures = await CunningDocumentScanner.getPictures(noOfPages: 1);
      if (pictures == null || pictures.isEmpty) return;
      await _processPickedFile(File(pictures.first));
    } catch (e) {
      setState(() => _isCheckingQuality = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Scanner error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _pickFromGallery() async {
    try {
      final picked = await ImagePicker().pickImage(source: ImageSource.gallery);
      if (picked == null) return;
      await _processPickedFile(File(picked.path));
    } catch (e) {
      setState(() => _isCheckingQuality = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  // Shared by camera scans and gallery uploads — same quality gate either
  // way, since a bad photo is a bad photo regardless of where it came from.
  Future<void> _processPickedFile(File rawFile) async {
    setState(() {
      _isCheckingQuality = true;
      _qualityResult = null;
      _rawImage = null;
    });

    final rawBytes = await rawFile.readAsBytes();
    final rawResult = await compute(checkQuality, rawBytes);

    setState(() {
      _rawImage = rawFile;
      _qualityResult = rawResult;
      _isCheckingQuality = false;
    });
  }

  Future<void> _saveToDatabase() async {
    if (_rawImage == null) return;
    setState(() => _isUploading = true);

    try {
      final timestamp = DateTime.now().millisecondsSinceEpoch;
      final fileName = 'submission_$timestamp.jpg';

      // Raw only — JC's OCR pipeline does its own preprocessing, so
      // mAIstra doesn't upload a normalized version anymore. The quality
      // gate still validates this raw image before Accept is enabled.
      await supabase.storage
          .from('handwritten-submissions')
          .upload(fileName, _rawImage!);

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
          _rawImage = null;
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
      _rawImage = null;
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
      body: _rawImage == null && !_isCheckingQuality
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
              child: _rawImage != null
                  ? Image.file(_rawImage!, fit: BoxFit.contain)
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
