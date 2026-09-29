import {
  Component,
  Input,
  Output,
  EventEmitter,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  ChangeDetectorRef,
} from '@angular/core';
import { Subscription } from 'rxjs';
import { CodeEditorComponent } from '../code-editor/code-editor';
import { CommonModule } from '@angular/common';
import {
  Judge0Service,
  judge0ErrorMessage,
} from '../../services/judge0.service';
import { normalizeOutput } from '../../utils/normalize-output';

/**
 * The grade of one test case. SubmissionsListComponent.runTestCases builds
 * these, and they are saved as `grading_results` in Supabase.
 */
export interface TestCaseResult {
  caseNumber: number; // 1, 2, 3, ... in the question's order
  stdin: string; // input given to scanf() ('' for function questions)
  expectedOutput: string; // from the question, normalized
  actualOutput: string; // what the student's code printed, normalized
  status: string; // 'Accepted', 'Wrong Answer', or Judge0's error text
  passed: boolean; // true = 1 point
}

/**
 * The grader panel shown in Step 3 ("Run and grade") of the submission review.
 *
 * It shows the code and two buttons:
 * - Run Sample: this component calls Judge0 itself, once, with the first test
 *   case, and shows that single result. Nothing is saved.
 * - Submit Code: this component only emits `submitCode`. The parent
 *   (SubmissionsListComponent.checkSubmission) runs every test case, saves
 *   the grade, and passes the results back in through `testCaseResults`.
 *
 * `resultMode` decides which of the two results is on screen.
 */
@Component({
  selector: 'app-judge0',
  standalone: true,
  imports: [CodeEditorComponent, CommonModule],
  templateUrl: './judge0.html',
  styleUrl: './judge0.css',
})
export class Judge0 implements OnChanges, OnDestroy {
  // ── Inputs from the parent ──
  @Input() initialCode = ''; // comes from parent
  // The code shown in the editor is the student's code only. `runCode` is
  // the complete program Run Sample sends (with #include and, for function
  // questions, the generated main()). Empty means: run the editor's code.
  @Input() runCode = '';
  // First test case's stdin and expected output, for Run Sample.
  @Input() stdin = '';
  @Input() expectedOutput = '';
  // Results of the last Submit Code, filled in by the parent.
  @Input() submittedOutput = '';
  @Input() submitStatus = '';
  @Input() isSubmitting = false;
  @Input() testCaseResults: TestCaseResult[] = [];
  // With requiresQuestion on, Run Sample refuses to run until a question is
  // linked (no question means no test case to compare against).
  @Input() hasQuestion = true;
  @Input() requiresQuestion = false;
  // Show the code without letting it be edited, e.g. when grading must run on
  // the saved code and edits belong in an earlier step.
  @Input() codeReadOnly = false;
  // Offer "Edit in Review code" next to read-only code. The parent opts in
  // and handles editCode by opening that step.
  @Input() canEditCode = false;

  // ── State of the last Run Sample ──
  codeToRun = ''; // editable copy
  stdout = '';
  stderr = '';
  compileOutput = '';
  statusDescription = '';
  // Judge0's own status id — 3 means Accepted (compiled + ran with no
  // compile error or runtime crash). This is the real success/failure
  // signal; compileOutput/stderr being non-empty does NOT by itself mean
  // failure (a program can compile with warnings, e.g. a missing include,
  // and still run correctly).
  statusId: number | null = null;
  runNotification = ''; // e.g. "Please select a question before running code."
  // Did the sample match the first test case? null = not run, the run could
  // not be done (Judge0 down, timeout), or no expected output to compare with.
  firstRunTestCasePassed: boolean | null = null;
  isRunning = false;
  // 'run' shows the Run Sample result; 'submit' shows the graded test cases.
  resultMode: 'run' | 'submit' = 'run';

  // ── Events to the parent ──
  // "Submit Code" was pressed: the parent grades every test case.
  @Output() submitCode = new EventEmitter<void>();
  @Output() codeChange = new EventEmitter<string>();
  @Output() editCode = new EventEmitter<void>();
  // True when a sample run starts, false when it ends, so the parent can keep
  // the teacher from switching away (which would drop the run).
  @Output() runningChange = new EventEmitter<boolean>();
  private runSubscription?: Subscription;

