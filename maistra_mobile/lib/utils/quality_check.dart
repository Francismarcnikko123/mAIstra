import 'dart:typed_data';
import 'package:image/image.dart' as img;

class QualityResult {
  final bool passed;
  final List<String> issues;
  QualityResult({required this.passed, required this.issues});
}

// % of near-black pixels. More reliable than average brightness, since
// phone auto-exposure hides genuine darkness by brightening the average.
double computeDarkClipFraction(img.Image grayscale, {int threshold = 50}) {
  int clipped = 0;
  for (int y = 0; y < grayscale.height; y++) {
    for (int x = 0; x < grayscale.width; x++) {
      if (grayscale.getPixel(x, y).r <= threshold) clipped++;
    }
  }
  return clipped / (grayscale.width * grayscale.height);
}

// Same idea, mirrored for overexposure (flash glare, direct light).
double computeBrightClipFraction(img.Image grayscale, {int threshold = 200}) {
  int clipped = 0;
  for (int y = 0; y < grayscale.height; y++) {
    for (int x = 0; x < grayscale.width; x++) {
      if (grayscale.getPixel(x, y).r >= threshold) clipped++;
    }
  }
  return clipped / (grayscale.width * grayscale.height);
}

// Splits the frame into a rows x cols grid and returns the gap between the
// brightest and darkest region's average — catches a localized shadow that
// a whole-frame check would average away.
double computeBrightnessSpread(img.Image grayscale, {required int rows, required int cols}) {
  final cellWidth = grayscale.width ~/ cols;
  final cellHeight = grayscale.height ~/ rows;

  double? minAvg;
  double? maxAvg;

  for (int row = 0; row < rows; row++) {
    for (int col = 0; col < cols; col++) {
      double total = 0;
      int count = 0;
      for (int y = row * cellHeight; y < (row + 1) * cellHeight; y++) {
        for (int x = col * cellWidth; x < (col + 1) * cellWidth; x++) {
          total += grayscale.getPixel(x, y).r.toDouble();
          count++;
        }
      }
      if (count == 0) continue;
      final avg = total / count;
      minAvg = (minAvg == null) ? avg : (avg < minAvg ? avg : minAvg);
      maxAvg = (maxAvg == null) ? avg : (avg > maxAvg ? avg : maxAvg);
    }
  }

  if (minAvg == null || maxAvg == null) return 0;
  return maxAvg - minAvg;
}

// Top third of the frame — blur is measured here only, so blank paper
// below the handwriting doesn't dilute the score.
img.Image cropTopPortion(img.Image image, {required double fraction}) {
  final cropHeight = (image.height * fraction).round();
  return img.copyCrop(image, x: 0, y: 0, width: image.width, height: cropHeight);
}

// Laplacian-variance sharpness — high for crisp edges, low for blur.
double computeBlurScore(img.Image grayscale) {
  double laplacianSum = 0;
  double laplacianSumSquares = 0;
  int count = 0;

  for (int y = 1; y < grayscale.height - 1; y++) {
    for (int x = 1; x < grayscale.width - 1; x++) {
      final center = grayscale.getPixel(x, y).r.toDouble();
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

  if (count == 0) return 0;
  final mean = laplacianSum / count;
  return (laplacianSumSquares / count) - (mean * mean);
}

// Dark/bright/shadow checks only — no blur. Used by both the final gate
// and the live pre-check screen, which can't measure blur from a preview frame.
QualityResult evaluateLighting({
  required double darkClipFraction,
  required double brightClipFraction,
  required double brightnessSpread,
}) {
  final List<String> issues = [];
  bool blocked = false;

  if (darkClipFraction > 0.05) {
    issues.add('Too dark — move to a brighter area');
    blocked = true;
  }

  if (brightClipFraction > 0.20) {
    issues.add('Too bright / overexposed — reduce lighting or move away from light source');
    blocked = true;
  }

  if (brightnessSpread > 35) {
    issues.add("Uneven lighting detected — try repositioning so your shadow isn't blocking the page");
    blocked = true;
  }

  return QualityResult(passed: !blocked, issues: issues);
}

// Thresholds calibrated against real device captures across white bond
// paper, green book, and yellow pad

QualityResult evaluateQuality({
  required double blurScore,
  required double darkClipFraction,
  required double brightClipFraction,
  required double brightnessSpread,
}) {
  final List<String> issues = [];
  bool blocked = false;

  if (blurScore < 480) {
    issues.add('Image quality too low — hold steady, ensure good lighting, and avoid glare');
    blocked = true;
  }

  final lighting = evaluateLighting(
    darkClipFraction: darkClipFraction,
    brightClipFraction: brightClipFraction,
    brightnessSpread: brightnessSpread,
  );
  issues.addAll(lighting.issues);
  if (!lighting.passed) blocked = true;

  return QualityResult(passed: !blocked, issues: issues);
}

QualityResult checkQuality(List<int> bytes) {
  final image = img.decodeImage(Uint8List.fromList(bytes));
  if (image == null) return QualityResult(passed: false, issues: ['Could not read image']);

  final small = img.copyResize(image, width: 600, height: 600);
  final grayscale = img.grayscale(small);

  final blurScore = computeBlurScore(cropTopPortion(grayscale, fraction: 1 / 3));
  final darkClipFraction = computeDarkClipFraction(grayscale);
  final brightClipFraction = computeBrightClipFraction(grayscale);
  final brightnessSpread = computeBrightnessSpread(grayscale, rows: 3, cols: 3);

  // ignore: avoid_print
  print('[quality-check] ----------------------------------------');
  // ignore: avoid_print
  print('[quality-check] dimensions:        ${image.width}x${image.height}');
  // ignore: avoid_print
  print('[quality-check] blurScore:         ${blurScore.toStringAsFixed(1)}');
  // ignore: avoid_print
  print('[quality-check] darkClipFraction:  ${darkClipFraction.toStringAsFixed(4)}');
  // ignore: avoid_print
  print('[quality-check] brightClipFraction:${brightClipFraction.toStringAsFixed(4)}');
  // ignore: avoid_print
  print('[quality-check] brightnessSpread:  ${brightnessSpread.toStringAsFixed(1)}');

  return evaluateQuality(
    blurScore: blurScore,
    darkClipFraction: darkClipFraction,
    brightClipFraction: brightClipFraction,
    brightnessSpread: brightnessSpread,
  );
}

// One Y-plane (luma) sample from a live YUV420 camera frame. bytesPerRow
// can be wider than width — camera plugins pad rows to an alignment
// boundary, so it can't be assumed equal to width.
class LumaFrame {
  final Uint8List bytes;
  final int width;
  final int height;
  final int bytesPerRow;
  LumaFrame({
    required this.bytes,
    required this.width,
    required this.height,
    required this.bytesPerRow,
  });
}

// Lighting check straight off a live camera frame — the Y-plane of a
// YUV420 frame is already grayscale brightness data, so no JPEG decode
// or color conversion is needed like checkQuality does.
QualityResult checkLightingFrame(LumaFrame frame) {
  final grayscale = img.Image(width: frame.width, height: frame.height);
  for (int y = 0; y < frame.height; y++) {
    final rowStart = y * frame.bytesPerRow;
    for (int x = 0; x < frame.width; x++) {
      final v = frame.bytes[rowStart + x];
      grayscale.setPixelRgb(x, y, v, v, v);
    }
  }

  return evaluateLighting(
    darkClipFraction: computeDarkClipFraction(grayscale),
    brightClipFraction: computeBrightClipFraction(grayscale),
    brightnessSpread: computeBrightnessSpread(grayscale, rows: 3, cols: 3),
  );
}
