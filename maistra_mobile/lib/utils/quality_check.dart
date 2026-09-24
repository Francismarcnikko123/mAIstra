import 'dart:math' as math;
import 'dart:typed_data';
import 'package:image/image.dart' as img;

// ═══════════════════════════════════════════════════════════════════════════
// CALIBRATION THRESHOLDS
// All thresholds live here. Adjust during testing without touching logic.
// ═══════════════════════════════════════════════════════════════════════════

// Blur (Laplacian variance) — higher = sharper
const double kBlurRetake = 200.0; // below → RETAKE

// Dark clip (fraction of pixels ≤ 40/255)
const double kDarkRetake  = 0.15; // above → RETAKE
const double kDarkFixable = 0.08; // above → FIXABLE

// Bright clip (fraction of pixels ≥ 240/255 — glare/overexposure only, not paper background)
const double kBrightRetake  = 0.20; // above → RETAKE
const double kBrightFixable = 0.10; // above → FIXABLE

// Contrast (pixel value standard deviation, 0–255)
// Documents have white background so whole-image stddev is naturally low.
// Calibrated from real scans: visually acceptable ~15+, washed-out ~12-14,
// truly faded <10. Threshold 15 catches soft-looking ink without being too strict.
const double kContrastFixable = 15.0; // below → FIXABLE (ink looks washed-out)

// Shadow (max − min of 3×3 regional brightness averages)
// Clean even-lit scans sit at 13-20. Anything above 25 has a visible gradient.
// Do NOT try to fix shadows — send clean scans to JC's pipeline unchanged.
const double kShadowRetake  = 25.0; // above → RETAKE (rescan with better lighting)
const double kShadowFixable = 999.0; // disabled — shadow is never auto-fixed

// Skew — DISABLED. warpPerspective corrects physical paper tilt before this
// check runs. OCR handles residual text-line skew natively, and empirical
// testing showed our de-skew correction degrades OCR accuracy.
const double kSkewPass   = 999.0; // disabled
const double kSkewRetake = 999.0; // disabled (see kSkewPass comment above)

// ═══════════════════════════════════════════════════════════════════════════

enum QualityDecision { pass, fixable, retake }

class QualityMetrics {
  final double blurScore;
  final double darkClipFraction;
  final double brightClipFraction;
  final double contrastScore;
  final double shadowScore;
  final double skewAngleDeg;

  const QualityMetrics({
    required this.blurScore,
    required this.darkClipFraction,
    required this.brightClipFraction,
    required this.contrastScore,
    required this.shadowScore,
    required this.skewAngleDeg,
  });
}

class QualityResult {
  final QualityDecision decision;
  final List<String> issues;
  final QualityMetrics metrics;
  final bool autoFixed;

  const QualityResult({
    required this.decision,
    required this.issues,
    required this.metrics,
    this.autoFixed = false,
  });

  // PASS and FIXABLE are both acceptable (FIXABLE gets auto-corrected before use)
  bool get passed => decision != QualityDecision.retake;
}

// ── Metric computations ───────────────────────────────────────────────────

double computeBlurScore(img.Image grayscale) {
  double sum = 0, sumSq = 0;
  int count = 0;
  for (int y = 1; y < grayscale.height - 1; y++) {
    for (int x = 1; x < grayscale.width - 1; x++) {
      final c = grayscale.getPixel(x, y).r.toDouble();
      final t = grayscale.getPixel(x, y - 1).r.toDouble();
      final b = grayscale.getPixel(x, y + 1).r.toDouble();
      final l = grayscale.getPixel(x - 1, y).r.toDouble();
      final r = grayscale.getPixel(x + 1, y).r.toDouble();
      final lap = 4 * c - t - b - l - r;
      sum += lap;
      sumSq += lap * lap;
      count++;
    }
  }
  if (count == 0) return 0;
  final mean = sum / count;
  return (sumSq / count) - (mean * mean);
}

double computeDarkClipFraction(img.Image grayscale, {int threshold = 40}) {
  int clipped = 0;
  for (int y = 0; y < grayscale.height; y++)
    for (int x = 0; x < grayscale.width; x++) {
      if (grayscale.getPixel(x, y).r <= threshold) clipped++;
    }
  return clipped / (grayscale.width * grayscale.height);
}