  constructor(
    private judge0: Judge0Service,
    private cdr: ChangeDetectorRef,
  ) {}
  ngOnChanges(changes: SimpleChanges): void {
    if (changes['initialCode']) {
      this.codeToRun = this.initialCode || '';
    }
    // Only a different grade switches the view: a new one, or a regrade from
    // another tab. The parent re-sends the same persisted grade as a fresh
    // array on every realtime reload, which must not pull the teacher away
    // from a sample run they are reading.
    const resultsChange = changes['testCaseResults'];
    if (
      resultsChange &&
      this.testCaseResults.length > 0 &&
      !Judge0.sameResults(resultsChange.previousValue ?? [], this.testCaseResults)
    ) {
      this.resultMode = 'submit';
    }
  }

  // Field by field rather than by reference or JSON: a reloaded grade is a new
  // array whose objects come back from jsonb with their keys reordered.
  private static sameResults(
    previous: TestCaseResult[],
    next: TestCaseResult[],
  ): boolean {
    return (
      previous.length === next.length &&
      previous.every((result, index) => {
        const other = next[index];
        return (
          result.caseNumber === other.caseNumber &&
          result.stdin === other.stdin &&
          result.expectedOutput === other.expectedOutput &&
          result.actualOutput === other.actualOutput &&
          result.status === other.status &&
          result.passed === other.passed
        );
      })
    );
  }

  // One thing at a time: both buttons are disabled while either is running.
  get isExecutionBusy(): boolean {
    return this.isRunning || this.isSubmitting;
  }

  /**
   * "Run Sample": runs the code once on Judge0 with the first test case's
   * stdin, then compares stdout with its expected output. Shown only here;
   * nothing is saved and no grade changes.
   */
  executeCode() {
    if (this.isExecutionBusy) return;

    if (this.requiresQuestion && !this.hasQuestion) {
      this.runNotification = 'Please select a question before running code.';
      this.cdr.detectChanges();
      return;
    }

    // Clear the previous run so old output never shows next to a new run.
    this.isRunning = true;
    this.resultMode = 'run';
    this.runNotification = '';
    this.stdout = '';
    this.stderr = '';
    this.compileOutput = '';
    this.statusDescription = '';
    this.statusId = null;
    this.firstRunTestCasePassed = null;
    this.runningChange.emit(true);

    this.cdr.detectChanges();
    this.runSubscription = this.judge0
      .runCCode(this.runCode || this.codeToRun, this.stdin)
      .subscribe({
        next: (result) => {
          this.stdout = result.stdout || '';
          this.stderr = result.stderr || '';
          this.compileOutput = result.compile_output || '';
          this.statusDescription = result.status?.description || '';
          this.statusId = result.status?.id ?? null;
          this.firstRunTestCasePassed = this.evaluateFirstRunTestCase();
          this.isRunning = false;
          this.runningChange.emit(false);

          this.cdr.detectChanges();
        },
        // The wrapper could not run the code at all (Judge0 down, timeout);
        // its reason is shown in the output box. A compile error is not this
        // case: it arrives in `next` above.
        error: (error) => {
          this.stderr = judge0ErrorMessage(error, 'Failed to execute code.');
          this.statusDescription = 'Execution failed';
          this.firstRunTestCasePassed = null;
          this.isRunning = false;
          this.runningChange.emit(false);

          console.error(error);
          this.cdr.detectChanges();
        },
      });
  }

  // A grader closed mid-run ignores the late answer instead of updating a
  // view that is gone.
  ngOnDestroy(): void {
    this.runSubscription?.unsubscribe();
  }

  updateCode(value: string) {
    this.codeToRun = value;
    this.codeChange.emit(value);
  }

  // "Submit Code": the parent does the grading and sends the results back.
  requestSubmit() {
    if (this.isExecutionBusy) return;

    this.resultMode = 'submit';
    this.submitCode.emit();
  }

  // Leaving mid-run would hide the results of a run or grade still in flight.
  requestEditCode() {
    if (this.isExecutionBusy) return;
    this.editCode.emit();
  }

  // ── What the template shows ──

