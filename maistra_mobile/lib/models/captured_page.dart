import 'dart:io';
import '../utils/quality_check.dart';
import '../utils/verdict.dart';

class CapturedPage {
  final File file;
  final QualityResult quality;
  final String? originalPath; // full-res photo before warpPerspective crop

  CapturedPage({required this.file, required this.quality, this.originalPath});

  Verdict get verdict => verdictOf(quality);
}
