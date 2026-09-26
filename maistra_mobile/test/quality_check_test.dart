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
          final value = y < 3 ? 0 : 200;
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
          final value = y < 2 ? 255 : 100;
          image.setPixelRgb(x, y, value, value, value);
        }
      }

      expect(computeBrightClipFraction(image), closeTo(0.2, 0.001));
    });
  });

  group('computeShadowScore', () {
    test('returns 0 for a uniformly bright image', () {
      final image = _whiteImage(30, 30);

      expect(computeShadowScore(image, rows: 3, cols: 3), 0);
    });

    test('returns a large spread when one region is much darker than the rest', () {
      final image = img.Image(width: 30, height: 30);
      for (int y = 0; y < 30; y++) {
        for (int x = 0; x < 30; x++) {
          final inShadow = x < 10 && y >= 20;
          final value = inShadow ? 60 : 200;
          image.setPixelRgb(x, y, value, value, value);
        }
      }

      expect(computeShadowScore(image, rows: 3, cols: 3), closeTo(140, 0.001));
    });
  });

  // Helper to build a QualityMetrics and call evaluateMetrics in one line.
  QualityResult eval({
    double blur = 9000,
    double dark = 0,
    double bright = 0,
    double contrast = 50,
    double shadow = 0,
    double skew = 0,
  }) =>
      evaluateMetrics(QualityMetrics(
        blurScore: blur,
        darkClipFraction: dark,
        brightClipFraction: bright,
        contrastScore: contrast,
        shadowScore: shadow,
        skewAngleDeg: skew,
      ));

  group('evaluateMetrics — blur', () {
    test('passes with no issues for a well-formed image', () {
      final result = eval();
      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });

    test('blur below threshold results in retake', () {
      // kBlurRetake = 200 — strict less-than triggers retake
      final result = eval(blur: 199);
      expect(result.passed, isFalse);
      expect(result.issues, contains('Too blurry — hold the camera steady'));
    });

    test('blur exactly at threshold does not retake', () {
      final result = eval(blur: 200);
      expect(result.passed, isTrue);
    });
  });

  group('evaluateMetrics — dark clip', () {
    test('dark fraction above retake threshold results in retake', () {
      // kDarkRetake = 0.15
      final result = eval(dark: 0.16);
      expect(result.passed, isFalse);
      expect(result.issues, contains('Too dark — move to a brighter area'));
    });

    test('dark fraction exactly at retake threshold does not retake', () {
      // 0.15 is not > 0.15 so no retake; it is > 0.08 (kDarkFixable) so fixable,
      // but fixable.passed == true
      final result = eval(dark: 0.15);
      expect(result.passed, isTrue);
    });

    test('dark fraction below fixable threshold produces no issues', () {
      // kDarkFixable = 0.08 — below both thresholds
      final result = eval(dark: 0.07);
      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });
  });

  group('evaluateMetrics — bright clip', () {
    test('bright fraction above retake threshold results in retake', () {
      // kBrightRetake = 0.20
      final result = eval(bright: 0.21);
      expect(result.passed, isFalse);
      expect(result.issues, contains('Severely overexposed — reduce glare or move away from light'));
    });

    test('bright fraction exactly at retake threshold does not retake', () {
      final result = eval(bright: 0.20);
      expect(result.passed, isTrue);
    });

    test('bright fraction below fixable threshold produces no issues', () {
      // kBrightFixable = 0.10
      final result = eval(bright: 0.09);
      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });
  });

  group('evaluateMetrics — shadow', () {
    test('shadow above retake threshold results in retake', () {
      // kShadowRetake = 25
      final result = eval(shadow: 26);
      expect(result.passed, isFalse);
      expect(result.issues, contains('Extreme shadow across page — reposition or use even lighting'));
    });

    test('shadow exactly at retake threshold does not retake', () {
      final result = eval(shadow: 25);
      expect(result.passed, isTrue);
    });

    test('shadow below retake threshold produces no issues', () {
      // kShadowFixable = 999 (disabled), so anything under kShadowRetake is clean
      final result = eval(shadow: 20);
      expect(result.passed, isTrue);
      expect(result.issues, isEmpty);
    });
  });

  group('evaluateMetrics — multiple issues', () {
    test('combines blur and dark-clip retake issues', () {
      final result = eval(blur: 50, dark: 0.5);
      expect(result.passed, isFalse);
      expect(result.issues, containsAll([
        'Too blurry — hold the camera steady',
        'Too dark — move to a brighter area',
      ]));
    });
  });

  group('evaluateMetrics — lighting only (blur/contrast/skew inert)', () {
    QualityResult lighting({double dark = 0, double bright = 0, double shadow = 0}) =>
        evaluateMetrics(QualityMetrics(
          blurScore: double.infinity,
          darkClipFraction: dark,
          brightClipFraction: bright,
          contrastScore: double.infinity,
          shadowScore: shadow,
          skewAngleDeg: 0,
        ));

    test('passes with no issues under normal lighting', () {
      expect(lighting().passed, isTrue);
      expect(lighting().issues, isEmpty);
    });

    test('flags too dark', () {
      final result = lighting(dark: 0.16);
      expect(result.passed, isFalse);
      expect(result.issues, contains('Too dark — move to a brighter area'));
    });

    test('flags too bright', () {
      final result = lighting(bright: 0.21);
      expect(result.passed, isFalse);
      expect(result.issues, contains('Severely overexposed — reduce glare or move away from light'));
    });

    test('flags uneven lighting / shadow', () {
      final result = lighting(shadow: 101);
      expect(result.passed, isFalse);
      expect(result.issues, contains('Extreme shadow across page — reposition or use even lighting'));
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
