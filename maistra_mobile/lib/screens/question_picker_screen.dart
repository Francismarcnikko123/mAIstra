import 'package:flutter/material.dart';
import '../models/question_choice.dart';
import '../services/question_repository.dart';
import 'capture_screen.dart';

/// Screen 1: the student picks which question this answer is for, before
/// the camera opens. One question per capture session.
class QuestionPickerScreen extends StatefulWidget {
  final QuestionRepository? repository;

  const QuestionPickerScreen({super.key, this.repository});

  @override
  State<QuestionPickerScreen> createState() => _QuestionPickerScreenState();
}

class _QuestionPickerScreenState extends State<QuestionPickerScreen> {
  late final QuestionRepository _repo =
      widget.repository ?? QuestionRepository();

  List<QuestionSection>? _sections;
  Object? _error;
  String? _selectedId;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _sections = null;
      _error = null;
    });
    try {
      final choices = await _repo.fetchReadyQuestions();
      if (!mounted) return;
      setState(() => _sections = groupBySection(choices));
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e);
    }
  }

  QuestionChoice? get _selected {
    for (final s in _sections ?? const <QuestionSection>[]) {
      for (final q in s.questions) {
        if (q.id == _selectedId) return q;
      }
    }
    return null;
  }

  Future<void> _start() async {
    final question = _selected;
    if (question == null) return;
    await Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => CaptureScreen(question: question)),
    );
    // The last choice is deliberately not remembered.
    if (!mounted) return;
    setState(() => _selectedId = null);
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final sections = _sections;
    final isEmpty = sections != null && sections.isEmpty;

    return Scaffold(
      appBar: AppBar(title: const Text('Choose a question')),
      body: _error != null
          ? _ErrorState(onRetry: _load)
          : sections == null
          ? const Center(child: CircularProgressIndicator())
          : isEmpty
          ? const _EmptyState()
          : RefreshIndicator(onRefresh: _load, child: _buildList(sections)),
      bottomNavigationBar: SafeArea(
        minimum: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (isEmpty) ...[
              Text(
                'Ask your teacher to validate a question in the web dashboard.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 16),
            ],
            FilledButton.icon(
              onPressed: _selected == null ? null : _start,
              icon: const Icon(Icons.document_scanner_outlined),
              label: const Text('Start capturing'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildList(List<QuestionSection> sections) {
    final theme = Theme.of(context);
    return RadioGroup<String>(
      groupValue: _selectedId,
      onChanged: (id) => setState(() => _selectedId = id),
      child: ListView(
        padding: const EdgeInsets.symmetric(vertical: 8),
        children: [
          for (final section in sections) ...[
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Text(
                section.name,
                style: theme.textTheme.titleSmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            for (final q in section.questions)
              RadioListTile<String>(
                key: ValueKey(q.id),
                value: q.id,
                title: Text(q.name),
                secondary: Text(
                  'Q${q.number}',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            const Divider(),
          ],
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.assignment_outlined,
              size: 48,
              color: theme.colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 16),
            Text(
              'No questions ready',
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'A question must be created and its model answer validated '
              'before papers can be captured for it.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final VoidCallback onRetry;

  const _ErrorState({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.cloud_off_outlined,
              size: 48,
              color: theme.colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 16),
            Text(
              'Could not load questions',
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Check your internet connection and try again.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}
