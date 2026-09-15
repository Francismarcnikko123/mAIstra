import 'dart:io';
import '../utils/quality_check.dart';

class CapturedPage {
  final File file;
  final QualityResult quality;
  bool accepted;
  final String? originalPath; // full-res photo before warpPerspective crop

  CapturedPage({
    required this.file,
    required this.quality,
    required this.accepted,
    this.originalPath,
  });
}
