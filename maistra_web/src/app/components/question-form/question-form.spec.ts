import '@angular/compiler';
import { ChangeDetectorRef } from '@angular/core';
import { readFileSync } from 'fs';
import { describe, expect, it, vi } from 'vitest';
import { SupabaseService } from '../../services/supabase';
import { Judge0Service } from '../../services/judge0.service';
import { QuestionFormComponent } from './question-form';

describe('QuestionFormComponent', () => {
  function createComponent(
    saveQuestion = vi.fn().mockResolvedValue({ data: {}, error: null }),
  ) {
    const supabase = { saveQuestion } as unknown as SupabaseService;
    const cdr = { detectChanges: vi.fn() } as unknown as ChangeDetectorRef;
    const judge0 = {} as Judge0Service;

    return new QuestionFormComponent(supabase, cdr, judge0);
  }

  it('resets test cases after a successful save', async () => {
    const component = createComponent();
    component.questionName = 'Addition';
    component.questionText = 'Write a C program that adds two numbers.';
    component.questionType = 'program';
    component.modelAnswer = 'int main(void) { return 0; }';
    component.testCases = [
      {
        test_code: '1 1',
        test_input: '1 1',
        expected_output: '2',
        mark: 2,
      },
      {
        test_code: '2 3',
        test_input: '2 3',
        expected_output: '5',
        mark: 3,
      },
    ];
    component.validationResults = [
      {
        passed: true,
        expected: '2',
        actual: '2',
      },
    ];
    component.testRunStatuses = ['passed', 'failed'];
    component.canPublish = true;
    component.collapsedTestCases = { 1: true };

    await component.save();

    expect(component.testCases).toEqual([
      {
        test_code: '',
        test_input: '',
        expected_output: '',
        mark: 2,
      },
    ]);
    expect(component.validationResults).toEqual([]);
    expect(component.testRunStatuses).toEqual([]);
    expect(component.canPublish).toBe(false);
    expect(component.collapsedTestCases).toEqual({});
  });

  it('renders save validation and success messages', async () => {
    const template = readFileSync(
      'src/app/components/question-form/question-form.html',
      'utf8',
    );

    expect(template).toContain('class="error-message"');
    expect(template).toContain('{{ errorMessage }}');
    expect(template).toContain('class="success-message"');
    expect(template).toContain('{{ successMessage }}');
  });
});
