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
import type { OcrReviewFlag } from '../submissions-list/ocr-review-flags';

export interface OcrReviewEdit {
  startLine: number;
  endLine: number;
  lineStructureChanged: boolean;
}

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
    `
      :host {
        display: block;
      }

      .ace-host {
        width: 100%;
        height: var(--code-editor-height, 300px);
        border: 1px solid #ccc;
        border-radius: 6px;
        box-sizing: border-box;
      }

      /* Ace builds its marker/gutter DOM at runtime, so Angular's view
       encapsulation never tags it -- ::ng-deep lets these reach it. */
      ::ng-deep .ocr-review-strong {
        position: absolute;
        background: rgba(139, 92, 246, 0.22);
      }

      ::ng-deep .ocr-review-soft {
        position: absolute;
        background: rgba(139, 92, 246, 0.1);
      }

      ::ng-deep .ocr-review-strong-gutter {
        border-left: 3px solid #8b5cf6;
      }

      ::ng-deep .ocr-review-soft-gutter {
        border-left: 3px solid #a78bfa;
      }
    `,
  ],
})
export class CodeEditorComponent
  implements AfterViewInit, OnChanges, OnDestroy
{
  @ViewChild('host', { static: true }) host!: ElementRef<HTMLElement>;

  @Input() value = '';
  @Output() valueChange = new EventEmitter<string>();

  /** Normalized, one-based line flags supplied by the review workspace. */
  @Input() lineReviewFlags: OcrReviewFlag[] = [];
  @Output() reviewEvidenceEdited = new EventEmitter<OcrReviewEdit>();

  private editor?: ace.Ace.Editor;
  private applyingExternalValue = false;
  private reviewMarkers: { row: number; id: number; cls: string }[] = [];

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
    this.renderReviewFlags();

    // Shift-Alt-F is the conventional "format document" chord. Formatting is
    // teacher-triggered on purpose (see format()), never automatic on load.
    this.editor.commands.addCommand({
      name: 'formatC',
      bindKey: { win: 'Shift-Alt-F', mac: 'Shift-Alt-F' },
      exec: () => this.format(),
    });

    this.editor.on('change', (delta: any) => {
      const startRow = delta?.start?.row;
      const endRow = delta?.end?.row;
      const lineStructureChanged =
        startRow != null &&
        endRow != null &&
        (startRow !== endRow || (delta?.lines?.length ?? 0) > 1);

      if (!this.applyingExternalValue && startRow != null && endRow != null) {
        if (lineStructureChanged) {
          // A row-changing edit makes extraction-era line numbers unreliable.
          this.clearAllReviewMarkers();
        } else {
          // Inline edits dismiss the OCR-era evidence for the touched row.
          this.clearReviewRows(startRow, endRow);
        }
        this.reviewEvidenceEdited.emit({
          startLine: startRow + 1,
          endLine: endRow + 1,
          lineStructureChanged,
        });
      }

      const current = this.editor!.getValue();
      if (current !== this.value) {
        this.value = current;
        this.valueChange.emit(current);
      }
    });
  }

  private clearAllReviewMarkers(): void {
    if (!this.editor) return;
    const session = this.editor.session;
    for (const marker of this.reviewMarkers) {
      session.removeMarker(marker.id);
      session.removeGutterDecoration(marker.row, `${marker.cls}-gutter`);
    }
    this.reviewMarkers = [];
  }

  /**
   * Draw one OCR-review marker per normalized flag. The marker is display-only
   * and never changes the editor document.
   */
  private renderReviewFlags(): void {
    if (!this.editor) return;
    const session = this.editor.session;
    this.clearAllReviewMarkers();
    if (!this.lineReviewFlags.length) return;

    const { Range } = (ace as any).require('ace/range');
    const rows = session.getLength();
    for (const flag of this.lineReviewFlags) {
      const row = flag.line - 1;
      if (!Number.isInteger(row) || row < 0 || row >= rows) continue;
      const cls =
        flag.strength === 'strong' ? 'ocr-review-strong' : 'ocr-review-soft';
      const id = session.addMarker(
        new Range(row, 0, row, Infinity),
        cls,
        'fullLine',
      );
      session.addGutterDecoration(row, `${cls}-gutter`);
      this.reviewMarkers.push({ row, id, cls });
    }
  }

  private clearReviewRows(startRow: number, endRow: number): void {
    if (!this.editor || startRow == null) return;
    const session = this.editor.session;
    this.reviewMarkers = this.reviewMarkers.filter((marker) => {
      if (marker.row >= startRow && marker.row <= endRow) {
        session.removeMarker(marker.id);
        session.removeGutterDecoration(marker.row, `${marker.cls}-gutter`);
        return false;
      }
      return true;
    });
  }

  /**
   * Re-indent the current buffer by C brace depth. This is a *display*
   * convenience for the teacher's editing pass, not part of OCR extraction:
   * OCR deliberately outputs a faithful, flat transcription (line structure
   * only, no indentation), and this lets the teacher make it readable on
   * demand without asserting anything about the student's handwriting.
   *
   * It only rewrites leading whitespace — never any other character — and is a
   * single undoable edit (Ctrl+Z reverts it). Because it keys off braces, it's
   * only as correct as the braces in the buffer; OCR frequently misreads `}`
   * (see the OCR brace error profile), so it's most useful after the teacher
   * has fixed the braces, not before. Not brace-aware of `switch`/`case`
   * labels or line-continuations — a simple, predictable reindent, not a full
   * C beautifier.
   */
  format(): void {
    if (!this.editor) return;
    const current = this.editor.getValue();
    const formatted = CodeEditorComponent.reindent(current);
    if (formatted === current) return;

    // Replace the whole document as one edit so the teacher can undo it, and
    // so the 'change' handler above still fires the two-way [(value)] update.
    const session = this.editor.session;
    const { Range } = (ace as any).require('ace/range');
    const lastRow = session.getLength() - 1;
    const lastCol = session.getLine(lastRow).length;
    session.replace(new Range(0, 0, lastRow, lastCol), formatted);
    this.editor.clearSelection();
  }

  /**
   * Pure brace-depth reindenter. Braces inside string/char literals and `//`
   * or block comments are ignored so they don't shift the indent level. A line
   * that starts by closing a block dedents itself.
   */
  private static reindent(source: string, unit = '  '): string {
    const out: string[] = [];
    let depth = 0;
    let inBlockComment = false;

    for (const raw of source.split('\n')) {
      const trimmed = raw.trim();
      if (trimmed === '') {
        out.push('');
        continue;
      }

      // A line whose first real character closes a block sits one level out.
      const startsWithClose = !inBlockComment && trimmed[0] === '}';
      const lineDepth = Math.max(0, depth - (startsWithClose ? 1 : 0));
      out.push(unit.repeat(lineDepth) + trimmed);

      // Walk the line to update depth for the lines below, skipping any braces
      // that live inside literals or comments.
      let inString: string | null = null;
      for (let i = 0; i < trimmed.length; i++) {
        const ch = trimmed[i];
        const next = trimmed[i + 1];
        if (inBlockComment) {
          if (ch === '*' && next === '/') {
            inBlockComment = false;
            i++;
          }
          continue;
        }
        if (inString) {
          if (ch === '\\') {
            i++; // skip the escaped character
          } else if (ch === inString) {
            inString = null;
          }
          continue;
        }
        if (ch === '/' && next === '/') break; // rest of line is a comment
        if (ch === '/' && next === '*') {
          inBlockComment = true;
          i++;
          continue;
        }
        if (ch === '"' || ch === "'") {
          inString = ch;
          continue;
        }
        if (ch === '{') depth++;
        else if (ch === '}') depth = Math.max(0, depth - 1);
      }
    }
    return out.join('\n');
  }

  ngOnChanges(changes: SimpleChanges): void {
    // Reflect external updates (e.g. OCR result arriving) without clobbering
    // what the teacher is typing.
    if (
      this.editor &&
      changes['value'] &&
      this.value !== this.editor.getValue()
    ) {
      this.applyingExternalValue = true;
      try {
        this.editor.setValue(this.value ?? '', -1);
      } finally {
        this.applyingExternalValue = false;
      }
    }
    // A fresh extraction updates both value and lineReviewFlags; redraw the
    // marks after the text is in place.
    if (this.editor && (changes['lineReviewFlags'] || changes['value'])) {
      this.renderReviewFlags();
    }
  }

  ngOnDestroy(): void {
    this.editor?.destroy();
  }
}
