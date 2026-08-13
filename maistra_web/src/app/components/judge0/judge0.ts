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

@Component({
  selector: 'app-judge0',
  standalone: true,
  imports: [CodeEditorComponent, CommonModule],
  templateUrl: './judge0.html',
  styleUrl: './judge0.css',
})
export class Judge0 implements OnChanges {
  @Input() initialCode = ''; // comes from parent
  codeToRun = ''; // editable copy
  stdin = '';
  stdout = '';
  stderr = '';
  compileOutput = '';
  statusDescription = '';
  isRunning = false;

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
        source_code: this.codeToRun,
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
}
