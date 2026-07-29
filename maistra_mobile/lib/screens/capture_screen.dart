import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:cunning_document_scanner/cunning_document_scanner.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:image/image.dart' as img;
import 'dart:typed_data';

// Document enhancement: background normalization + contrast stretching.
// Step 1 — Background normalization: estimates the illumination map by
//   downsampling + blurring, then divides each pixel by it. This flattens
//   shadows and uneven lighting.
// Step 2 — Levels stretch: maps the [30, 215] range to [0, 255] so the
//   paper background becomes pure white and ink becomes darker.
//   This is what CamScanner's "Enhance" mode does under the hood.
img.Image _processDocument(img.Image source) {
  // Step 1: Estimate background illumination via tiny blurred copy
  final tiny = img.copyResize(source, width: 50, height: 50);
  final tinyBlurred = img.gaussianBlur(tiny, radius: 10);
  final bgMap = img.copyResize(
    tinyBlurred,
    width: source.width,
    height: source.height,
    interpolation: img.Interpolation.linear,
  );

  final result = source.clone();
  for (int y = 0; y < source.height; y++) {
    for (int x = 0; x < source.width; x++) {
      final pixel = source.getPixel(x, y);
      final bg = bgMap.getPixel(x, y);

      // Normalize by background
      double r = bg.r > 10 ? (pixel.r / bg.r * 255).clamp(0, 255) : pixel.r.toDouble();
      double g = bg.g > 10 ? (pixel.g / bg.g * 255).clamp(0, 255) : pixel.g.toDouble();
      double b = bg.b > 10 ? (pixel.b / bg.b * 255).clamp(0, 255) : pixel.b.toDouble();

      // Step 2: Levels stretch — maps [30, 215] → [0, 255]
      // Anything ≥215 becomes pure white; anything ≤30 becomes pure black
      r = ((r - 30) / (215 - 30) * 255).clamp(0, 255);
      g = ((g - 30) / (215 - 30) * 255).clamp(0, 255);
      b = ((b - 30) / (215 - 30) * 255).clamp(0, 255);

      result.setPixelRgb(x, y, r.toInt(), g.toInt(), b.toInt());
    }
  }
  return result;
}

// Quality check runs on the RAW scan (before thresholding) for accurate detection
class QualityResult {
  final bool passed;
  final List<String> issues;
  QualityResult({required this.passed, required this.issues});
}

QualityResult _checkQuality(List<int> bytes) {
  final image = img.decodeImage(Uint8List.fromList(bytes));
  if (image == null) return QualityResult(passed: false, issues: ['Could not read image']);

  final small = img.copyResize(image, width: 200, height: 200);
  final grayscale = img.grayscale(small);

  double totalBrightness = 0;
  double laplacianSum = 0;
  double laplacianSumSquares = 0;
  int count = 0;

  for (int y = 1; y < grayscale.height - 1; y++) {
    for (int x = 1; x < grayscale.width - 1; x++) {
      final center = grayscale.getPixel(x, y).r.toDouble();
      totalBrightness += center;

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

  print('Blur score: $blurScore');
  print('Avg brightness: $avgBrightness');

  final List<String> issues = [];
  if (blurScore < 800) issues.add('Blurry image — hold steady and wait for camera to focus');
  if (avgBrightness < 60) issues.add('Too dark — move to a brighter area');

  return QualityResult(passed: issues.isEmpty, issues: issues);
}

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

      // Run quality check + image processing in background isolate
      // (prevents blocking the UI thread / ANR crash)
      final result = await compute(_checkQuality, rawBytes);

      final rawImage = img.decodeImage(Uint8List.fromList(rawBytes));
      File processedFile;
      if (rawImage != null) {
        final cleaned = await compute(_processDocument, rawImage);
        final cleanedBytes = img.encodeJpg(cleaned, quality: 95);
        final tempPath = '${rawFile.parent.path}/cleaned_${rawFile.uri.pathSegments.last}';
        processedFile = await File(tempPath).writeAsBytes(cleanedBytes);
      } else {
        processedFile = rawFile;
      }

      setState(() {
        _scannedImage = processedFile;
        _qualityResult = result;
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
              Text('Processing scan...'),
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
