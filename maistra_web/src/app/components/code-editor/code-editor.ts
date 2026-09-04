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
    `:host {
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
    ::ng-deep .oc-med { position: absolute; background: rgba(239, 159, 39, 0.16); }
    ::ng-deep .oc-low { position: absolute; background: rgba(226, 75, 74, 0.17); }
    ::ng-deep .oc-med-gutter { border-left: 3px solid #ef9f27; }
    ::ng-deep .oc-low-gutter { border-left: 3px solid #e24b4a; }`,
  ],
})
export class CodeEditorComponent implements AfterViewInit, OnChanges, OnDestroy {
  @ViewChild('host', { static: true }) host!: ElementRef<HTMLElement>;

  @Input() value = '';
  @Output() valueChange = new EventEmitter<string>();

  /**
   * Per-editor-line OCR confidence (the backend's `min_confidence` for each
   * line, aligned 1:1 with the editor's rows). null = no score for that line.
   * Lines below the thresholds get a background tint + gutter mark so the
   * teacher's eye goes to the shaky reads first. Display-only: it never
   * changes the code, and a line's mark clears once the teacher edits it.
   */
  @Input() lineConfidence: (number | null)[] = [];

  // Two-tier thresholds, set by the flag-precision study on samples/ (361
  // lines, 2026-09-04): at <0.70 the flag is ~0.7-0.8 precise (when it fires
  // it's usually a real error); raising the "check" bound to 0.85 lifts recall
  // from ~0.07 to ~0.16 while precision stays ~0.71. Confidence is a HIGH-
  // precision, LOW-recall signal here (it misses ~84% of errors -- the model is
  // often confidently wrong), so these colors are a "look here first" hint, not
  // an error detector; the structural + misspelling checks and the verify
  // reminder are what cover the rest. See docs/ocr/EVALUATION.md.
  private static readonly LOW = 0.7; // below -> "likely wrong" (red)
  private static readonly MED = 0.85; // below -> "check" (amber)

  private editor?: ace.Ace.Editor;
  // Active confidence markers, so they can be removed on re-render or edit.
  private confidenceMarkers: { row: number; id: number; cls: string }[] = [];

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
    this.renderConfidence();

    // Shift-Alt-F is the conventional "format document" chord. Formatting is
    // teacher-triggered on purpose (see format()), never automatic on load.
    this.editor.commands.addCommand({
      name: 'formatC',
      bindKey: { win: 'Shift-Alt-F', mac: 'Shift-Alt-F' },
      exec: () => this.format(),
    });

    this.editor.on('change', (delta: any) => {
      const start = delta?.start?.row;
      const end = delta?.end?.row;
      if (start != null && end != null && end !== start) {
        // A whole line was inserted or removed: every row below shifts, so the
        // line->confidence mapping is no longer reliable. Clear all marks
        // rather than leave stale ones pointing at the wrong lines.
        this.clearAllConfidence();
      } else {
        // Inline edit on one line: that line no longer reflects the OCR's
        // read, so clear just its mark.
        this.clearConfidenceRows(start, end);
      }

      const current = this.editor!.getValue();
      if (current !== this.value) {
        this.value = current;
        this.valueChange.emit(current);
      }
    });
  }

  private clearAllConfidence(): void {
    if (!this.editor) return;
    const session = this.editor.session;
    for (const m of this.confidenceMarkers) {
      session.removeMarker(m.id);
      session.removeGutterDecoration(m.row, `${m.cls}-gutter`);
    }
    this.confidenceMarkers = [];
  }

  /**
   * Draw a background tint + gutter mark on each line whose confidence is below
   * threshold. Cleared and redrawn whenever the confidence input or the text
   * changes. Display-only -- touches no document content.
   */
  private renderConfidence(): void {
    if (!this.editor) return;
    const session = this.editor.session;
    this.clearAllConfidence();
    if (!this.lineConfidence?.length) return;

    const { Range } = (ace as any).require('ace/range');
    const rows = session.getLength();
    for (let row = 0; row < this.lineConfidence.length && row < rows; row++) {
      const conf = this.lineConfidence[row];
      if (conf == null) continue;
      let cls = '';
      if (conf < CodeEditorComponent.LOW) cls = 'oc-low';
      else if (conf < CodeEditorComponent.MED) cls = 'oc-med';
      else continue;
      const id = session.addMarker(
        new Range(row, 0, row, Infinity),
        cls,
        'fullLine',
      );
      session.addGutterDecoration(row, `${cls}-gutter`);
      this.confidenceMarkers.push({ row, id, cls });
    }
  }

  private clearConfidenceRows(startRow?: number, endRow?: number): void {
    if (!this.editor || startRow == null) return;
    const session = this.editor.session;
    const last = endRow ?? startRow;
    this.confidenceMarkers = this.confidenceMarkers.filter((m) => {
      if (m.row >= startRow && m.row <= last) {
        session.removeMarker(m.id);
        session.removeGutterDecoration(m.row, `${m.cls}-gutter`);
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
      this.editor.setValue(this.value ?? '', -1);
    }
    // A fresh extraction updates both value and lineConfidence; redraw the
    // marks after the text is in place.
    if (this.editor && (changes['lineConfidence'] || changes['value'])) {
      this.renderConfidence();
    }
  }

  ngOnDestroy(): void {
    this.editor?.destroy();
  }
}
