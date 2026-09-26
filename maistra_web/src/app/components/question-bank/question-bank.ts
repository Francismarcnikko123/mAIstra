import { ChangeDetectorRef, Component, EventEmitter, OnInit, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SupabaseService } from '../../services/supabase';
import {
  BankGroup,
  BankQuestion,
  BankSection,
  BankSectionItem,
  PaperLink,
  buildBankGroups,
  plural,
  typeLabel,
} from './bank-groups';
import { QuestionPlace, indexQuestionPlaces } from './question-labels';
import { QuestionPageComponent } from './question-page';
import { EditQuestionRequest } from '../question-form/question-form';

/**
 * Question bank: every question, grouped by section and sorted by number,
 * with unsectioned questions last under "No section yet".
 */
@Component({
  selector: 'app-question-bank',
  standalone: true,
  imports: [CommonModule, FormsModule, QuestionPageComponent],
  templateUrl: './question-bank.html',
  styleUrls: ['./question-bank.css'],
})
export class QuestionBankComponent implements OnInit {
  /** "+ Create question": the app shell opens the form. */
  @Output() createQuestion = new EventEmitter<void>();
  /** Edit on a question page: the app opens the form pre-filled. */
  @Output() editQuestion = new EventEmitter<EditQuestionRequest>();

  isLoading = true;
  errorMessage = '';
  /** Shown when sections can't be read, e.g. before the migration runs. */
  sectionsNotice = '';
  search = '';
  collapsed: Record<string, boolean> = {};
  /** Question whose page is open, or null for the list. */
  openQuestionId: string | null = null;

  private questions: BankQuestion[] = [];
  private sections: BankSection[] = [];
  private items: BankSectionItem[] = [];
  private links: PaperLink[] = [];
  gateResults = new Map<string, string>();

  readonly plural = plural;
  readonly typeLabel = typeLabel;

  constructor(
    private supabase: SupabaseService,
    private cdr: ChangeDetectorRef,
  ) {}

  async ngOnInit() {
    await this.load();
  }

  async load() {
    this.isLoading = true;
    this.errorMessage = '';
    this.sectionsNotice = '';
    this.cdr.detectChanges();

    const [questions, sections, items, links, gateResults] = await Promise.all([
      this.supabase.getQuestions(),
      this.supabase.getQuestionSections(),
      this.supabase.getSectionItems(),
      this.supabase.getQuestionPaperLinks(),
      this.supabase.getGateResults(),
    ]);
    this.gateResults = gateResults;

    if (questions.error) {
      this.errorMessage = 'Could not load questions: ' + questions.error.message;
    } else {
      this.questions = (questions.data ?? []) as BankQuestion[];
    }

    // Without sections every question still shows, under "No section yet".
    if (sections.error || items.error) {
      this.sectionsNotice =
        'Sections are not available yet, so every question is listed under "No section yet".';
      this.sections = [];
      this.items = [];
    } else {
      this.sections = (sections.data ?? []) as BankSection[];
      this.items = (items.data ?? []) as BankSectionItem[];
    }

    // Paper counts are a nice-to-have; show 0 rather than failing the bank.
    this.links = links.error ? [] : ((links.data ?? []) as unknown as PaperLink[]);

    this.isLoading = false;
    this.cdr.detectChanges();
  }

  get groups(): BankGroup[] {
    return buildBankGroups(
      this.questions,
      this.sections,
      this.items,
      this.links,
      this.search,
    );
  }

  get totalCount(): number {
    return this.questions.length;
  }

  groupKey(group: BankGroup): string {
    return group.sectionId ?? 'none';
  }

  trackGroup = (_index: number, group: BankGroup) => this.groupKey(group);

  toggleGroup(group: BankGroup) {
    const key = this.groupKey(group);
    this.collapsed[key] = !this.collapsed[key];
  }

  isCollapsed(group: BankGroup): boolean {
    // While searching, show every match.
    return !this.search.trim() && !!this.collapsed[this.groupKey(group)];
  }

  requestEdit(question: BankQuestion) {
    const place = indexQuestionPlaces(this.sections, this.items).get(question.id);
    this.editQuestion.emit({
      question,
      place: place ? { sectionId: place.sectionId, number: place.number } : null,
    });
  }

  openQuestion(id: string) {
    this.openQuestionId = id;
  }

  closeQuestion() {
    this.openQuestionId = null;
  }

  get openQuestionData(): BankQuestion | null {
    return this.questions.find((q) => q.id === this.openQuestionId) ?? null;
  }

  get openQuestionPlace(): QuestionPlace | null {
    if (!this.openQuestionId) return null;
    return indexQuestionPlaces(this.sections, this.items).get(this.openQuestionId) ?? null;
  }

  get paperLinks(): PaperLink[] {
    return this.links;
  }
}
