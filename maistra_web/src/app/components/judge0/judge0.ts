import {
  Component,
  Input,
  Output,
  EventEmitter,
  OnChanges,
  SimpleChanges,
  ChangeDetectorRef,
} from '@angular/core';
import { CodeEditorComponent } from '../code-editor/code-editor';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';

export interface TestCaseResult {
  caseNumber: number;
  stdin: string;
  expectedOutput: string;
  actualOutput: string;
  status: string;
  passed: boolean;
}

export interface LogicAnalysisResult {
  name: string;
  passed: boolean;
  weight: number;
  score: number;
}

@Component({
  selector: 'app-judge0',
  standalone: true,
  imports: [CodeEditorComponent, CommonModule],
  templateUrl: './judge0.html',
  styleUrl: './judge0.css',
})
export class Judge0 implements OnChanges {
  @Input() initialCode = ''; // comes from parent
  @Input() runCode = '';
  @Input() stdin = '';
  @Input() expectedOutput = '';
  @Input() submittedOutput = '';
  @Input() submitStatus = '';
  @Input() isSubmitting = false;
  @Input() testCaseResults: TestCaseResult[] = [];
  @Input() logicAnalysisResults: LogicAnalysisResult[] = [];
  @Input() hasQuestion = true;
  @Input() requiresQuestion = false;
  codeToRun = ''; // editable copy
  stdout = '';
  stderr = '';
  compileOutput = '';
  statusDescription = '';
  runNotification = '';
  firstRunTestCasePassed: boolean | null = null;
  isRunning = false;
  logicAnalysisExpanded = false;
  resultMode: 'run' | 'submit' = 'run';
  @Output() submitCode = new EventEmitter<void>();
  @Output() codeChange = new EventEmitter<string>();

  constructor(
    private http: HttpClient,
    private cdr: ChangeDetectorRef,
  ) {}
  ngOnChanges(changes: SimpleChanges): void {
    if (changes['initialCode']) {
      this.codeToRun = this.initialCode || '';
    }

    if (changes['logicAnalysisResults']) {
      this.logicAnalysisExpanded = false;
    }
  }
  executeCode() {
    if (this.requiresQuestion && !this.hasQuestion) {
      this.runNotification = 'Please select a question before running code.';
      this.cdr.detectChanges();
      return;
    }

    this.isRunning = true;
    this.resultMode = 'run';
    this.runNotification = '';
    this.stdout = '';
    this.stderr = '';
    this.compileOutput = '';
    this.statusDescription = '';
    this.firstRunTestCasePassed = null;

    this.cdr.detectChanges();
    console.log('Execute clicked');

    this.http
      .post<any>('http://127.0.0.1:8001/api/judge0/run', {
        source_code: this.runCode || this.codeToRun,
        language_id: 50,
        stdin: this.stdin,
      })
      .subscribe({
        next: (result) => {
          this.stdout = result.stdout || '';
          this.stderr = result.stderr || '';
          this.compileOutput = result.compile_output || '';
          this.statusDescription = result.status?.description || '';
          this.firstRunTestCasePassed = this.evaluateFirstRunTestCase();
          this.isRunning = false;

          this.cdr.detectChanges();
        },
        error: (error) => {
          this.stderr = 'Failed to execute code.';
          this.firstRunTestCasePassed = false;
          this.isRunning = false;

          console.error(error);
          this.cdr.detectChanges();
        },
      });
  }

  updateCode(value: string) {
    this.codeToRun = value;
    this.codeChange.emit(value);
  }

  requestSubmit() {
    this.resultMode = 'submit';
    this.submitCode.emit();
  }

  toggleLogicAnalysis() {
    this.logicAnalysisExpanded = !this.logicAnalysisExpanded;
  }

  get displayedOutput(): string {
    return (
      this.submittedOutput ||
      this.stdout ||
      this.stderr ||
      this.compileOutput ||
      (this.isRunning || this.isSubmitting ? 'Running...' : '(no output)')
    );
  }

  get shouldShowProcessingState(): boolean {
    return this.isRunning && !this.stdout && !this.stderr && !this.compileOutput;
  }

  get displayedStatus(): string {
    if (this.isRunning) return 'Running';
    if (this.isSubmitting) return 'Checking';
    return this.submitStatus || this.statusDescription;
  }

  get shouldShowTerminalResults(): boolean {
    if (this.isRunning) return false;
    if (this.resultMode === 'submit') return this.shouldShowSubmitResults;

    return (
      !!this.stdout ||
      !!this.submittedOutput ||
      !!this.stderr ||
      !!this.compileOutput ||
      this.testCaseResults.length > 0
    );
  }

  get shouldShowRunResultPanel(): boolean {
    return (
      this.resultMode === 'run' &&
      (!!this.stdout ||
        !!this.submittedOutput ||
        !!this.stderr ||
        !!this.compileOutput ||
        this.firstRunTestCasePassed !== null)
    );
  }

  get shouldShowSubmitResults(): boolean {
    return this.resultMode === 'submit' && this.testCaseResults.length > 0;
  }

  get hasErrorStatus(): boolean {
    return (
      !!this.compileOutput ||
      !!this.stderr ||
      this.displayedStatus === 'Wrong Answer' ||
      this.displayedStatus === 'Error' ||
      this.firstRunTestCasePassed === false
    );
  }

  get passedTestCaseCount(): number {
    return this.testCaseResults.filter((result) => result.passed).length;
  }

  get firstTestCaseResult(): TestCaseResult | null {
    return this.testCaseResults[0] ?? null;
  }

  get firstTestCasePassedLabel(): string {
    const passed = this.firstTestCaseResult?.passed ?? this.firstRunTestCasePassed;
    if (passed === null) return '';
    return passed ? 'First Test Case Passed' : 'First Test Case Failed';
  }

  get runResultTitle(): string {
    const passed = this.firstTestCaseResult?.passed ?? this.firstRunTestCasePassed;
    if (passed === null) return '';
    return passed ? 'Accepted' : 'Wrong Answer :(';
  }

  get runResultSummary(): string {
    const passed = this.firstTestCaseResult?.passed ?? this.firstRunTestCasePassed;
    if (passed === null) return '';
    return passed ? '1/1 test case passed' : '1/1 test case failed';
  }

  get passedLogicCheckCount(): number {
    return this.logicAnalysisResults.filter((result) => result.passed).length;
  }

  private evaluateFirstRunTestCase(): boolean | null {
    if (this.stderr || this.compileOutput || !this.expectedOutput.trim()) {
      return null;
    }

    return this.normalizeOutput(this.stdout) === this.normalizeOutput(this.expectedOutput);
  }

  private normalizeOutput(value: string): string {
    return value.trim().toLowerCase().replace(/\s*:\s*/g, ':').replace(/\s+/g, ' ');
  }
}
