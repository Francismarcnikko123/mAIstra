import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { describe, expect, it, vi } from 'vitest';
import { Judge0Service } from '../../services/judge0.service';
import { SupabaseService } from '../../services/supabase';
import { SubmissionsListComponent } from './submissions-list';

// Folders from question sections (Nikko). Review, grading and program tabs
// are covered by the other submissions-list specs.

const sections = [
  { id: 'loops', name: 'Loops', position: 1 },
  { id: 'basic', name: 'Basic', position: 0 },
];
const items = [
  { section_id: 'basic', question_id: 'q-sum', number: 2 },
  { section_id: 'loops', question_id: 'q-vowels', number: 1 },
];
const submissions = [
  { id: 's1', image_url: 'u', captured_at: '2026-09-24T01:12:00Z', question_id: 'q-vowels' },
  { id: 's2', image_url: 'u', captured_at: '2026-09-24T01:13:00Z', question_id: 'q-sum' },
  { id: 's3', image_url: 'u', captured_at: '2026-09-24T01:14:00Z', topic: 'Chapter 3' },
  { id: 's4', image_url: 'u', captured_at: '2026-09-24T01:15:00Z' },
];

function createComponent(overrides: Record<string, unknown> = {}) {
  const supabase = {
    // A fresh copy per test: saving details mutates the rows.
    getSubmissions: vi.fn().mockResolvedValue({ data: structuredClone(submissions), error: null }),
    getQuestionSections: vi.fn().mockResolvedValue({ data: sections, error: null }),
    getSectionItems: vi.fn().mockResolvedValue({ data: items, error: null }),
    getGateResults: vi.fn().mockResolvedValue(new Map([['s2', 'FIXABLE']])),
    getSubmission: vi.fn().mockResolvedValue({ data: null, error: null }),
    // Returns the new grading_revision (Jayrald's compare-and-set save).
    updateSubmissionDetails: vi.fn().mockResolvedValue(1),
    ...overrides,
  };
  const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
  const component = new SubmissionsListComponent(
    supabase as unknown as SupabaseService,
    {} as HttpClient,
    cdr,
    {} as Judge0Service,
  );
  component.questions = [
    { id: 'q-sum', question_name: 'Sum of two numbers', question_type: 'program', model_answer: '', test_cases: [] },
    { id: 'q-vowels', question_name: 'Count vowels', question_type: 'program', model_answer: '', test_cases: [] },
  ];
  return { component, supabase };
}

describe('SubmissionsListComponent section folders', () => {
  it("files papers under their question's section, then typed topics, then Uncategorized", async () => {
    const { component } = createComponent();
    await component.loadSubmissions();

    expect(component.groupedSubmissions.map((g) => g.topic)).toEqual([
      'Basic',
      'Loops',
      'Chapter 3',
      'Uncategorized',
    ]);
    expect(component.groupedSubmissions[0].submissions.map((s) => s.id)).toEqual(['s2']);
  });

  it('labels cards with section, number and name, and keeps the photo verdict', async () => {
    const { component } = createComponent();
    await component.loadSubmissions();
    const sum = component.submissions.find((s) => s.id === 's2')!;

    expect(component.getQuestionLabel(sum)).toBe('Basic · Q2 · Sum of two numbers');
    expect(component.gateBadge(component.gateResults.get('s2'))?.label).toBe(
      'Photo auto-corrected',
    );
  });

  it('shows the section read-only in Details and saves it as the folder', async () => {
    const { component, supabase } = createComponent();
    await component.loadSubmissions();
    component.openModal(component.submissions.find((s) => s.id === 's4')!);

    expect(component.selectedSectionName()).toBe('Choose a question first');
    component.selectedQuestionId = 'q-vowels';
    expect(component.selectedSectionName()).toBe('Loops');

    await component.continueFromDetails();
    expect(supabase.updateSubmissionDetails).toHaveBeenCalledWith('s4', 'Loops', 'q-vowels', 0);
    expect(component.groupedSubmissions.find((g) => g.topic === 'Loops')?.submissions).toHaveLength(2);
  });

  it('keeps the typed topic when the question has no section yet', async () => {
    const { component, supabase } = createComponent();
    await component.loadSubmissions();
    component.openModal(component.submissions.find((s) => s.id === 's3')!);
    component.selectedQuestionId = 'q-unsectioned';

    expect(component.selectedSectionName()).toBe('No section yet');
    await component.continueFromDetails();
    expect(supabase.updateSubmissionDetails).toHaveBeenCalledWith('s3', 'Chapter 3', 'q-unsectioned', 0);
  });

  it('still lists every paper when sections cannot be loaded', async () => {
    const { component } = createComponent({
      getQuestionSections: vi.fn().mockRejectedValue(new Error('offline')),
    });
    vi.spyOn(console, 'error').mockImplementation(() => {});
    await component.loadSubmissions();

    expect(component.submissions).toHaveLength(4);
    expect(component.groupedSubmissions.map((g) => g.topic)).toEqual(['Chapter 3', 'Uncategorized']);
  });

  it("says when a save hit someone else's change or newer typing", async () => {
    const { component } = createComponent();
    await component.loadSubmissions();
    component.openModal(component.submissions.find((s) => s.id === 's2')!);

    component.saveStatus['s2'] = 'conflict';
    expect(component.saveStatusLabel('s2')).toBe(
      'Changed by someone else. Save again to keep yours',
    );

    component.saveStatus['s2'] = 'saved';
    component.updateSubmissionCode('s2', 'typed after saving');
    expect(component.saveStatusLabel('s2')).toBe('New changes need to be saved');
  });
});
