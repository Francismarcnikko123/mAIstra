import 'dart:typed_data';
import 'package:image/image.dart' as img;
import 'quality_check.dart';

// Combined check + fix — call this with compute() instead of checkQuality().
// Returns the final QualityResult and, if corrections were applied, the
// corrected image bytes ready to be written to disk.
QualityAndFix checkAndFixQuality(List<int> bytes) {
  final raw = checkQuality(bytes);

  if (raw.decision == QualityDecision.fixable) {
    final fixed = _applyCorrections(bytes, raw);
    if (fixed != null) {
      // Re-evaluate the corrected image so the displayed result is accurate
      final fixedResult = checkQuality(fixed);

      // The histogram stretch widens regional brightness spread along with
      // ink separation, so a page already near kShadowRetake can cross it
      // once corrected. Discard the correction rather than reject a page
      // that was acceptable before it was touched.
      if (fixedResult.decision == QualityDecision.retake) {
        return QualityAndFix(quality: raw, fixedBytes: null);
      }

      return QualityAndFix(
        quality: QualityResult(
          decision: fixedResult.decision,
          issues: fixedResult.issues,
          metrics: fixedResult.metrics,
          autoFixed: true,
        ),
        fixedBytes: fixed,
      );
    }
  }

  return QualityAndFix(quality: raw, fixedBytes: null);
}

class QualityAndFix {
  final QualityResult quality;
  final List<int>? fixedBytes; // null = no correction applied

  const QualityAndFix({required this.quality, required this.fixedBytes});
}

// ── Targeted corrections ──────────────────────────────────────────────────

List<int>? _applyCorrections(List<int> originalBytes, QualityResult result) {
  if (result.decision != QualityDecision.fixable) return null;

  final image = img.decodeImage(Uint8List.fromList(originalBytes));
  if (image == null) return null;

  img.Image out = image;
  final m = result.metrics;

  // 1. De-skew — rotate opposite to detected angle to straighten text lines
  if (m.skewAngleDeg.abs() > kSkewPass) {
    out = img.copyRotate(out, angle: -m.skewAngleDeg);
  }

  // 2. Brightness correction via gamma
  if (m.darkClipFraction > kDarkFixable) {
    out = img.adjustColor(out, gamma: 0.65);
  } else if (m.brightClipFraction > kBrightFixable) {
    out = img.adjustColor(out, gamma: 1.5);
  }

  // 3. Low contrast → histogram stretch
  // Shadow is never fixed here — shadowed scans are rejected at the gate
  // (RETAKE) so JC's grayscale+denoise pipeline always receives clean input.
  if (m.contrastScore < kContrastFixable) {
    out = _histogramStretch(out);
  }

  return img.encodeJpg(out, quality: 92);
}

// ── Global histogram stretch (contrast-only correction) ───────────────────

// Maps the actual min–max luma range to 0–255, boosting faded ink.
// Effective only when illumination is even — use illumination normalize for shadows.
img.Image _histogramStretch(img.Image src) {
  int minL = 255, maxL = 0;
  for (int y = 0; y < src.height; y++) {
    for (int x = 0; x < src.width; x++) {
      final p = src.getPixel(x, y);
      final luma =
          (0.299 * p.r + 0.587 * p.g + 0.114 * p.b).round().clamp(0, 255);
      if (luma < minL) minL = luma;
      if (luma > maxL) maxL = luma;
    }
  }
  if (maxL == minL) return src;

  final range = maxL - minL;
  final result = src.clone();
  for (int y = 0; y < src.height; y++) {
    for (int x = 0; x < src.width; x++) {
      final p = src.getPixel(x, y);
      result.setPixelRgb(
        x,
        y,
        ((p.r - minL) * 255 ~/ range).clamp(0, 255),
        ((p.g - minL) * 255 ~/ range).clamp(0, 255),
        ((p.b - minL) * 255 ~/ range).clamp(0, 255),
      );
    }
  }
  return result;
}
