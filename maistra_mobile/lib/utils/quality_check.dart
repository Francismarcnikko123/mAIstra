import 'dart:math';
import 'dart:typed_data';
import 'package:image/image.dart' as img;

class QualityResult {
  final bool passed;
  final List<String> issues;
  QualityResult({required this.passed, required this.issues});
}

// Background normalization — run via compute() to avoid blocking UI.
// Estimates illumination from a tiny blurred copy and divides it out,
// flattening shadows without structurally altering ink strokes.
// No levels stretch — removing the stretch improved CER (Round 3 confirmation).
List<int> processDocument(List<int> bytes) {
  final image = img.decodeImage(Uint8List.fromList(bytes));
  if (image == null) return bytes;

  final small = img.copyResize(image, width: 50, height: 50);
  final blurred = img.gaussianBlur(small, radius: 10);
  final illumination = img.copyResize(blurred, width: image.width, height: image.height);

  final normalized = img.Image(width: image.width, height: image.height);
  for (int y = 0; y < image.height; y++) {
    for (int x = 0; x < image.width; x++) {
      final pixel = image.getPixel(x, y);
      final illum = illumination.getPixel(x, y);

      final r = ((pixel.r / (illum.r + 1)) * 255).round().clamp(0, 255);
      final g = ((pixel.g / (illum.g + 1)) * 255).round().clamp(0, 255);
      final b = ((pixel.b / (illum.b + 1)) * 255).round().clamp(0, 255);

      normalized.setPixelRgb(x, y, r, g, b);
    }
  }

  return img.encodeJpg(normalized, quality: 95);
}

// Mean grayscale pixel value of an image/region — used to measure exposure
// (too dark / too bright) scoped to just the content region, not the whole
// frame (see checkQuality for why whole-frame brightness doesn't work: it's
// dominated by however much blank margin happens to be in shot).
double computeAvgBrightness(img.Image grayscale) {
  double total = 0;
  for (int y = 0; y < grayscale.height; y++) {
    for (int x = 0; x < grayscale.width; x++) {
      total += grayscale.getPixel(x, y).r.toDouble();
    }
  }
  return total / (grayscale.width * grayscale.height);
}

// Fraction of pixels in a grayscale image/region darker than inkThreshold —
// a proxy for how much content (ink, printed lines) is on the page. Denser
// pages naturally produce higher raw blur scores independent of actual
// focus (more edges = more variance), so this is being explored as a way
// to normalize blurScore by content density instead of using one fixed
// threshold for every page. Diagnostic only for now — not yet wired into
// evaluateQuality.
double computeInkDensity(img.Image grayscale, {int inkThreshold = 180}) {
  int darkCount = 0;
  for (int y = 0; y < grayscale.height; y++) {
    for (int x = 0; x < grayscale.width; x++) {
      if (grayscale.getPixel(x, y).r < inkThreshold) darkCount++;
    }
  }
  return darkCount / (grayscale.width * grayscale.height);
}

// Laplacian-variance sharpness score for a grayscale image/region: high for
// crisp edges, low for blurred or flat content. Pulled out of checkQuality
// so it can run on either the whole frame or just the ink region, and so
// it's unit-testable against synthetic patterns.
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

// Finds the bounding box of ink-like (dark) pixels in a grayscale image, so
// blur can be measured only where the handwriting actually is instead of
// across the whole frame (which is mostly blank margin). Returns null when
// no content is found.
//
// A pixel only counts if it's part of a run of at least minRunLength
// consecutive dark pixels, horizontally or vertically. This is what makes
// it noise-resistant without needing to blur the image first: random sensor
// noise is spatially independent, so it essentially never lines up several
// pixels in a row by chance, while a real pen stroke — even a thin one —
// always does in at least one direction. (An earlier version pre-blurred
// the image to smooth out noise, but any blur strong enough to remove the
// noise was also strong enough to erase thin strokes — they're a similar
// size. Run-length detection on the original, unblurred image avoids that
// tradeoff entirely.)
Rectangle<int>? findInkBoundingBox(img.Image grayscale, {int inkThreshold = 180, int minRunLength = 4}) {
  int? minX, minY, maxX, maxY;

  void expand(int x, int y) {
    if (minX == null || x < minX!) minX = x;
    if (minY == null || y < minY!) minY = y;
    if (maxX == null || x > maxX!) maxX = x;
    if (maxY == null || y > maxY!) maxY = y;
  }

  bool isDark(int x, int y) => grayscale.getPixel(x, y).r < inkThreshold;

  // Horizontal runs.
  for (int y = 0; y < grayscale.height; y++) {
    int runStart = -1;
    for (int x = 0; x <= grayscale.width; x++) {
      final dark = x < grayscale.width && isDark(x, y);
      if (dark) {
        if (runStart == -1) runStart = x;
      } else if (runStart != -1) {
        if (x - runStart >= minRunLength) {
          for (int rx = runStart; rx < x; rx++) {
            expand(rx, y);
          }
        }
        runStart = -1;
      }
    }
  }

  // Vertical runs.
  for (int x = 0; x < grayscale.width; x++) {
    int runStart = -1;
    for (int y = 0; y <= grayscale.height; y++) {
      final dark = y < grayscale.height && isDark(x, y);
      if (dark) {
        if (runStart == -1) runStart = y;
      } else if (runStart != -1) {
        if (y - runStart >= minRunLength) {
          for (int ry = runStart; ry < y; ry++) {
            expand(x, ry);
          }
        }
        runStart = -1;
      }
    }
  }

  if (minX == null) return null;
  return Rectangle<int>(minX!, minY!, maxX! - minX!, maxY! - minY!);
}

