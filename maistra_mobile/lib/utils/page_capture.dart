import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:edge_detection/edge_detection.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;
import '../models/captured_page.dart';
import 'quality_check.dart';
import 'quality_fix.dart';

/// Opens the edge-detection scanner for one page. Returns null when the
/// student backs out. The quality gate runs on a background isolate
/// exactly as before; [onScanned] fires once the photo exists, before the
/// gate finishes, so the UI can show it while checking.
Future<CapturedPage?> scanPage({void Function(File file)? onScanned}) async {
  final dir = await getTemporaryDirectory();
  final imagePath = p.join(
    dir.path,
    '${DateTime.now().millisecondsSinceEpoch}.jpg',
  );

  final captured = await EdgeDetection.detectEdge(
    imagePath,
    canUseGallery: false,
    androidScanTitle: 'Scan Page',
    androidCropTitle: 'Adjust Crop',
    androidCropBlackWhiteTitle: 'B&W',
    androidCropReset: 'Reset',
  );
  if (!captured) return null;

  final file = File(imagePath);
  if (!await file.exists()) return null;
  onScanned?.call(file);

  // Native CropPresenter saves the pre-warp original alongside the cropped
  // result as <timestamp>_original.jpg.
  final candidateOriginal = imagePath.replaceFirst('.jpg', '_original.jpg');
  final originalExists = await File(candidateOriginal).exists();

  return _gate(file, originalExists ? candidateOriginal : null);
}

/// Picks several photos from the gallery, crops each, and runs the gate.
/// Returns an empty list when the student picks nothing.
Future<List<CapturedPage>> importFromGallery() async {
  final picked = await ImagePicker().pickMultiImage(imageQuality: 100);
  if (picked.isEmpty) return [];

  final dir = await getTemporaryDirectory();
  final ts = DateTime.now().millisecondsSinceEpoch;
  final inputPaths = picked.map((x) => x.path).toList();
  final outputPaths = List.generate(
    picked.length,
    (i) => p.join(dir.path, '${ts}_batch_$i.jpg'),
  );

  final results = await EdgeDetection.batchProcessImages(
    inputPaths: inputPaths,
    outputPaths: outputPaths,
  );

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
        pages.add(
          CapturedPage(
            file: File(fallbackPath),
            quality: QualityResult(
              decision: QualityDecision.retake,
              issues: [
                'Page edges not detected — tap Recrop to adjust manually',
              ],
              metrics: const QualityMetrics(
                blurScore: 0,
                darkClipFraction: 0,
                brightClipFraction: 0,
                contrastScore: 0,
                shadowScore: 0,
                skewAngleDeg: 0,
              ),
            ),
            originalPath: origPath,
          ),
        );
      } catch (_) {}
      continue;
    }

    // Original gallery photo is kept for Recrop.
    pages.add(await _gate(file, inputPaths[i]));
  }
  return pages;
}

/// Re-crops a page from its original photo and re-runs the gate.
Future<CapturedPage?> recropPage(CapturedPage page) async {
  final dir = await getTemporaryDirectory();
  final saveTo = p.join(
    dir.path,
    'recrop_${DateTime.now().millisecondsSinceEpoch}.jpg',
  );
  final ok = await EdgeDetection.recropImage(
    inputPath: page.originalPath ?? page.file.path,
    saveTo: saveTo,
  );
  if (!ok) return null;
  final file = File(saveTo);
  if (!await file.exists()) return null;
  // Same check -> auto-fix -> re-check as a scanned page, so a recropped
  // FIXABLE page is corrected before upload like every other page.
  return _gate(file, page.originalPath);
}

Future<CapturedPage> _gate(File file, String? originalPath) async {
  final bytes = await file.readAsBytes();
  final qa = await compute(checkAndFixQuality, bytes);

  // If auto-corrected, save fixed image and use that
  var resultFile = file;
  if (qa.fixedBytes != null) {
    resultFile = File(file.path.replaceFirst('.jpg', '_fixed.jpg'));
    await resultFile.writeAsBytes(qa.fixedBytes!);
  }
  return CapturedPage(
    file: resultFile,
    quality: qa.quality,
    originalPath: originalPath,
  );
}