double computeBrightClipFraction(img.Image grayscale, {int threshold = 240}) {
  int clipped = 0;
  for (int y = 0; y < grayscale.height; y++)
    for (int x = 0; x < grayscale.width; x++) {
      if (grayscale.getPixel(x, y).r >= threshold) clipped++;
    }
  return clipped / (grayscale.width * grayscale.height);
}

double computeContrastScore(img.Image grayscale) {
  double sum = 0, sumSq = 0;
  final count = grayscale.width * grayscale.height;
  for (int y = 0; y < grayscale.height; y++)
    for (int x = 0; x < grayscale.width; x++) {
      final v = grayscale.getPixel(x, y).r.toDouble();
      sum += v;
      sumSq += v * v;
    }
  final mean = sum / count;
  return math.sqrt(((sumSq / count) - (mean * mean)).clamp(0, double.maxFinite));
}

double computeShadowScore(img.Image grayscale, {int rows = 3, int cols = 3}) {
  final cellW = grayscale.width ~/ cols;
  final cellH = grayscale.height ~/ rows;
  double? minAvg, maxAvg;
  for (int row = 0; row < rows; row++) {
    for (int col = 0; col < cols; col++) {
      double total = 0;
      int count = 0;
      for (int y = row * cellH; y < (row + 1) * cellH; y++)
        for (int x = col * cellW; x < (col + 1) * cellW; x++) {
          total += grayscale.getPixel(x, y).r.toDouble();
          count++;
        }
      if (count == 0) continue;
      final avg = total / count;
      minAvg = (minAvg == null || avg < minAvg) ? avg : minAvg;
      maxAvg = (maxAvg == null || avg > maxAvg) ? avg : maxAvg;
    }
  }
  return (maxAvg ?? 0) - (minAvg ?? 0);
}

// Projection profile method: rotate image at candidate angles, compute
// variance of horizontal dark-pixel counts per row. The angle that
// maximises variance = text lines are most horizontal = true skew angle.
double computeSkewAngle(img.Image grayscale) {
  final small = img.copyResize(grayscale, width: 300);
  // Threshold: dark pixels (text) = true, light (background) = false
  final List<List<bool>> binary = List.generate(
    small.height,
    (y) => List.generate(small.width, (x) => small.getPixel(x, y).r < 128),
  );

  double bestAngle = 0;
  double bestVariance = -1;

  for (double angle = -20.0; angle <= 20.0; angle += 0.5) {
    final rad = angle * math.pi / 180.0;
    final cosA = math.cos(rad);
    final sinA = math.sin(rad);
    final cx = small.width / 2;
    final cy = small.height / 2;

    // Project: for each pixel, find which row it maps to after rotation
    final proj = List<int>.filled(small.height, 0);
    for (int y = 0; y < small.height; y++) {
      for (int x = 0; x < small.width; x++) {
        if (!binary[y][x]) continue;
        // Rotate point around centre
        final nx = cosA * (x - cx) + sinA * (y - cy) + cx;
        final ny = -sinA * (x - cx) + cosA * (y - cy) + cy;
        final row = ny.round();
        if (row >= 0 && row < small.height) proj[row]++;
      }
    }

    final mean = proj.fold(0, (a, b) => a + b) / proj.length;
    final variance =
        proj.fold(0.0, (a, b) => a + (b - mean) * (b - mean)) / proj.length;

    if (variance > bestVariance) {
      bestVariance = variance;
      bestAngle = angle;
    }
  }
  return bestAngle;
}

img.Image cropTopPortion(img.Image image, {required double fraction}) {
  final h = (image.height * fraction).round();
  return img.copyCrop(image, x: 0, y: 0, width: image.width, height: h);
}

// ── Decision logic ────────────────────────────────────────────────────────

