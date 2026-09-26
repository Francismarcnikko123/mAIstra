import 'dart:async';

import 'package:flutter/services.dart';

class EdgeDetection {
  static const MethodChannel _channel = const MethodChannel('edge_detection');

  /// Call this method to scan the object edge in live camera.
  static Future<bool> detectEdge(String saveTo,
      {
        bool canUseGallery = true,
        String androidScanTitle = "Scanning",
        String androidCropTitle = "Crop",
        String androidCropBlackWhiteTitle = "Black White",
        String androidCropReset = "Reset",
      }) async {
    return await _channel.invokeMethod('edge_detect', {
      'save_to': saveTo,
      'can_use_gallery': canUseGallery,
      'scan_title': androidScanTitle,
      'crop_title': androidCropTitle,
      'crop_black_white_title': androidCropBlackWhiteTitle,
      'crop_reset_title': androidCropReset,
    });
  }

  /// Headless batch processing: auto-detects and crops each image silently.
  /// [inputPaths] are source images; [outputPaths] are where results are saved.
  /// Returns a list of booleans — true if processing succeeded for that image.
  static Future<List<bool>> batchProcessImages({
    required List<String> inputPaths,
    required List<String> outputPaths,
  }) async {
    final result = await _channel.invokeMethod('batch_process_images', {
      'input_paths': inputPaths,
      'output_paths': outputPaths,
    });
    return List<bool>.from(result as List);
  }

  /// Opens the Adjust Crop screen for an existing image at [inputPath].
  /// Saves the result to [saveTo]. Returns true if the user confirmed the crop.
  static Future<bool> recropImage({
    required String inputPath,
    required String saveTo,
  }) async {
    return await _channel.invokeMethod('recrop_image', {
      'input_path': inputPath,
      'save_to': saveTo,
    });
  }

  /// Call this method to scan the object edge from a gallery image.
  static Future<bool> detectEdgeFromGallery(String saveTo,
      {
        String androidCropTitle = "Crop",
        String androidCropBlackWhiteTitle = "Black White",
        String androidCropReset = "Reset",
      }) async {
    return await _channel.invokeMethod('edge_detect_gallery', {
      'save_to': saveTo,
      'crop_title': androidCropTitle,
      'crop_black_white_title': androidCropBlackWhiteTitle,
      'crop_reset_title': androidCropReset,
      'from_gallery': true,
    });
  }
}
