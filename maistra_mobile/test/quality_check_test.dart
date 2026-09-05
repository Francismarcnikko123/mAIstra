import 'dart:typed_data';
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

  group('cropTopPortion', () {
    test('keeps only the top fraction of the image, preserving width', () {
      final image = _whiteImage(30, 30);

      final cropped = cropTopPortion(image, fraction: 1 / 3);

      expect(cropped.width, 30);
      expect(cropped.height, 10);
    });

    test('rounds a fractional crop height to the nearest pixel', () {
      final image = _whiteImage(10, 100);

      final cropped = cropTopPortion(image, fraction: 1 / 3);

      expect(cropped.height, 33);
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

  group('computeDarkClipFraction', () {
    test('returns 1 when every pixel is pure black', () {
      final image = img.Image(width: 10, height: 10);
      for (int y = 0; y < 10; y++) {
        for (int x = 0; x < 10; x++) {
          image.setPixelRgb(x, y, 0, 0, 0);
        }
      }

      expect(computeDarkClipFraction(image), 1.0);
    });

    test('returns 0 when no pixels are near black', () {
      final image = _whiteImage(10, 10);

      expect(computeDarkClipFraction(image), 0.0);
    });

    test('returns the fraction of pixels at or below the clip threshold', () {
      final image = img.Image(width: 10, height: 10);
      for (int y = 0; y < 10; y++) {
        for (int x = 0; x < 10; x++) {
          final value = y < 3 ? 0 : 200; // 3 of 10 rows are pure black
          image.setPixelRgb(x, y, value, value, value);
        }
      }

      expect(computeDarkClipFraction(image), closeTo(0.3, 0.001));
    });
  });

  group('computeBrightClipFraction', () {
    test('returns 1 when every pixel is pure white', () {
      final image = _whiteImage(10, 10);

      expect(computeBrightClipFraction(image), 1.0);
    });

    test('returns 0 when no pixels are near white', () {
      final image = img.Image(width: 10, height: 10);
      for (int y = 0; y < 10; y++) {
        for (int x = 0; x < 10; x++) {
          image.setPixelRgb(x, y, 0, 0, 0);
        }
      }

      expect(computeBrightClipFraction(image), 0.0);
    });

    test('returns the fraction of pixels at or above the clip threshold', () {
      final image = img.Image(width: 10, height: 10);
      for (int y = 0; y < 10; y++) {
        for (int x = 0; x < 10; x++) {
          final value = y < 2 ? 255 : 100; // 2 of 10 rows are pure white
          image.setPixelRgb(x, y, value, value, value);
        }
      }

      expect(computeBrightClipFraction(image), closeTo(0.2, 0.001));
    });
  });

  group('computeBrightnessSpread', () {
    test('returns 0 for a uniformly bright image', () {
      final image = _whiteImage(30, 30);

      expect(computeBrightnessSpread(image, rows: 3, cols: 3), 0);
    });

    test('returns a large spread when one region is much darker than the rest', () {
      final image = img.Image(width: 30, height: 30);
      for (int y = 0; y < 30; y++) {
        for (int x = 0; x < 30; x++) {
          // Bottom-left third dark (shadow-like), rest bright.
          final inShadow = x < 10 && y >= 20;
          final value = inShadow ? 60 : 200;
          image.setPixelRgb(x, y, value, value, value);
        }
      }

      expect(computeBrightnessSpread(image, rows: 3, cols: 3), closeTo(140, 0.001));
    });
  });

  group('computeCornerMismatch', () {
    test('returns 0 for a perfectly uniform image', () {
      final image = _whiteImage(100, 100);

      expect(computeCornerMismatch(image, patchFraction: 0.1), 0.0);
    });

    test('returns a large value when corners are much darker than the center', () {
      final image = img.Image(width: 100, height: 100);
      for (int y = 0; y < 100; y++) {
        for (int x = 0; x < 100; x++) {
          // Dark borders (simulating desk/background at edges), bright center.
          final inCornerRegion = x < 15 || x >= 85 || y < 15 || y >= 85;
          final value = inCornerRegion ? 20 : 220;
          image.setPixelRgb(x, y, value, value, value);
        }
      }

      expect(computeCornerMismatch(image, patchFraction: 0.1), greaterThan(70));
    });

    test('returns a small value when corners match the center closely', () {
      final image = img.Image(width: 100, height: 100);
      for (int y = 0; y < 100; y++) {
        for (int x = 0; x < 100; x++) {
          // Slight vignette — corners slightly darker but within paper range.
          final inCornerRegion = x < 15 || x >= 85 || y < 15 || y >= 85;
          final value = inCornerRegion ? 190 : 220;
          image.setPixelRgb(x, y, value, value, value);
        }
      }

      expect(computeCornerMismatch(image, patchFraction: 0.1), lessThan(70));
    });
  });

  group('evaluateQuality', () {
    test('passes with no issues for a normal, well-formed image', () {
      final result = evaluateQuality(
          blurScore: 9000, darkClipFraction: 0, brightClipFraction: 0, brightnessSpread: 0, cornerMismatch: 0);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('low blur score blocks accept as image quality too low', () {
      final result = evaluateQuality(
          blurScore: 479, darkClipFraction: 0, brightClipFraction: 0, brightnessSpread: 0, cornerMismatch: 0);

      expect(result.passed, isFalse);
      expect(result.issues, ['Image quality too low — hold steady, ensure good lighting, and avoid glare']);
    });

    test('does not flag blur score exactly at the low threshold', () {
      final result = evaluateQuality(
          blurScore: 480, darkClipFraction: 0, brightClipFraction: 0, brightnessSpread: 0, cornerMismatch: 0);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('high dark-clip fraction blocks accept as too dark', () {
      final result = evaluateQuality(
          blurScore: 9000, darkClipFraction: 0.06, brightClipFraction: 0, brightnessSpread: 0, cornerMismatch: 0);

      expect(result.passed, isFalse);
      expect(result.issues, ['Too dark — move to a brighter area']);
    });

    test('does not flag dark-clip fraction exactly at the threshold', () {
      final result = evaluateQuality(
          blurScore: 9000, darkClipFraction: 0.05, brightClipFraction: 0, brightnessSpread: 0, cornerMismatch: 0);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('high bright-clip fraction blocks accept as too bright', () {
      final result = evaluateQuality(
          blurScore: 9000, darkClipFraction: 0, brightClipFraction: 0.96, brightnessSpread: 0, cornerMismatch: 0);

      expect(result.passed, isFalse);
      expect(result.issues, ['Too bright / overexposed — reduce lighting or move away from light source']);
    });

    test('does not flag bright-clip fraction exactly at the threshold', () {
      final result = evaluateQuality(
          blurScore: 9000, darkClipFraction: 0, brightClipFraction: 0.95, brightnessSpread: 0, cornerMismatch: 0);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('does not flag normal white paper bright-clip fraction', () {
      final result = evaluateQuality(
          blurScore: 9000, darkClipFraction: 0, brightClipFraction: 0.91, brightnessSpread: 0, cornerMismatch: 0);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('high brightness spread blocks accept as uneven lighting', () {
      final result = evaluateQuality(
          blurScore: 9000, darkClipFraction: 0, brightClipFraction: 0, brightnessSpread: 36, cornerMismatch: 0);

      expect(result.passed, isFalse);
      expect(result.issues,
          ["Uneven lighting detected — try repositioning so your shadow isn't blocking the page"]);
    });

    test('does not flag brightness spread exactly at the threshold', () {
      final result = evaluateQuality(
          blurScore: 9000, darkClipFraction: 0, brightClipFraction: 0, brightnessSpread: 35, cornerMismatch: 0);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('high corner mismatch blocks accept as crop including background', () {
      final result = evaluateQuality(
          blurScore: 9000, darkClipFraction: 0, brightClipFraction: 0, brightnessSpread: 0, cornerMismatch: 71);

      expect(result.passed, isFalse);
      expect(result.issues, ['Crop may include background — retake and align the corners to the paper edges']);
    });

    test('does not flag corner mismatch exactly at the threshold', () {
      final result = evaluateQuality(
          blurScore: 9000, darkClipFraction: 0, brightClipFraction: 0, brightnessSpread: 0, cornerMismatch: 70);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('combines low blur and too-dark blocks together', () {
      final result = evaluateQuality(
          blurScore: 50, darkClipFraction: 0.5, brightClipFraction: 0, brightnessSpread: 0, cornerMismatch: 0);

      expect(result.passed, isFalse);
      expect(result.issues, [
        'Image quality too low — hold steady, ensure good lighting, and avoid glare',
        'Too dark — move to a brighter area',
      ]);
    });
  });

  group('evaluateLighting', () {
    test('passes with no issues under normal lighting', () {
      final result = evaluateLighting(
          darkClipFraction: 0, brightClipFraction: 0, brightnessSpread: 0);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('flags too dark', () {
      final result = evaluateLighting(
          darkClipFraction: 0.06, brightClipFraction: 0, brightnessSpread: 0);

      expect(result.passed, isFalse);
      expect(result.issues, ['Too dark — move to a brighter area']);
    });

    test('flags too bright', () {
      final result = evaluateLighting(
          darkClipFraction: 0, brightClipFraction: 0.21, brightnessSpread: 0);

      expect(result.passed, isFalse);
      expect(result.issues, ['Too bright / overexposed — reduce lighting or move away from light source']);
    });

    test('flags uneven lighting', () {
      final result = evaluateLighting(
          darkClipFraction: 0, brightClipFraction: 0, brightnessSpread: 36);

      expect(result.passed, isFalse);
      expect(result.issues,
          ["Uneven lighting detected — try repositioning so your shadow isn't blocking the page"]);
    });
  });

  group('checkLightingFrame', () {
    test('passes for a uniform mid-brightness luma frame with no row padding', () {
      final bytes = Uint8List(20 * 20);
      bytes.fillRange(0, bytes.length, 128);
      final frame = LumaFrame(bytes: bytes, width: 20, height: 20, bytesPerRow: 20);

      final result = checkLightingFrame(frame);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('flags too dark when the luma plane is mostly near-black', () {
      final bytes = Uint8List(20 * 20);
      bytes.fillRange(0, bytes.length, 10);
      final frame = LumaFrame(bytes: bytes, width: 20, height: 20, bytesPerRow: 20);

      final result = checkLightingFrame(frame);

      expect(result.passed, isFalse);
      expect(result.issues, contains('Too dark — move to a brighter area'));
    });

    test('ignores row-stride padding bytes beyond the frame width', () {
      // bytesPerRow (24) is wider than the actual frame (20) — common when
      // the camera plugin pads rows to a byte alignment boundary. Real
      // pixel data is mid-range (180, safely between the dark/bright
      // thresholds); padding is 0 (near-black) and must be skipped, or
      // it would wrongly read as a too-dark image.
      const width = 20;
      const height = 20;
      const bytesPerRow = 24;
      final bytes = Uint8List(bytesPerRow * height);
      for (int y = 0; y < height; y++) {
        for (int x = 0; x < bytesPerRow; x++) {
          bytes[y * bytesPerRow + x] = x < width ? 180 : 0;
        }
      }
      final frame = LumaFrame(bytes: bytes, width: width, height: height, bytesPerRow: bytesPerRow);

      final result = checkLightingFrame(frame);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });
  });
}