QualityResult evaluateMetrics(QualityMetrics m, {bool autoFixed = false}) {
  final issues = <String>[];
  var decision = QualityDecision.pass;

  void flag(String msg, QualityDecision d) {
    issues.add(msg);
    if (d == QualityDecision.retake) {
      decision = QualityDecision.retake;
    } else if (d == QualityDecision.fixable &&
        decision == QualityDecision.pass) {
      decision = QualityDecision.fixable;
    }
  }

  if (m.blurScore < kBlurRetake) {
    flag('Too blurry — hold the camera steady', QualityDecision.retake);
  }

  if (m.darkClipFraction > kDarkRetake) {
    flag('Too dark — move to a brighter area', QualityDecision.retake);
  } else if (m.darkClipFraction > kDarkFixable)
    flag('Slightly dark — brightness will be auto-adjusted', QualityDecision.fixable);

  if (m.brightClipFraction > kBrightRetake) {
    flag('Severely overexposed — reduce glare or move away from light',
        QualityDecision.retake);
  } else if (m.brightClipFraction > kBrightFixable)
    flag('Overexposed — brightness will be auto-adjusted', QualityDecision.fixable);

  if (m.contrastScore < kContrastFixable) {
    flag('Low contrast / faded ink — contrast will be auto-enhanced',
        QualityDecision.fixable);
  }

  if (m.shadowScore > kShadowRetake) {
    flag('Extreme shadow across page — reposition or use even lighting',
        QualityDecision.retake);
  } else if (m.shadowScore > kShadowFixable)
    flag('Uneven lighting / shadow — will be auto-corrected',
        QualityDecision.fixable);

  final absSkew = m.skewAngleDeg.abs();
  if (absSkew > kSkewRetake) {
    flag(
        'Page too tilted (${m.skewAngleDeg.toStringAsFixed(1)}°) — straighten and rescan',
        QualityDecision.retake);
  } else if (absSkew > kSkewPass)
    flag(
        'Page tilted ${m.skewAngleDeg.toStringAsFixed(1)}° — will be auto de-skewed',
        QualityDecision.fixable);

  return QualityResult(
    decision: decision,
    issues: issues,
    metrics: m,
    autoFixed: autoFixed,
  );
}

// ── Lighting-only check for live camera frames ────────────────────────────

class LumaFrame {
  final Uint8List bytes;
  final int width;
  final int height;
  final int bytesPerRow;
  const LumaFrame({
    required this.bytes,
    required this.width,
    required this.height,
    required this.bytesPerRow,
  });
}

QualityResult checkLightingFrame(LumaFrame frame) {
  final grayscale = img.Image(width: frame.width, height: frame.height);
  for (int y = 0; y < frame.height; y++) {
    final rowStart = y * frame.bytesPerRow;
    for (int x = 0; x < frame.width; x++) {
      final v = frame.bytes[rowStart + x];
      grayscale.setPixelRgb(x, y, v, v, v);
    }
  }
  final dark = computeDarkClipFraction(grayscale);
  final bright = computeBrightClipFraction(grayscale);
  final shadow = computeShadowScore(grayscale);
  final metrics = QualityMetrics(
    blurScore: double.infinity,
    darkClipFraction: dark,
    brightClipFraction: bright,
    contrastScore: double.infinity,
    shadowScore: shadow,
    skewAngleDeg: 0,
  );
  return evaluateMetrics(metrics);
}

// ── Full quality check (runs in compute isolate) ──────────────────────────

QualityResult checkQuality(List<int> bytes) {
  final image = img.decodeImage(Uint8List.fromList(bytes));
  if (image == null) {
    return QualityResult(
      decision: QualityDecision.retake,
      issues: ['Could not read image'],
      metrics: const QualityMetrics(
        blurScore: 0,
        darkClipFraction: 0,
        brightClipFraction: 0,
        contrastScore: 0,
        shadowScore: 0,
        skewAngleDeg: 0,
      ),
    );
  }

  final small = img.copyResize(image, width: 600);
  final gray = img.grayscale(small);

  final blur = computeBlurScore(cropTopPortion(gray, fraction: 1 / 3));
  final dark = computeDarkClipFraction(gray);
  final bright = computeBrightClipFraction(gray);
  final contrast = computeContrastScore(gray);
  final shadow = computeShadowScore(gray);

  // computeSkewAngle is not called: both skew thresholds are disabled, so the
  // angle is never acted on, and the 81-angle projection sweep it runs is the
  // most expensive operation in this function.
  final metrics = QualityMetrics(
    blurScore: blur,
    darkClipFraction: dark,
    brightClipFraction: bright,
    contrastScore: contrast,
    shadowScore: shadow,
    skewAngleDeg: 0,
  );

  // ignore: avoid_print
  print('[quality] blur=${blur.toStringAsFixed(1)}'
      ' dark=${dark.toStringAsFixed(3)}'
      ' bright=${bright.toStringAsFixed(3)}'
      ' contrast=${contrast.toStringAsFixed(1)}'
      ' shadow=${shadow.toStringAsFixed(1)}');

  return evaluateMetrics(metrics);
}
