import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../utils/quality_check.dart';
import '../utils/verdict.dart';

IconData verdictIcon(Verdict v) => switch (v) {
  Verdict.pass => Icons.check_circle_outline,
  Verdict.fixable => Icons.auto_fix_high_outlined,
  Verdict.retake => Icons.error_outline,
};

String verdictLabel(Verdict v) => switch (v) {
  Verdict.pass => 'Good',
  Verdict.fixable => 'Corrected',
  Verdict.retake => 'Retake',
};

(Color, Color) verdictColors(BuildContext context, Verdict v) {
  final c = VerdictColors.of(context);
  return switch (v) {
    Verdict.pass => (c.pass, c.passContainer),
    Verdict.fixable => (c.fixable, c.fixableContainer),
    Verdict.retake => (c.retake, c.retakeContainer),
  };
}

/// Icon + heading + one plain sentence for a gate result.
class VerdictBanner extends StatelessWidget {
  final QualityResult result;
  final bool dense;

  const VerdictBanner({super.key, required this.result, this.dense = false});

  @override
  Widget build(BuildContext context) {
    final verdict = verdictOf(result);
    final copy = verdictCopy(result);
    final (fg, bg) = verdictColors(context, verdict);
    final text = Theme.of(context).textTheme;

    return Semantics(
      container: true,
      label: '${copy.heading}. ${copy.sentence}',
      excludeSemantics: true,
      child: Container(
        width: double.infinity,
        padding: EdgeInsets.all(dense ? 8 : 16),
        decoration: BoxDecoration(
          color: bg,
          border: Border.all(color: fg),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(verdictIcon(verdict), color: fg, size: dense ? 20 : 24),
            SizedBox(width: dense ? 8 : 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    copy.heading,
                    style: (dense ? text.titleSmall : text.titleMedium)
                        ?.copyWith(color: fg, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 4),
                  Text(copy.sentence, style: text.bodyMedium),
                  for (final m in copy.more)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(m, style: text.bodySmall),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Small icon + label pill, e.g. "2 Good".
class VerdictChip extends StatelessWidget {
  final Verdict verdict;
  final int? count;

  const VerdictChip({super.key, required this.verdict, this.count});

  @override
  Widget build(BuildContext context) {
    final (fg, bg) = verdictColors(context, verdict);
    final label = count == null
        ? verdictLabel(verdict)
        : '$count ${verdictLabel(verdict)}';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: fg),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(verdictIcon(verdict), size: 16, color: fg),
          const SizedBox(width: 4),
          Text(
            label,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: fg,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}