  // Text for the "Your Output" box: stdout first, else the error text, so a
  // failed compile or crash still shows why.
  get displayedOutput(): string {
    if (this.resultMode === 'run') {
      return (
        this.stdout ||
        this.stderr ||
        this.compileOutput ||
        (this.isRunning ? 'Running...' : '(no output)')
      );
    }

    return (
      this.submittedOutput ||
      this.stdout ||
      this.stderr ||
      this.compileOutput ||
      (this.isRunning || this.isSubmitting ? 'Running...' : '(no output)')
    );
  }

  // The "Processing code" spinner, while a sample run has no output yet.
  get shouldShowProcessingState(): boolean {
    return (
      this.isRunning && !this.stdout && !this.stderr && !this.compileOutput
    );
  }

  get displayedStatus(): string {
    if (this.resultMode === 'run') {
      return this.isRunning ? 'Running' : this.statusDescription;
    }
    if (this.isSubmitting) return 'Checking';
    return this.submitStatus;
  }

  // The whole results area below the buttons, for either mode.
  get shouldShowTerminalResults(): boolean {
    if (this.isRunning) return false;
    if (this.resultMode === 'submit') return this.shouldShowSubmitResults;

    return (
      !!this.stdout ||
      !!this.stderr ||
      !!this.compileOutput ||
      !!this.statusDescription ||
      this.firstRunTestCasePassed !== null
    );
  }

  // Run Sample's Input / Your Output / Expected Output boxes.
  get shouldShowRunResultPanel(): boolean {
    return (
      this.resultMode === 'run' &&
      (!!this.stdout ||
        !!this.stderr ||
        !!this.compileOutput ||
        !!this.statusDescription ||
        this.firstRunTestCasePassed !== null)
    );
  }

  // Submit Code's list of test-case cards.
  get shouldShowSubmitResults(): boolean {
    return this.resultMode === 'submit' && this.testCaseResults.length > 0;
  }

  // Colours the status label red.
  get hasErrorStatus(): boolean {
    return (
      (this.statusId !== null && this.statusId !== 3) ||
      this.displayedStatus === 'Wrong Answer' ||
      this.displayedStatus === 'Error' ||
      this.displayedStatus === 'Execution failed' ||
      this.firstRunTestCasePassed === false
    );
  }

  // Score: every test case is worth 1 point, e.g. 2 of 3 passed = 66.67%.
  get passedTestCaseCount(): number {
    return this.testCaseResults.filter((result) => result.passed).length;
  }

  get testCaseScorePercentage(): number {
    if (!this.testCaseResults.length) return 0;
    return Number(
      ((this.passedTestCaseCount / this.testCaseResults.length) * 100).toFixed(
        2,
      ),
    );
  }

  get testCaseScoreSummary(): string {
    if (!this.testCaseResults.length) return '';
    return `${this.passedTestCaseCount}/${this.testCaseResults.length} test cases passed — Score: ${this.testCaseScorePercentage}%`;
  }

  getTestCasePointLabel(result: TestCaseResult): string {
    return result.passed ? '1/1 point' : '0/1 point';
  }

  get firstTestCaseResult(): TestCaseResult | null {
    return this.testCaseResults[0] ?? null;
  }

  // Labels for the Run Sample result; '' hides them when nothing was compared.
  get firstTestCasePassedLabel(): string {
    const passed = this.firstRunTestCasePassed;
    if (passed === null) return '';
    return passed ? 'First Test Case Passed' : 'First Test Case Failed';
  }

  get runResultTitle(): string {
    const passed = this.firstRunTestCasePassed;
    if (passed === null) return '';
    return passed ? 'Accepted' : 'Wrong Answer :(';
  }

  get runResultSummary(): string {
    const passed = this.firstRunTestCasePassed;
    if (passed === null) return '';
    return passed ? '1/1 test case passed' : '1/1 test case failed';
  }

  // Passed = ran normally (status 3) and the output matches once both are
  // normalized (case, spaces, ':'), the same rule grading uses.
  private evaluateFirstRunTestCase(): boolean | null {
    if (!this.expectedOutput.trim()) {
      return null; // nothing configured to compare against
    }
    if (this.statusId !== 3) {
      return false; // real compile error or runtime crash
    }

    return (
      normalizeOutput(this.stdout) === normalizeOutput(this.expectedOutput)
    );
  }
}
