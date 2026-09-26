import 'package:flutter/material.dart';

const kBrandRed = Color(0xFFB71C1C);

/// Semantic colours for the quality-gate verdicts. Always shown with an icon
/// and text, never as colour alone.
class VerdictColors extends ThemeExtension<VerdictColors> {
  final Color pass;
  final Color passContainer;
  final Color fixable;
  final Color fixableContainer;
  final Color retake;
  final Color retakeContainer;

  const VerdictColors({
    required this.pass,
    required this.passContainer,
    required this.fixable,
    required this.fixableContainer,
    required this.retake,
    required this.retakeContainer,
  });

  static const light = VerdictColors(
    pass: Color(0xFF15803D),
    passContainer: Color(0xFFF0FDF4),
    fixable: Color(0xFFB45309),
    fixableContainer: Color(0xFFFFFBEB),
    retake: Color(0xFFB91C1C),
    retakeContainer: Color(0xFFFEF2F2),
  );

  static const dark = VerdictColors(
    pass: Color(0xFF4ADE80),
    passContainer: Color(0xFF052E16),
    fixable: Color(0xFFFBBF24),
    fixableContainer: Color(0xFF3B2305),
    retake: Color(0xFFF87171),
    retakeContainer: Color(0xFF3F0D0D),
  );

  static VerdictColors of(BuildContext context) =>
      Theme.of(context).extension<VerdictColors>()!;

  @override
  VerdictColors copyWith({
    Color? pass,
    Color? passContainer,
    Color? fixable,
    Color? fixableContainer,
    Color? retake,
    Color? retakeContainer,
  }) {
    return VerdictColors(
      pass: pass ?? this.pass,
      passContainer: passContainer ?? this.passContainer,
      fixable: fixable ?? this.fixable,
      fixableContainer: fixableContainer ?? this.fixableContainer,
      retake: retake ?? this.retake,
      retakeContainer: retakeContainer ?? this.retakeContainer,
    );
  }

  @override
  VerdictColors lerp(VerdictColors? other, double t) {
    if (other == null) return this;
    return VerdictColors(
      pass: Color.lerp(pass, other.pass, t)!,
      passContainer: Color.lerp(passContainer, other.passContainer, t)!,
      fixable: Color.lerp(fixable, other.fixable, t)!,
      fixableContainer: Color.lerp(
        fixableContainer,
        other.fixableContainer,
        t,
      )!,
      retake: Color.lerp(retake, other.retake, t)!,
      retakeContainer: Color.lerp(retakeContainer, other.retakeContainer, t)!,
    );
  }
}

/// Flat, high-contrast Material 3 theme: brand red for primary actions,
/// slate surfaces, no decorative shadows.
ThemeData buildAppTheme(Brightness brightness) {
  final isDark = brightness == Brightness.dark;
  final scheme = ColorScheme.fromSeed(
    seedColor: kBrandRed,
    brightness: brightness,
    primary: isDark ? null : kBrandRed,
    surface: isDark ? const Color(0xFF0F172A) : Colors.white,
    onSurface: isDark ? const Color(0xFFF1F5F9) : const Color(0xFF0F172A),
    onSurfaceVariant: isDark
        ? const Color(0xFF94A3B8)
        : const Color(0xFF475569),
    outlineVariant: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0),
    tertiary: isDark ? const Color(0xFF60A5FA) : const Color(0xFF2563EB),
  );

  final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(8));
  const buttonPadding = EdgeInsets.symmetric(horizontal: 16, vertical: 16);

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: scheme.surface,
    appBarTheme: AppBarTheme(
      backgroundColor: isDark ? scheme.surface : kBrandRed,
      foregroundColor: isDark ? scheme.onSurface : Colors.white,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardThemeData(
      elevation: 0,
      margin: EdgeInsets.zero,
      color: scheme.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: BorderSide(color: scheme.outlineVariant),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        padding: buttonPadding,
        shape: shape,
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        padding: buttonPadding,
        shape: shape,
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
      ),
    ),
    dividerTheme: DividerThemeData(color: scheme.outlineVariant, space: 1),
    extensions: [isDark ? VerdictColors.dark : VerdictColors.light],
  );
}
