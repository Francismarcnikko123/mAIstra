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

  group('evaluateQuality', () {
    test('passes with no issues for a normal, well-formed image', () {
      final result = evaluateQuality(blurScore: 9000, darkClipFraction: 0, brightClipFraction: 0);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('low blur score blocks accept as image quality too low', () {
      final result = evaluateQuality(blurScore: 479, darkClipFraction: 0, brightClipFraction: 0);

      expect(result.passed, isFalse);
      expect(result.issues, ['Image quality too low — hold steady, ensure good lighting, and avoid glare']);
    });

    test('does not flag blur score exactly at the low threshold', () {
      final result = evaluateQuality(blurScore: 480, darkClipFraction: 0, brightClipFraction: 0);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('high dark-clip fraction blocks accept as too dark', () {
      final result = evaluateQuality(blurScore: 9000, darkClipFraction: 0.06, brightClipFraction: 0);

      expect(result.passed, isFalse);
      expect(result.issues, ['Too dark — move to a brighter area']);
    });

    test('does not flag dark-clip fraction exactly at the threshold', () {
      final result = evaluateQuality(blurScore: 9000, darkClipFraction: 0.05, brightClipFraction: 0);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('high bright-clip fraction blocks accept as too bright', () {
      final result = evaluateQuality(blurScore: 9000, darkClipFraction: 0, brightClipFraction: 0.06);

      expect(result.passed, isFalse);
      expect(result.issues, ['Too bright / overexposed — reduce lighting or move away from light source']);
    });

    test('does not flag bright-clip fraction exactly at the threshold', () {
      final result = evaluateQuality(blurScore: 9000, darkClipFraction: 0, brightClipFraction: 0.05);

      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('combines low blur and too-dark blocks together', () {
      final result = evaluateQuality(blurScore: 50, darkClipFraction: 0.5, brightClipFraction: 0);

      expect(result.passed, isFalse);
      expect(result.issues, [
        'Image quality too low — hold steady, ensure good lighting, and avoid glare',
        'Too dark — move to a brighter area',
      ]);
    });
  });
}
