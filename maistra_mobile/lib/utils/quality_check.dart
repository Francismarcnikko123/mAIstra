import 'dart:typed_data';
import 'package:image/image.dart' as img;

class QualityResult {
  final bool passed;
  final List<String> issues;
  QualityResult({required this.passed, required this.issues});
}

// Mean grayscale pixel value of the whole image — used for too-dark/too-bright.
double computeAvgBrightness(img.Image grayscale) {
  double total = 0;
  for (int y = 0; y < grayscale.height; y++) {
    for (int x = 0; x < grayscale.width; x++) {
      total += grayscale.getPixel(x, y).r.toDouble();
    }
  }
  return total / (grayscale.width * grayscale.height);
}

// Fraction of pixels at or below a "near black" cutoff. Phone auto-exposure
// compensates dim scenes toward a "medium" average, so the average
// brightness alone can't reliably tell a genuinely dark room from a
// well-lit one. Real device data showed this camera's shadow-lifting is
// aggressive enough that literal pure black (<=10) never occurs even in
// genuinely dim rooms — <=50 is where dim and well-lit captures actually
// separate (clean scans measured ~0.0002, dim scans measured 0.10-0.23).
double computeDarkClipFraction(img.Image grayscale, {int threshold = 50}) {
  int clipped = 0;
  for (int y = 0; y < grayscale.height; y++) {
    for (int x = 0; x < grayscale.width; x++) {
      if (grayscale.getPixel(x, y).r <= threshold) clipped++;
    }
  }
  return clipped / (grayscale.width * grayscale.height);
}

// Fraction of pixels at or above a "near white" cutoff — the overexposure
// mirror of computeDarkClipFraction. A flash glare or direct light hits
// sensor saturation locally even when the auto-exposed average brightness
// stays moderate, so this survives auto-exposure compensation the same way.
// Real device data showed literal pure white (>=245) is too strict — >=200
// is where clean and overexposed captures actually separate (clean scans
// measured 0.0, overexposed scans measured 0.11-0.18).
double computeBrightClipFraction(img.Image grayscale, {int threshold = 200}) {
  int clipped = 0;
  for (int y = 0; y < grayscale.height; y++) {
    for (int x = 0; x < grayscale.width; x++) {
      if (grayscale.getPixel(x, y).r >= threshold) clipped++;
    }
  }
  return clipped / (grayscale.width * grayscale.height);
}

// Returns just the top fraction of an image (e.g. the top third). Used to
// measure blur only where handwriting actually is, instead of over the
// whole frame — blank paper below the writing has no texture to measure,
// so including it drags a sharp page's score down and makes blur scores
// incomparable across pages with different amounts of blank space.
img.Image cropTopPortion(img.Image image, {required double fraction}) {
  final cropHeight = (image.height * fraction).round();
  return img.copyCrop(image, x: 0, y: 0, width: image.width, height: cropHeight);
}

// Laplacian-variance sharpness score for the whole image: high for crisp
// edges, low for blurred/flat content. Pulled out of checkQuality so it's
// unit-testable against synthetic patterns.
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

// Decides quality issues and whether Accept should be blocked. Simple,
// deliberately: four checks (blurry, too dark, too bright, otherwise good),
// all measured across the whole photo — no region detection. Split out from
// checkQuality so the threshold logic is unit-testable without synthesizing
// real JPEG pixel data.
//
// Thresholds are from this session's real device captures, 600x600
// analysis size:
// - blurScore < 480: too blurry. Blur is measured on the top-third crop
//   (see cropTopPortion) rather than the whole frame, so blank paper below
//   the writing no longer dilutes the score. Across white bond paper, green
//   book, and yellow pad — clean scans measured 595-873, blurry scans
//   measured 242-374 — this threshold sits in the ~220-point gap between
//   the worst clean score and the worst blurry score.
// - darkClipFraction > 0.05: too dark. Whole-frame average brightness
//   couldn't separate genuinely dim captures from good ones (phone
//   auto-exposure pulls the average toward "medium" regardless), so this
//   checks the fraction of near-black (<=50) pixels instead, which survives
//   that compensation. Real device data across white bond paper and green
//   book: clean scans measured ~0.0002, dim scans measured 0.10-0.23 — this
//   threshold sits well inside that gap.
// - brightClipFraction > 0.05: too bright. Same idea, mirrored: fraction of
//   near-white (>=200) pixels (flash glare, direct light) instead of average
//   brightness, which also couldn't separate overexposed captures from good
//   ones. Real device data across white bond paper, green book, and yellow
//   pad: clean scans measured 0.0, overexposed scans measured 0.11-0.18 —
//   this threshold sits well inside that gap.
QualityResult evaluateQuality({
  required double blurScore,
  required double darkClipFraction,
  required double brightClipFraction,
}) {
  final List<String> issues = [];
  bool blocked = false;

  if (blurScore < 480) {
    issues.add('Image quality too low — hold steady, ensure good lighting, and avoid glare');
    blocked = true;
  }

  if (darkClipFraction > 0.05) {
    issues.add('Too dark — move to a brighter area');
    blocked = true;
  }

  if (brightClipFraction > 0.05) {
    issues.add('Too bright / overexposed — reduce lighting or move away from light source');
    blocked = true;
  }

  return QualityResult(passed: !blocked, issues: issues);
}

// Checks a single image for blur, darkness, and overexposure across the
// whole frame.
QualityResult checkQuality(List<int> bytes) {
  final image = img.decodeImage(Uint8List.fromList(bytes));
  if (image == null) return QualityResult(passed: false, issues: ['Could not read image']);

  final small = img.copyResize(image, width: 600, height: 600);
  final grayscale = img.grayscale(small);

  final avgBrightness = computeAvgBrightness(grayscale);
  final blurScore = computeBlurScore(cropTopPortion(grayscale, fraction: 1 / 3));
  final darkClipFraction = computeDarkClipFraction(grayscale);
  final brightClipFraction = computeBrightClipFraction(grayscale);

  // ignore: avoid_print
  print('[quality-check diagnostic] blurScore=$blurScore avgBrightness=$avgBrightness '
      'darkClipFraction=$darkClipFraction brightClipFraction=$brightClipFraction');
  return evaluateQuality(
    blurScore: blurScore,
    darkClipFraction: darkClipFraction,
    brightClipFraction: brightClipFraction,
  );
}
