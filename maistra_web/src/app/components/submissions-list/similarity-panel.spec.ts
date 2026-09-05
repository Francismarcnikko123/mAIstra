import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';
import { SimilarityPanelComponent } from './similarity-panel';

describe('Similarity panel', () => {
  async function render(inputs: Record<string, unknown> = {}) {
    await TestBed.configureTestingModule({
      imports: [SimilarityPanelComponent],
    }).compileComponents();
    const fixture = TestBed.createComponent(SimilarityPanelComponent);
    for (const [key, value] of Object.entries(inputs))
      fixture.componentRef.setInput(key, value);
    fixture.detectChanges();
    return {
      fixture,
      panel: fixture.componentInstance,
      element: fixture.nativeElement as HTMLElement,
    };
  }

  it.each([
    ['missing_metadata', 'Complete and save'],
    ['not_checked', 'No check yet'],
    ['checking', 'Checking saved answers'],
    ['outdated', 'changed'],
    ['unavailable', 'unavailable'],
  ])('explains the %s state', async (state, message) => {
    const { element } = await render({ state });
    expect(element.textContent).toContain(message);
    expect(element.textContent).toContain('does not change the grade');
  });

  it('offers Retry on failure and only disables its own action while checking', async () => {
    const { fixture, element, panel } = await render({ state: 'unavailable' });
    const retry = vi.fn();
    panel.retry.subscribe(retry);
    const button = element.querySelector('button')!;
    expect(button.textContent).toContain('Retry');
    button.click();
    expect(retry).toHaveBeenCalledOnce();
    fixture.componentRef.setInput('state', 'checking');
    fixture.detectChanges();
    expect(element.querySelector('button')!.disabled).toBe(true);
  });

  it('distinguishes an empty cohort from completed comparisons and parsing limits', async () => {
    const { fixture, element } = await render({
      state: 'complete',
      summary: { eligible_submission_count: 1, matches: [] },
    });
    expect(element.textContent).toContain('No other eligible');
    fixture.componentRef.setInput('summary', {
      eligible_submission_count: 3,
      compared_pair_count: 2,
      skipped_pair_count: 1,
      skipped_reasons: { partial_analysis: 1 },
      matches: [],
    });
    fixture.detectChanges();
    expect(element.textContent).toContain('No significant matches');
    expect(element.textContent).toContain('2 pairs compared');
    expect(element.textContent).toContain('1 skipped');
    expect(element.textContent).toContain('incomplete parsing');
  });

  it('shows both coverages and escapes source while highlighting stored ranges', async () => {
    const source = '<script>alert(1)</script>';
    const { element } = await render({
      state: 'complete',
      selectedPeer: 'b',
      studentName: 'Alex',
      sectionName: 'Block A',
      summary: {
        eligible_submission_count: 2,
        matches: [
          {
            peer_submission_id: 'b',
            peer_student_name: 'Bea',
            peer_block_section_name: 'Block B',
            match_type: 'normalized_duplicate',
            submission_coverage: 0.8,
            peer_coverage: 0.6,
            matched_token_count: 20,
          },
        ],
      },
      detail: {
        submission_code: source,
        peer_code: 'return 1;',
        submission_ranges: [
          { start: { row: 0, column: 8 }, end: { row: 0, column: 16 } },
        ],
        peer_ranges: [],
      },
    });
    expect(element.textContent).toContain('Bea');
    expect(element.textContent).toContain('Block B');
    expect(element.textContent).toContain('Same tokens');
    expect(element.textContent).toContain('Your answer: 80%');
    expect(element.textContent).toContain('Other answer: 60%');
    expect(element.querySelector('script')).toBeNull();
    expect(element.querySelector('code')!.textContent).toContain(source);
    expect(element.querySelector('.matched')!.textContent).toBe('alert(1)');
  });
});
