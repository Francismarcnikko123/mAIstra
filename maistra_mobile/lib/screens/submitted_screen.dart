import 'package:flutter/material.dart';
import '../models/question_choice.dart';
import '../theme/app_theme.dart';
import 'question_picker_screen.dart';

/// Screen 4: confirmation. "Capture another answer" returns to the picker,
/// which is how a student submits their second and third answers.
class SubmittedScreen extends StatelessWidget {
  final QuestionChoice question;
  final int pageCount;
  final DateTime submittedAt;

  const SubmittedScreen({
    super.key,
    required this.question,
    required this.pageCount,
    required this.submittedAt,
  });

  // Starts a fresh picker so the last choice is not remembered.
  void _captureAnother(BuildContext context) {
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const QuestionPickerScreen()),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final loc = MaterialLocalizations.of(context);
    final when =
        '${loc.formatMediumDate(submittedAt)} · ${loc.formatTimeOfDay(TimeOfDay.fromDateTime(submittedAt))}';
    final pages = '$pageCount ${pageCount == 1 ? 'page' : 'pages'}';

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _captureAnother(context);
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Submitted'),
          automaticallyImplyLeading: false,
        ),
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Spacer(),
                Icon(
                  Icons.check_circle_outline,
                  size: 64,
                  color: VerdictColors.of(context).pass,
                ),
                const SizedBox(height: 24),
                Text(
                  'Answer submitted',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  question.fullLabel,
                  textAlign: TextAlign.center,
                  style: theme.textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  '$pages · $when',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodyLarge?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 24),
                Text(
                  'Your teacher reviews the extracted code before it is graded.',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodyMedium,
                ),
                const Spacer(),
                FilledButton.icon(
                  onPressed: () => _captureAnother(context),
                  icon: const Icon(Icons.add),
                  label: const Text('Capture another answer'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
