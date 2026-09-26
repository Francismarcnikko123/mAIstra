import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  BankQuestion,
  LinkedPaper,
  PaperLink,
  linkedPapers,
  plural,
  totalMarks,
  typeLabel,
} from './bank-groups';
import { QuestionPlace, gateBadge, questionLabel } from './question-labels';

/**
 * One question: its model answer, test cases and the papers linked to it.
 * Opened from the question bank.
 */
@Component({
  selector: 'app-question-page',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './question-page.html',
  styleUrls: ['./question-page.css'],
})
export class QuestionPageComponent {
  @Input({ required: true }) question!: BankQuestion;
  @Input() place: QuestionPlace | null = null;
  @Input() papers: PaperLink[] = [];
  @Input() gateResults = new Map<string, string>();
  @Output() back = new EventEmitter<void>();

  readonly plural = plural;
  readonly gateBadge = gateBadge;

  get label(): string {
    return questionLabel(this.question.question_name, this.place);
  }

  get validated(): boolean {
    return this.question.can_publish === true;
  }

  get linked(): LinkedPaper[] {
    return linkedPapers(this.question.id, this.papers);
  }

  /** "Program · 3 test cases · 5 marks · used by 2 papers" */
  get summary(): string {
    return [
      typeLabel(this.question.question_type),
      plural(this.testCases.length, 'test case'),
      plural(totalMarks(this.question), 'mark'),
      `used by ${plural(this.linked.length, 'paper')}`,
    ].join(' · ');
  }

  get testCases(): Record<string, unknown>[] {
    return Array.isArray(this.question.test_cases)
      ? (this.question.test_cases as Record<string, unknown>[])
      : [];
  }

  trackPaper(_index: number, linked: LinkedPaper) {
    return linked.paper.id ?? _index;
  }
}
