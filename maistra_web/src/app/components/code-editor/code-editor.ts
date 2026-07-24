import {
  Component,
  ElementRef,
  Input,
  Output,
  EventEmitter,
  AfterViewInit,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import * as ace from 'ace-builds';
import 'ace-builds/src-noconflict/mode-c_cpp';
import 'ace-builds/src-noconflict/theme-monokai';

/**
 * Thin wrapper around the Ace editor so the teacher edits the extracted C code
 * with syntax highlighting instead of a plain textarea. Two-way bindable via
 * [(value)] so it drops in where the old textarea's [(ngModel)] was.
 */
@Component({
  selector: 'app-code-editor',
  standalone: true,
  template: `<div #host class="ace-host"></div>`,
  styles: [
    `.ace-host {
      width: 100%;
      height: 300px;
      border: 1px solid #ccc;
      border-radius: 6px;
    }`,
  ],
})
export class CodeEditorComponent implements AfterViewInit, OnChanges, OnDestroy {
  @ViewChild('host', { static: true }) host!: ElementRef<HTMLElement>;

  @Input() value = '';
  @Output() valueChange = new EventEmitter<string>();

  private editor?: ace.Ace.Editor;

  ngAfterViewInit(): void {
    this.editor = ace.edit(this.host.nativeElement);
    this.editor.session.setMode('ace/mode/c_cpp');
    this.editor.setTheme('ace/theme/monokai');
    // No language server / background worker: we only need highlighting, and
    // disabling the worker avoids having to configure worker asset paths.
    this.editor.session.setUseWorker(false);
    this.editor.setOptions({
      fontSize: '14px',
      showPrintMargin: false,
      tabSize: 2,
      useSoftTabs: true,
      highlightActiveLine: true,
    });
    this.editor.setValue(this.value ?? '', -1);

    this.editor.on('change', () => {
      const current = this.editor!.getValue();
      if (current !== this.value) {
        this.value = current;
        this.valueChange.emit(current);
      }
    });
  }

  ngOnChanges(changes: SimpleChanges): void {
    // Reflect external updates (e.g. OCR result arriving) without clobbering
    // what the teacher is typing.
    if (
      this.editor &&
      changes['value'] &&
      this.value !== this.editor.getValue()
    ) {
      this.editor.setValue(this.value ?? '', -1);
    }
  }

  ngOnDestroy(): void {
    this.editor?.destroy();
  }
}
