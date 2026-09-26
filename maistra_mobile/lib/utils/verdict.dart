import 'quality_check.dart';

/// The gate verdict as the student sees it and as it is stored in
/// `submissions.gate_result`.
///
/// A page the gate flagged FIXABLE and then corrected comes back from
/// `checkAndFixQuality` as PASS with `autoFixed`; it still counts as FIXABLE
/// here so a low grade can be traced to a corrected photo.
enum Verdict { pass, fixable, retake }

Verdict verdictOf(QualityResult r) {
  if (r.decision == QualityDecision.retake) return Verdict.retake;
  if (r.decision == QualityDecision.fixable || r.autoFixed) {
    return Verdict.fixable;
  }
  return Verdict.pass;
}

/// Value written to `submissions.gate_result`.
String gateResultValue(Verdict v) => v.name.toUpperCase();

class VerdictCopy {
  final String heading;
  final String sentence;

  /// Further gate issues after the first, already phrased as sentences.
  final List<String> more;

  const VerdictCopy(this.heading, this.sentence, [this.more = const []]);
}

/// Heading plus one plain sentence for a gate result, built from the gate's
/// own issue strings ("Too blurry — hold the camera steady" becomes
/// "Too blurry" / "Hold the camera steady.").
VerdictCopy verdictCopy(QualityResult r) {
  final verdict = verdictOf(r);

  if (verdict == Verdict.pass) {
    return const VerdictCopy('Photo is good', 'Nothing needs changing.');
  }

  // Lead with a RETAKE issue when there is one; the gate lists issues in
  // check order, not by severity.
  final issues = List<String>.of(r.issues);
  if (verdict == Verdict.retake) {
    final lead = issues.indexWhere(_isRetakeIssue);
    if (lead > 0) issues.insert(0, issues.removeAt(lead));
  }

  if (issues.isEmpty) {
    // Corrected pages lose their original issues when re-checked.
    return verdict == Verdict.fixable
        ? const VerdictCopy(
            'Auto-corrected',
            'Lighting or tilt was adjusted automatically. Nothing else needs changing.',
          )
        : const VerdictCopy('Retake this page', 'Take this page again.');
  }

  final (head, tail) = _split(issues.first);
  final more = issues.skip(1).map((i) {
    final (h, t) = _split(i);
    return t.isEmpty ? '$h.' : '$h: ${_lowerFirst(t)}';
  }).toList();
  if (tail.isEmpty) {
    final fallback = verdict == Verdict.retake
        ? 'Retake this page'
        : 'Auto-corrected';
    return VerdictCopy(fallback, '$head.', more);
  }
  return VerdictCopy(head, tail, more);
}

// FIXABLE issue strings all say the problem "will be auto-..." corrected.
bool _isRetakeIssue(String issue) => !issue.contains('will be auto');

(String, String) _split(String issue) {
  const sep = ' — ';
  final at = issue.indexOf(sep);
  if (at < 0) return (issue, '');
  final head = issue.substring(0, at).trim();
  var tail = issue.substring(at + sep.length).trim();
  if (tail.isNotEmpty) {
    tail = tail[0].toUpperCase() + tail.substring(1);
    if (!tail.endsWith('.')) tail = '$tail.';
  }
  return (head, tail);
}

String _lowerFirst(String s) =>
    s.isEmpty ? s : s[0].toLowerCase() + s.substring(1);