// Decides quality issues and whether Accept should be blocked, given the
// measured blur/brightness. Split out from checkQuality so the threshold
// logic is unit-testable without synthesizing real JPEG pixel data.
//
// Both blurScore and avgBrightness are measured only within the ink region
// (see checkQuality), not the whole frame — whole-frame stats were
// dominated by however much blank margin happened to be in shot.
//
// There is intentionally NO brightness ceiling ("too bright") check.
// Real device testing (5 conditions: good, blurry, and 3 separate
// overexposure attempts including flash-on-document) consistently measured
// brightness in the same ~247-254 range regardless of condition, whole-frame
// or region-scoped — it never once separated good from overexposed. Severe
// overexposure IS still caught, just via the low blurScore check below:
// overexposure collapses local pixel contrast the same way real blur does.
//
// Thresholds calibrated against real device captures with this
// region-scoped, run-length-based measurement:
// - Good (white paper): 4260-8876. Blurry/overexposed: 1695-3587.
// - Ruled/lined paper (exam booklet): a legitimate good scan reached 16361 —
//   printed ruling lines are genuine detail, not noise, and push the score
//   well above what blank paper produces.
// - Covered-camera/no-content (sensor noise, no real structure): always
//   18000+ across three separate tests tonight, spanning two pipeline
//   versions — noise spread across the whole frame reliably scores very high.
// - blurScore < 4000: too blurry (also catches overexposure — see above).
//   Sits between the worst bad sample (3587) and the good range (4260+).
// - blurScore > 20000: no document detected (noise misread as sharpness).
//   Sits between the ruled-paper legitimate max (16361) and the
//   covered-camera minimum ever observed (18000) — reasoned, not yet
//   confirmed with a fresh covered-camera sample against this exact ceiling.
// - A null blurScore (no ink pixels found at all) also means no visible
//   content — "no document detected".
// - avgBrightness < 60: too dark — still unvalidated against a real
//   too-dark failure sample, unchanged all session.
QualityResult evaluateQuality({required double? blurScore, required double avgBrightness}) {
  final List<String> issues = [];
  bool blocked = false;

  if (blurScore == null) {
    issues.add("No document detected — check the camera isn't blocked and try better lighting");
    blocked = true;
  } else {
    if (blurScore < 4000) {
      issues.add('Image quality too low — hold steady, ensure good lighting, and avoid glare');
      blocked = true;
    }
    if (blurScore > 20000) {
      issues.add("No document detected — check the camera isn't blocked and try better lighting");
      blocked = true;
    }
  }

  if (avgBrightness < 60) {
    issues.add('Too dark — move to a brighter area');
    blocked = true;
  }

  return QualityResult(passed: !blocked, issues: issues);
}

// Checks a single image for blur (measured only in the ink region),
// missing content, and darkness.
QualityResult checkQuality(List<int> bytes) {
  final image = img.decodeImage(Uint8List.fromList(bytes));
  if (image == null) return QualityResult(passed: false, issues: ['Could not read image']);

  // 200x200 was too aggressive a downsample for blur detection — it smoothed
  // away fine pen-stroke detail. 600x600 preserves enough detail. Both blur
  // and brightness are measured only within the ink region (see
  // findInkBoundingBox), not this whole frame — whole-frame stats were
  // dominated by however much blank margin happened to be in shot, unrelated
  // to actual sharpness/exposure of the handwriting itself.
  final small = img.copyResize(image, width: 600, height: 600);
  final grayscale = img.grayscale(small);

  final inkBox = findInkBoundingBox(grayscale);

  double? blurScore;
  double? inkDensity;
  double avgBrightness;
  if (inkBox != null) {
    const padding = 20;
    final x0 = (inkBox.left - padding).clamp(0, grayscale.width - 1);
    final y0 = (inkBox.top - padding).clamp(0, grayscale.height - 1);
    final x1 = (inkBox.right + padding).clamp(0, grayscale.width - 1);
    final y1 = (inkBox.bottom + padding).clamp(0, grayscale.height - 1);
    final roi = img.copyCrop(grayscale, x: x0, y: y0, width: x1 - x0 + 1, height: y1 - y0 + 1);
    blurScore = computeBlurScore(roi);
    avgBrightness = computeAvgBrightness(roi);
    inkDensity = computeInkDensity(roi);
  } else {
    // No content region to scope to — fall back to the whole frame so
    // "too dark" can still fire (e.g. a fully covered/black camera).
    avgBrightness = computeAvgBrightness(grayscale);
  }

  // ignore: avoid_print
  print('[quality-check diagnostic] blurScore=$blurScore avgBrightness=$avgBrightness inkBox=$inkBox inkDensity=$inkDensity normalizedBlur=${blurScore != null && inkDensity != null && inkDensity > 0 ? blurScore / inkDensity : null}');
  return evaluateQuality(blurScore: blurScore, avgBrightness: avgBrightness);
}

// Merges the raw-scan check with a check of the same image after
// processing, so defects introduced by normalization aren't missed.
QualityResult combineQualityResults(QualityResult raw, QualityResult processed) {
  return QualityResult(
    passed: raw.passed && processed.passed,
    issues: [
      ...raw.issues,
      ...processed.issues.map((issue) => '(after processing) $issue'),
    ],
  );
}
