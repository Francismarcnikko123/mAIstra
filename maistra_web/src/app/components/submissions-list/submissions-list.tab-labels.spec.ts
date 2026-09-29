import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { readFileSync } from 'fs';
import { describe, expect, it, vi } from 'vitest';
import { Judge0Service } from '../../services/judge0.service';
import { SupabaseService } from '../../services/supabase';
import { SubmissionsListComponent } from './submissions-list';
import { indexQuestionPlaces } from '../question-bank/question-labels';

// Step 2 tabs say only "Program N" so three to five fit without scrolling;
// the question is on hover and on the Question row, always as
// "Section · Q# · Name". The rest of the tabs is in the program-tabs spec.

function createComponent() {
  const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
  const component = new SubmissionsListComponent(
    { answersColumnAvailable: true } as unknown as SupabaseService,
    {} as HttpClient,
    cdr,
    {} as Judge0Service,
  );
  component.questions = [
    { id: 'q-sum', question_name: 'Sum of two numbers', question_type: 'program', model_answer: 'm', test_cases: [] },
    { id: 'q-saved', question_name: 'Saved by B', question_type: 'program', model_answer: 'm', test_cases: [] },
    { id: 'q-old', question_name: 'Old question', question_type: 'program', model_answer: 'm', test_cases: [] },
  ];
  component.questionPlaces = indexQuestionPlaces(
    [
      { id: 'basic', name: 'Basic', position: 0 },
      { id: 'e2e', name: 'E2E TEST', position: 1 },
    ],
    [
      { section_id: 'basic', question_id: 'q-sum', number: 2 },
      { section_id: 'e2e', question_id: 'q-saved', number: 1 },
    ],
  );
  component.selectedSubmission = { id: 'paper-1', image_url: 'x', captured_at: 'y' };
  component.selectedQuestionId = 'q-sum';
  return component;
}

function readTemplate() {
  const template = readFileSync('src/app/components/submissions-list/submissions-list.html', 'utf8');
  return new DOMParser().parseFromString(template, 'text/html');
}

describe('SubmissionsListComponent tab labels', () => {
  it('names each tab only "Program N" and keeps its keys, markers and × button', () => {
    const tabs = [...readTemplate().querySelectorAll('.program-tabs [role="tab"]')];

    expect(tabs.map((tab) => tab.querySelector('.program-tab-label')?.textContent?.trim())).toEqual([
      'Program 1',
      'Program {{ i + 2 }}',
    ]);
    for (const tab of tabs) {
      // The question is on the Question row under the tabs, not in the tab.
      expect(tab.textContent).not.toMatch(/question/i);
      // Nothing overrides the "Program N" text as the tab's accessible name.
      expect(tab.hasAttribute('aria-label')).toBe(false);
      expect(tab.hasAttribute('[attr.aria-label]')).toBe(false);
      expect(tab.getAttribute('(keydown.arrowright)')).toBe('moveTab(1, $event)');
      expect(tab.getAttribute('(keydown.arrowleft)')).toBe('moveTab(-1, $event)');
      expect(tab.querySelector('.program-tab-dot')).not.toBeNull();
    }

    const extra = tabs[1];
    expect(extra.getAttribute('tabindex')).toBe('0');
    expect(extra.getAttribute('(keydown.enter)')).toBe('selectTab(i + 1)');
    expect(extra.querySelector('.program-tab-warn')?.textContent?.trim()).toBe('!');
    expect(extra.querySelector('.program-tab-close')).not.toBeNull();
  });

  it('shows each tab\'s full question label on hover', () => {
    const tabs = [...readTemplate().querySelectorAll('.program-tabs [role="tab"]')];
    expect(tabs.map((tab) => tab.getAttribute('[title]'))).toEqual([
      'programTabTitle(0)',
      'programTabTitle(i + 1)',
    ]);

    const component = createComponent();
    component.addExtraAnswer();
    component.chooseExtraQuestion(0, 'q-saved');
    component.addExtraAnswer();
    component.addExtraAnswer();
    component.chooseExtraQuestion(2, 'q-old');

    expect(component.programTabTitle(0)).toBe('Program 1 · Basic · Q2 · Sum of two numbers');
    expect(component.programTabTitle(1)).toBe('Program 2 · E2E TEST · Q1 · Saved by B');
    expect(component.programTabTitle(2)).toBe('Program 3 · No question yet');
    // A question with no section yet keeps its plain name.
    expect(component.programTabTitle(3)).toBe('Program 4 · Old question');
  });

  it('labels the question the same way in the picker, the Program 1 line and the header', () => {
    const component = createComponent();

    expect(component.tabQuestionLabel('q-saved')).toBe('E2E TEST · Q1 · Saved by B');
    expect(component.tabQuestionLabel('q-old')).toBe('Old question');
    expect(component.tabQuestionLabel('q-deleted')).toBe('Unknown question');
    expect(component.getQuestionLabel(component.selectedSubmission!)).toBe(
      'Basic · Q2 · Sum of two numbers',
    );
    // The name-only helper is gone.
    expect('getQuestionTitle' in component).toBe(false);

    const page = readTemplate();
    expect(page.querySelector('.question-picker-value')?.textContent?.trim()).toBe(
      "{{ answer.question_id ? tabQuestionLabel(answer.question_id) : 'Choose a question…' }}",
    );
    expect(page.querySelector('.question-locked')?.textContent?.trim()).toBe(
      '{{ getQuestionLabel(selectedSubmission) }} · set in Details',
    );
    const meta = page.querySelector('.review-meta')?.textContent ?? '';
    expect(meta).toContain('{{ getQuestionLabel(selectedSubmission) }}');
    expect(meta).not.toContain('getQuestionName');
  });
});
