import 'dart:math';

/// A random version-4 UUID (`xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`) for
/// `submissions.batch_id`: every page of one answer gets the same id, so the
/// web can treat them as one paper. Uses the platform's secure random source,
/// so no extra package is needed.
String newBatchId([Random? random]) {
  final rng = random ?? Random.secure();
  final bytes = List<int>.generate(16, (_) => rng.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // RFC 4122 variant
  final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
      '${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}
