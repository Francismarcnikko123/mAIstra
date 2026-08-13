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
  codeToRun = ''; // editable copy
  stdout = '';
  stderr = '';
  compileOutput = '';
  statusDescription = '';
  isRunning = false;
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
  }
  executeCode() {
    this.isRunning = true;
    this.stdout = '';
    this.stderr = '';
    this.compileOutput = '';
    this.statusDescription = '';

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
          this.isRunning = false;

          this.cdr.detectChanges();
        },
        error: (error) => {
          this.stderr = 'Failed to execute code.';
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
    this.submitCode.emit();
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

  get displayedStatus(): string {
    if (this.isRunning) return 'Running';
    if (this.isSubmitting) return 'Checking';
    return this.submitStatus || this.statusDescription;
  }

  get shouldShowTerminalResults(): boolean {
    return (
      this.isRunning ||
      this.isSubmitting ||
      !!this.stdout ||
      !!this.submittedOutput ||
      !!this.stderr ||
      !!this.compileOutput ||
      this.testCaseResults.length > 0
    );
  }

  get hasErrorStatus(): boolean {
    return (
      !!this.compileOutput ||
      !!this.stderr ||
      this.displayedStatus === 'Wrong Answer' ||
      this.displayedStatus === 'Error'
    );
  }

  get passedTestCaseCount(): number {
    return this.testCaseResults.filter((result) => result.passed).length;
  }
}
