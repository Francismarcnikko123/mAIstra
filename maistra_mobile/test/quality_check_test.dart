import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:maistra_mobile/utils/quality_check.dart';

img.Image _whiteImage(int width, int height) {
  final image = img.Image(width: width, height: height);
  for (int y = 0; y < height; y++) {
    for (int x = 0; x < width; x++) {
      image.setPixelRgb(x, y, 255, 255, 255);
    }
  }
  return image;
}

void _fillDark(img.Image image, int x0, int y0, int x1, int y1, {int value = 20}) {
  for (int y = y0; y <= y1; y++) {
    for (int x = x0; x <= x1; x++) {
      image.setPixelRgb(x, y, value, value, value);
    }
  }
}

img.Image _checkerboard(int width, int height, {int cellSize = 4}) {
  final image = img.Image(width: width, height: height);
  for (int y = 0; y < height; y++) {
    for (int x = 0; x < width; x++) {
      final isDark = ((x ~/ cellSize) + (y ~/ cellSize)) % 2 == 0;
      final value = isDark ? 0 : 255;
      image.setPixelRgb(x, y, value, value, value);
    }
  }
  return image;
}

void main() {
  group('computeInkDensity', () {
    test('returns 0 for a blank white image', () {
      final image = _whiteImage(20, 20);

      expect(computeInkDensity(image), 0);
    });

    test('returns 1 for a fully dark image', () {
      final image = _whiteImage(20, 20);
      _fillDark(image, 0, 0, 19, 19);

      expect(computeInkDensity(image), 1);
    });

    test('returns the fraction of dark pixels for a partially dark image', () {
      final image = _whiteImage(10, 10);
      _fillDark(image, 0, 0, 9, 4); // top half (50 of 100 pixels) dark

      expect(computeInkDensity(image), 0.5);
    });
  });

  group('computeAvgBrightness', () {
    test('returns the flat value for a uniform image', () {
      final image = _whiteImage(20, 20);

      expect(computeAvgBrightness(image), 255);
    });

    test('averages a half-black half-white image to the midpoint', () {
      final image = img.Image(width: 20, height: 20);
      for (int y = 0; y < 20; y++) {
        for (int x = 0; x < 20; x++) {
          final value = x < 10 ? 0 : 255;
          image.setPixelRgb(x, y, value, value, value);
        }
      }

      expect(computeAvgBrightness(image), 127.5);
    });
  });

  group('computeBlurScore', () {
    test('scores a flat, uniform image as zero (no detail at all)', () {
      final image = _whiteImage(40, 40);

      final score = computeBlurScore(image);

      expect(score, 0);
    });

    test('scores a sharp high-contrast pattern higher than a blurred version of it', () {
      final sharp = _checkerboard(40, 40);
      final sharpScore = computeBlurScore(sharp);

      // gaussianBlur mutates its argument in place, so score the sharp
      // version first, then blur it and score again.
      final blurred = img.gaussianBlur(sharp, radius: 6);
      final blurredScore = computeBlurScore(blurred);

      expect(sharpScore, greaterThan(blurredScore));
    });
  });

  group('findInkBoundingBox', () {
    test('returns null for a blank white image', () {
      final image = _whiteImage(50, 50);

      final box = findInkBoundingBox(image);

      expect(box, isNull);
    });

    test('finds the bounding box of a single solid dark region', () {
      final image = _whiteImage(50, 50);
      _fillDark(image, 10, 5, 30, 15);

      final box = findInkBoundingBox(image);

      expect(box, isNotNull);
      expect(box!.left, 10);
      expect(box.top, 5);
      expect(box.right, 30);
      expect(box.bottom, 15);
    });

    test('spans from the topmost/leftmost to bottommost/rightmost dark pixel across multiple regions', () {
      final image = _whiteImage(50, 50);
      _fillDark(image, 40, 2, 43, 3);
      _fillDark(image, 5, 44, 8, 47);

      final box = findInkBoundingBox(image);

      expect(box, isNotNull);
      expect(box!.left, 5);
      expect(box.top, 2);
      expect(box.right, 43);
      expect(box.bottom, 47);
    });

    test('does not count pixels right at the paper-white end of the threshold', () {
      final image = _whiteImage(50, 50);
      _fillDark(image, 10, 10, 10, 10, value: 200);

      final box = findInkBoundingBox(image, inkThreshold: 180);

      expect(box, isNull);
    });

    test('ignores scattered isolated noise pixels that never form a run', () {
      final image = _whiteImage(50, 50);
      // Single dark pixels, spaced far apart so none form a run of 4+.
      _fillDark(image, 2, 2, 2, 2);
      _fillDark(image, 20, 30, 20, 30);
      _fillDark(image, 45, 10, 45, 10);
      _fillDark(image, 8, 40, 9, 40); // a 2-pixel run — still below minRunLength

      final box = findInkBoundingBox(image);

      expect(box, isNull);
    });

    test('detects a thin vertical stroke via a column run even though each row is only 1px wide', () {
      final image = _whiteImage(50, 50);
      _fillDark(image, 25, 10, 25, 19); // 1px wide, 10px tall

      final box = findInkBoundingBox(image);

      expect(box, isNotNull);
      expect(box!.left, 25);
      expect(box.top, 10);
      expect(box.right, 25);
      expect(box.bottom, 19);
    });

    test('finds the real ink region and ignores unrelated scattered noise in the same image', () {
      final image = _whiteImage(50, 50);
      _fillDark(image, 2, 2, 2, 2);
      _fillDark(image, 45, 45, 45, 45);
      _fillDark(image, 15, 15, 20, 16); // real ink: 6 wide, 2 tall

      final box = findInkBoundingBox(image);

      expect(box, isNotNull);
      expect(box!.left, 15);
      expect(box.top, 15);
      expect(box.right, 20);
      expect(box.bottom, 16);
    });
  });

  group('evaluateQuality', () {
    test('passes with no issues for a normal, well-formed image', () {
      final result = evaluateQuality(blurScore: 9000, avgBrightness: 150);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('low blur score blocks accept as image quality too low', () {
      final result = evaluateQuality(blurScore: 3999, avgBrightness: 150);

      expect(result.passed, isFalse);
      expect(result.issues, ['Image quality too low — hold steady, ensure good lighting, and avoid glare']);
    });

    test('does not warn when blur score is exactly at the low threshold', () {
      final result = evaluateQuality(blurScore: 4000, avgBrightness: 150);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('implausibly high blur score blocks accept as no document detected', () {
      final result = evaluateQuality(blurScore: 20001, avgBrightness: 150);

      expect(result.passed, isFalse);
      expect(result.issues, ["No document detected — check the camera isn't blocked and try better lighting"]);
    });

    test('does not flag blur score exactly at the high threshold', () {
      final result = evaluateQuality(blurScore: 20000, avgBrightness: 150);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('a legitimate ruled-paper blur score does not block accept', () {
      // Real ruled paper measured 16361 — must stay well clear of the ceiling.
      final result = evaluateQuality(blurScore: 16361, avgBrightness: 150);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('a null blur score (no ink found at all) blocks accept as no document detected', () {
      final result = evaluateQuality(blurScore: null, avgBrightness: 150);

      expect(result.passed, isFalse);
      expect(result.issues, ["No document detected — check the camera isn't blocked and try better lighting"]);
    });

    test('low brightness blocks accept as too dark', () {
      final result = evaluateQuality(blurScore: 9000, avgBrightness: 59);

      expect(result.passed, isFalse);
      expect(result.issues, ['Too dark — move to a brighter area']);
    });

    test('does not flag brightness exactly at the dark threshold', () {
      final result = evaluateQuality(blurScore: 9000, avgBrightness: 60);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('high brightness alone does not block accept — not a reliable signal for this document type', () {
      // Real device testing found brightness clustering in the same ~247-254
      // range across good, blurry, and overexposed (flash-on-document)
      // captures alike — it never separated them, whole-frame or
      // region-scoped. Overexposure is instead caught by the low blur score
      // (severe overexposure collapses local contrast the same way blur
      // does), so there's no separate brightness ceiling.
      final result = evaluateQuality(blurScore: 9000, avgBrightness: 253);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('combines low blur and too-dark blocks together', () {
      final result = evaluateQuality(blurScore: 500, avgBrightness: 50);

      expect(result.passed, isFalse);
      expect(result.issues, [
        'Image quality too low — hold steady, ensure good lighting, and avoid glare',
        'Too dark — move to a brighter area',
      ]);
    });
  });

  group('combineQualityResults', () {
    test('passes when both raw and processed pass', () {
      final raw = QualityResult(passed: true, issues: []);
      final processed = QualityResult(passed: true, issues: []);

      final combined = combineQualityResults(raw, processed);

      expect(combined.passed, isTrue);
      expect(combined.issues, isEmpty);
    });

    test('fails and reports raw issues unprefixed when only raw fails', () {
      final raw = QualityResult(passed: false, issues: ['Blurry image — hold steady and wait for camera to focus']);
      final processed = QualityResult(passed: true, issues: []);

      final combined = combineQualityResults(raw, processed);

      expect(combined.passed, isFalse);
      expect(combined.issues, ['Blurry image — hold steady and wait for camera to focus']);
    });

    test('fails and prefixes processed issues when only processed fails', () {
      final raw = QualityResult(passed: true, issues: []);
      final processed = QualityResult(passed: false, issues: ['Too bright / overexposed — reduce lighting or move away from light source']);

      final combined = combineQualityResults(raw, processed);

      expect(combined.passed, isFalse);
      expect(combined.issues, ['(after processing) Too bright / overexposed — reduce lighting or move away from light source']);
    });

    test('fails and combines both, raw issues first, when both fail', () {
      final raw = QualityResult(passed: false, issues: ['Too dark — move to a brighter area']);
      final processed = QualityResult(passed: false, issues: ['Too bright / overexposed — reduce lighting or move away from light source']);

      final combined = combineQualityResults(raw, processed);

      expect(combined.passed, isFalse);
      expect(combined.issues, [
        'Too dark — move to a brighter area',
        '(after processing) Too bright / overexposed — reduce lighting or move away from light source',
      ]);
    });
  });
}
