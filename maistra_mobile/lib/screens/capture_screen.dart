import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:edge_detection/edge_detection.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;
import 'package:supabase_flutter/supabase_flutter.dart';
import '../utils/quality_check.dart';
import '../utils/quality_fix.dart';
import '../models/captured_page.dart';
import 'batch_review_screen.dart';

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  // All scanned pages (accepted + discarded) — shown in batch review
  final List<CapturedPage> _allPages = [];

  File? _currentImage;
  String? _currentOriginalPath;
  QualityResult? _qualityResult;
  bool _isCheckingQuality = false;
  bool _isUploading = false;

  final supabase = Supabase.instance.client;

  Future<void> _scan() async {
    final dir = await getTemporaryDirectory();
    final imagePath =
        p.join(dir.path, '${DateTime.now().millisecondsSinceEpoch}.jpg');

    final captured = await EdgeDetection.detectEdge(
      imagePath,
      canUseGallery: false,
      androidScanTitle: 'Scan Page',
      androidCropTitle: 'Adjust Crop',
      androidCropBlackWhiteTitle: 'B&W',
      androidCropReset: 'Reset',
    );

    if (!captured) return;

    final file = File(imagePath);
    if (!await file.exists()) return;

    // Native CropPresenter saves the pre-warp original alongside the cropped
    // result as <timestamp>_original.jpg.
    final candidateOriginal = imagePath.replaceFirst('.jpg', '_original.jpg');
    final originalExists = await File(candidateOriginal).exists();

    setState(() {
      _isCheckingQuality = true;
      _currentImage = file;
      _currentOriginalPath = originalExists ? candidateOriginal : null;
      _qualityResult = null;
    });

    final bytes = await file.readAsBytes();
    final qa = await compute(checkAndFixQuality, bytes);

    // If auto-corrected, save fixed image and use that
    File resultFile = file;
    if (qa.fixedBytes != null) {
      final fixedPath = file.path.replaceFirst('.jpg', '_fixed.jpg');
      resultFile = File(fixedPath);
      await resultFile.writeAsBytes(qa.fixedBytes!);
    }

    setState(() {
      _currentImage = resultFile;
      _qualityResult = qa.quality;
      _isCheckingQuality = false;
    });
  }

  Future<void> _batchFromGallery() async {
    final picker = ImagePicker();
    final picked = await picker.pickMultiImage(imageQuality: 100);
    if (picked.isEmpty) return;

    final dir = await getTemporaryDirectory();

    // Build output paths
    final ts = DateTime.now().millisecondsSinceEpoch;
    final inputPaths = picked.map((x) => x.path).toList();
    final outputPaths = List.generate(
      picked.length,
      (i) => p.join(dir.path, '${ts}_batch_$i.jpg'),
    );

    // Show processing indicator
    setState(() => _isCheckingQuality = true);

    try {
      final results = await EdgeDetection.batchProcessImages(
        inputPaths: inputPaths,
        outputPaths: outputPaths,
      );

      // Quality-check + auto-fix each processed image
      final pages = <CapturedPage>[];
      for (int i = 0; i < results.length; i++) {
        final outPath = outputPaths[i];
        final file = File(outPath);

        if (!results[i] || !await file.exists()) {
          // Edge detection couldn't find page corners — copy original into temp
          // and surface as a retake so user can fix it via Recrop.
          final origPath = inputPaths[i];
          final fallbackPath = outPath.replaceFirst('.jpg', '_orig.jpg');
          try {
            await File(origPath).copy(fallbackPath);
            pages.add(CapturedPage(
              file: File(fallbackPath),
              quality: QualityResult(
                decision: QualityDecision.retake,
                issues: ['Page edges not detected — tap Recrop to adjust manually'],
                metrics: const QualityMetrics(
                  blurScore: 0,
                  darkClipFraction: 0,
                  brightClipFraction: 0,
                  contrastScore: 0,
                  shadowScore: 0,
                  skewAngleDeg: 0,
                ),
              ),
              accepted: false,
              originalPath: origPath,
            ));
          } catch (_) {}
          continue;
        }

        final bytes = await file.readAsBytes();
        final qa = await compute(checkAndFixQuality, bytes);

        File pageFile = file;
        if (qa.fixedBytes != null) {
          final fixedPath = outPath.replaceFirst('.jpg', '_fixed.jpg');
          pageFile = File(fixedPath);
          await pageFile.writeAsBytes(qa.fixedBytes!);
        }

        pages.add(CapturedPage(
          file: pageFile,
          quality: qa.quality,
          accepted: qa.quality.passed,
          originalPath: inputPaths[i], // original gallery photo for Recrop
        ));
      }

      setState(() {
        _allPages.addAll(pages);
        _isCheckingQuality = false;
      });

      if (pages.isNotEmpty && mounted) {
        _openBatchReview();
      }
    } catch (e) {
      setState(() => _isCheckingQuality = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Batch processing failed: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  void _acceptCurrent() {
    if (_currentImage == null || _qualityResult == null) return;
    setState(() {
      _allPages.add(CapturedPage(
        file: _currentImage!,
        quality: _qualityResult!,
        accepted: true,
        originalPath: _currentOriginalPath,
      ));
      _currentImage = null;
      _currentOriginalPath = null;
      _qualityResult = null;
    });
  }

  void _discardCurrent() {
    if (_currentImage == null || _qualityResult == null) return;
    // Still track discarded pages so they appear in batch review as "bad"
    setState(() {
      _allPages.add(CapturedPage(
        file: _currentImage!,
        quality: _qualityResult!,
        accepted: false,
        originalPath: _currentOriginalPath,
      ));
      _currentImage = null;
      _currentOriginalPath = null;
      _qualityResult = null;
    });
  }

  void _rescanCurrent() {
    // Discard the rejected image silently and immediately reopen the camera
    setState(() {
      _currentImage = null;
      _currentOriginalPath = null;
      _qualityResult = null;
    });
    _scan();
  }

  Future<void> _openBatchReview() async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => BatchReviewScreen(pages: _allPages),
      ),
    );
    // Refresh after user may have toggled selections in batch review
    setState(() {});
  }

  Future<void> _uploadAll() async {
    final toUpload = _allPages.where((p) => p.accepted).toList();
    if (toUpload.isEmpty) return;
    setState(() => _isUploading = true);

    try {
      for (final page in toUpload) {
        final bytes = await page.file.readAsBytes();
        final fileName =
            'submission_${DateTime.now().millisecondsSinceEpoch}.jpg';
        await supabase.storage
            .from('handwritten-submissions')
            .uploadBinary(fileName, bytes);
        final imageUrl = supabase.storage
            .from('handwritten-submissions')
            .getPublicUrl(fileName);
        await supabase.from('submissions').insert({
          'image_url': imageUrl,
          'status': 'pending',
        });
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('${toUpload.length} page(s) uploaded successfully!'),
            backgroundColor: Colors.green,
          ),
        );
        setState(() => _allPages.clear());
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Upload failed: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      setState(() => _isUploading = false);
    }
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
      body: _currentImage != null || _isCheckingQuality
          ? _buildReviewView()
          : _buildScanView(),
    );
  }

  Widget _buildScanView() {
    final goodCount = _allPages.where((p) => p.quality.passed).length;
    final badCount = _allPages.length - goodCount;
    final acceptedCount = _allPages.where((p) => p.accepted).length;

    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24),
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
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              _allPages.isEmpty
                  ? 'Place the paper on a flat surface and scan'
                  : '$goodCount good  •  $badCount bad  •  ${_allPages.length} scanned',
              style: const TextStyle(fontSize: 14, color: Colors.grey),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 40),
            // Scan button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _isUploading || _isCheckingQuality ? null : _scan,
                icon: const Icon(Icons.document_scanner, color: Colors.white),
                label: Text(
                  _allPages.isEmpty ? 'Scan Document' : 'Scan Another Page',
                  style: const TextStyle(color: Colors.white, fontSize: 16),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFB71C1C),
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
            // Batch from Gallery button
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _isUploading || _isCheckingQuality
                    ? null
                    : _batchFromGallery,
                icon: _isCheckingQuality
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Color(0xFFB71C1C),
                        ),
                      )
                    : const Icon(
                        Icons.photo_library,
                        color: Color(0xFFB71C1C),
                      ),
                label: Text(
                  _isCheckingQuality
                      ? 'Processing images...'
                      : 'Batch from Gallery',
                  style: const TextStyle(
                    color: Color(0xFFB71C1C),
                    fontSize: 16,
                  ),
                ),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  side: const BorderSide(color: Color(0xFFB71C1C)),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ),
            if (_allPages.isNotEmpty) ...[
              const SizedBox(height: 12),
              // Review All button
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: _isUploading ? null : _openBatchReview,
                  icon: const Icon(
                    Icons.grid_view,
                    color: Color(0xFFB71C1C),
                  ),
                  label: Text(
                    'Review ${_allPages.length} Page(s)  ($goodCount good / $badCount bad)',
                    style: const TextStyle(
                      color: Color(0xFFB71C1C),
                      fontSize: 15,
                    ),
                  ),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    side: const BorderSide(color: Color(0xFFB71C1C)),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                ),
              ),
              if (acceptedCount > 0) ...[
                const SizedBox(height: 12),
                // Upload button
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _isUploading ? null : _uploadAll,
                    icon: _isUploading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 2,
                            ),
                          )
                        : const Icon(Icons.cloud_upload, color: Colors.white),
                    label: Text(
                      _isUploading
                          ? 'Uploading...'
                          : 'Upload $acceptedCount Page(s)',
                      style: const TextStyle(color: Colors.white, fontSize: 16),
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildQualityBanner(QualityResult r) {
    final Color bg, border, iconColor;
    final IconData icon;
    final String title;

    switch (r.decision) {
      case QualityDecision.pass:
        bg = Colors.green.shade50;
        border = Colors.green;
        iconColor = Colors.green;
        icon = Icons.check_circle;
        title = r.autoFixed ? 'Auto-corrected — ready to accept' : 'Image quality is good';
        break;
      case QualityDecision.fixable:
        bg = Colors.orange.shade50;
        border = Colors.orange;
        iconColor = Colors.orange;
        icon = Icons.auto_fix_high;
        title = 'Auto-corrections applied';
        break;
      case QualityDecision.retake:
        bg = Colors.red.shade50;
        border = Colors.red;
        iconColor = Colors.red;
        icon = Icons.warning;
        title = 'Quality issues — please retake';
        break;
    }

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: bg,
        border: Border.all(color: border),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: iconColor, size: 18),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: iconColor,
                  ),
                ),
              ),
            ],
          ),
          ...r.issues.map(
            (issue) => Padding(
              padding: const EdgeInsets.only(top: 4, left: 26),
              child: Text('• $issue', style: const TextStyle(fontSize: 13)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildReviewView() {
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
              child: _currentImage != null
                  ? Image.file(_currentImage!, fit: BoxFit.contain)
                  : const SizedBox(),
            ),
          ),
        ),

        if (_isCheckingQuality)
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                SizedBox(width: 8),
                Text('Checking image quality...'),
              ],
            ),
          ),

        if (!_isCheckingQuality && _qualityResult != null)
          _buildQualityBanner(_qualityResult!),

        const SizedBox(height: 12),

        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          child: Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _isCheckingQuality ? null : _discardCurrent,
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
                child: _qualityResult?.decision == QualityDecision.retake
                    ? ElevatedButton.icon(
                        onPressed: _isCheckingQuality ? null : _rescanCurrent,
                        icon: const Icon(Icons.camera_alt, color: Colors.white),
                        label: const Text(
                          'Rescan',
                          style: TextStyle(color: Colors.white, fontSize: 16),
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFFB71C1C),
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                      )
                    : ElevatedButton.icon(
                        onPressed: _isCheckingQuality ? null : _acceptCurrent,
                        icon: const Icon(Icons.check, color: Colors.white),
                        label: const Text(
                          'Accept',
                          style: TextStyle(color: Colors.white, fontSize: 16),
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
        ),
      ],
    );
  }
}
