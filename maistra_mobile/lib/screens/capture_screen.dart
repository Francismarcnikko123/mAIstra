import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  File? _capturedImage;
  bool _isUploading = false;
  final ImagePicker _picker = ImagePicker();
  final supabase = Supabase.instance.client;

  Future<void> _captureImage() async {
    final XFile? photo = await _picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 90,
    );

    if (photo != null) {
      setState(() {
        _capturedImage = File(photo.path);
      });
    }
  }

  Future<void> _saveToDatabase() async {
    if (_capturedImage == null) return;

    setState(() {
      _isUploading = true;
    });

    try {
      final fileName =
          'submission_${DateTime.now().millisecondsSinceEpoch}.jpg';

      await supabase.storage
          .from('handwritten-submissions')
          .upload(fileName, _capturedImage!);

      final imageUrl = supabase.storage
          .from('handwritten-submissions')
          .getPublicUrl(fileName);

      await supabase.from('submissions').insert({
        'image_url': imageUrl,
        'status': 'pending',
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Image saved successfully!'),
            backgroundColor: Colors.green,
          ),
        );
        setState(() {
          _capturedImage = null;
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      setState(() {
        _isUploading = false;
      });
    }
  }

  void _discard() {
    setState(() {
      _capturedImage = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: const Color(0xFFB71C1C),
        title: const Text(
          'mAIstra',
          style: TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.bold,
          ),
        ),
        centerTitle: true,
      ),
      body: _capturedImage == null
          ? _buildCaptureView()
          : _buildPreviewView(),
    );
  }

  Widget _buildCaptureView() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.document_scanner,
            size: 100,
            color: Color(0xFFB71C1C),
          ),
          const SizedBox(height: 24),
          const Text(
            'Capture Handwritten C Code',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Take a photo of the student\'s paper',
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey,
            ),
          ),
          const SizedBox(height: 40),
          ElevatedButton.icon(
            onPressed: _captureImage,
            icon: const Icon(Icons.camera_alt, color: Colors.white),
            label: const Text(
              'Open Camera',
              style: TextStyle(color: Colors.white, fontSize: 16),
            ),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFB71C1C),
              padding: const EdgeInsets.symmetric(
                horizontal: 40,
                vertical: 16,
              ),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
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
              child: Image.file(
                _capturedImage!,
                fit: BoxFit.contain,
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              const Text(
                'Is the image clear and readable?',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _isUploading ? null : _discard,
                      icon: const Icon(Icons.close, color: Colors.red),
                      label: const Text(
                        'Discard',
                        style: TextStyle(color: Colors.red, fontSize: 16),
                      ),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        side: const BorderSide(color: Colors.red),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _isUploading ? null : _saveToDatabase,
                      icon: _isUploading
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                color: Colors.white,
                                strokeWidth: 2,
                              ),
                            )
                          : const Icon(Icons.check, color: Colors.white),
                      label: Text(
                        _isUploading ? 'Saving...' : 'Accept',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                        ),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFB71C1C),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }
}