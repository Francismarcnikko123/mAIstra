import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:image/image.dart' as img;
import 'dart:typed_data';
import 'dart:math';

// Result of the quality check
class QualityResult {
  final bool passed;
  final List<String> issues;

  QualityResult({required this.passed, required this.issues});
}

// This runs in a separate thread (isolate) so it doesn't freeze the UI
// Heavy image processing should never run on the main thread
QualityResult _analyzeInIsolate(List<int> bytes) {
  final image = img.decodeImage(Uint8List.fromList(bytes));
  if (image == null) return QualityResult(passed: false, issues: ['Could not read image']);

  // Resize to 200x200 for speed — we don't need full resolution to check quality
  final small = img.copyResize(image, width: 200, height: 200);
  final grayscale = img.grayscale(small);

  double totalBrightness = 0;
  double laplacianSum = 0;
  double laplacianSumSquares = 0;
  int count = 0;

  for (int y = 1; y < grayscale.height - 1; y++) {
    for (int x = 1; x < grayscale.width - 1; x++) {
      // Brightness: average pixel value across all pixels
      final center = grayscale.getPixel(x, y).r.toDouble();
      totalBrightness += center;

      // Blur detection using Laplacian operator
      // It measures how much edges exist — blurry images have weak edges
      final top    = grayscale.getPixel(x, y - 1).r.toDouble();
      final bottom = grayscale.getPixel(x, y + 1).r.toDouble();
      final left   = grayscale.getPixel(x - 1, y).r.toDouble();
      final right  = grayscale.getPixel(x + 1, y).r.toDouble();

      final laplacian = 4 * center - top - bottom - left - right;
      laplacianSum += laplacian;
      laplacianSumSquares += laplacian * laplacian;
      count++;
    }
  }

  final totalPixels = grayscale.width * grayscale.height;
  final avgBrightness = totalBrightness / totalPixels;

  final mean = laplacianSum / count;
  final blurScore = (laplacianSumSquares / count) - (mean * mean);
  // Higher blurScore = sharper image. Low score = blurry.

  final List<String> issues = [];

 // Check for uneven lighting by comparing brightest vs darkest quadrant
  final regions = [
    [0, 0, grayscale.width ~/ 2, grayscale.height ~/ 2],
    [grayscale.width ~/ 2, 0, grayscale.width, grayscale.height ~/ 2],
    [0, grayscale.height ~/ 2, grayscale.width ~/ 2, grayscale.height],
    [grayscale.width ~/ 2, grayscale.height ~/ 2, grayscale.width, grayscale.height],
  ];

  double minRegion = 255;
  double maxRegion = 0;

  for (final r in regions) {
    double regionBrightness = 0;
    int regionCount = 0;
    for (int y = r[1]; y < r[3]; y++) {
      for (int x = r[0]; x < r[2]; x++) {
        regionBrightness += grayscale.getPixel(x, y).r.toDouble();
        regionCount++;
      }
    }
    final avg = regionBrightness / regionCount;
    if (avg < minRegion) minRegion = avg;
    if (avg > maxRegion) maxRegion = avg;
  }

  if (maxRegion - minRegion > 50) {
    issues.add('Uneven lighting or shadow detected — ensure even lighting');
  }
  if (avgBrightness < 60)  issues.add('Too dark — find better lighting');
  if (avgBrightness > 220) issues.add('Too bright / overexposed');
  if (blurScore < 1300)    issues.add('Image is blurry — hold camera steady');

  // Slant detection using horizontal projection
// Straight paper = text lines create clear peaks in horizontal projection
// Tilted paper = projection is flat/uniform
final List<double> hProj = [];
for (int y = 0; y < grayscale.height; y++) {
  int edgeCount = 0;
  for (int x = 1; x < grayscale.width - 1; x++) {
    final left = grayscale.getPixel(x - 1, y).r.toDouble();
    final right = grayscale.getPixel(x + 1, y).r.toDouble();
    if ((right - left).abs() > 15) edgeCount++;
  }
  hProj.add(edgeCount.toDouble());
}

final projMean = hProj.reduce((a, b) => a + b) / hProj.length;
double projVariance = 0;
for (final v in hProj) {
  projVariance += (v - projMean) * (v - projMean);
}
projVariance /= hProj.length;
final cv = projMean > 0 ? sqrt(projVariance) / projMean : 0;
print('Slant cv: $cv');

if (cv < 1.0) {
  issues.add('Paper is slanted — hold the paper flat and straight');
}

  return QualityResult(passed: issues.isEmpty, issues: issues);
}

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  File? _capturedImage;
  bool _isUploading = false;
  bool _isCheckingQuality = false;
  QualityResult? _qualityResult;

  final ImagePicker _picker = ImagePicker();
  final supabase = Supabase.instance.client;

  Future<void> _captureImage() async {
  final XFile? photo = await _picker.pickImage(
    source: ImageSource.camera,
    imageQuality: 90,
  );

  if (photo == null) return;

  setState(() {
    _capturedImage = File(photo.path);
    _isCheckingQuality = true;
    _qualityResult = null;
  });

  try {
    final bytes = await _capturedImage!.readAsBytes();
    final result = _analyzeInIsolate(bytes); // run directly, no isolate
    setState(() {
      _qualityResult = result;
      _isCheckingQuality = false;
    });
  } catch (e) {
    // if analysis fails, just let the user proceed
    setState(() {
      _qualityResult = QualityResult(passed: true, issues: []);
      _isCheckingQuality = false;
    });
  }
}

  Future<void> _saveToDatabase() async {
    if (_capturedImage == null) return;

    setState(() => _isUploading = true);

    try {
      final fileName = 'submission_${DateTime.now().millisecondsSinceEpoch}.jpg';

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
            content: Text('Saved successfully!'),
            backgroundColor: Colors.green,
          ),
        );
        setState(() {
          _capturedImage = null;
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
      _capturedImage = null;
      _qualityResult = null;
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
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        centerTitle: true,
      ),
      body: _capturedImage == null ? _buildCaptureView() : _buildPreviewView(),
    );
  }

  Widget _buildCaptureView() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.document_scanner, size: 100, color: Color(0xFFB71C1C)),
          const SizedBox(height: 24),
          const Text('Capture Handwritten C Code',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          const Text('Take a photo of the student\'s paper',
              style: TextStyle(fontSize: 14, color: Colors.grey)),
          const SizedBox(height: 40),
          ElevatedButton.icon(
            onPressed: _captureImage,
            icon: const Icon(Icons.camera_alt, color: Colors.white),
            label: const Text('Open Camera',
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
        // Image preview
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
              child: Image.file(_capturedImage!, fit: BoxFit.contain),
            ),
          ),
        ),

        // Quality check result banner
        if (_isCheckingQuality)
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                SizedBox(width: 16, height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2)),
                SizedBox(width: 8),
                Text('Checking image quality...'),
              ],
            ),
          ),

        if (!_isCheckingQuality && _qualityResult != null)
          Container(
            width: double.infinity,
            margin: const EdgeInsets.symmetric(horizontal: 16),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              // Green if passed, red if failed
              color: _qualityResult!.passed
                  ? Colors.green.shade50
                  : Colors.red.shade50,
              border: Border.all(
                color: _qualityResult!.passed ? Colors.green : Colors.red,
              ),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
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
                  ],
                ),
                // List each issue found
                ..._qualityResult!.issues.map((issue) => Padding(
                  padding: const EdgeInsets.only(top: 4, left: 26),
                  child: Text('• $issue', style: const TextStyle(fontSize: 13)),
                )),
              ],
            ),
          ),

        const SizedBox(height: 12),

        // Accept / Discard buttons
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          child: Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _isUploading || _isCheckingQuality ? null : _discard,
                  icon: const Icon(Icons.close, color: Colors.red),
                  label: const Text('Discard',
                      style: TextStyle(color: Colors.red, fontSize: 16)),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    side: const BorderSide(color: Colors.red),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: _isUploading || _isCheckingQuality || (_qualityResult != null && !_qualityResult!.passed) ? null : _saveToDatabase,
                  icon: _isUploading
                      ? const SizedBox(
                          width: 20, height: 20,
                          child: CircularProgressIndicator(
                              color: Colors.white, strokeWidth: 2))
                      : const Icon(Icons.check, color: Colors.white),
                  label: Text(
                    _isUploading ? 'Saving...' : 'Accept',
                    style: const TextStyle(color: Colors.white, fontSize: 16),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFB71C1C),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}