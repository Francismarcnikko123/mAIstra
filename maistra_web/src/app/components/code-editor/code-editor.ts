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
    }`,
  ],
})
export class CodeEditorComponent implements AfterViewInit, OnChanges, OnDestroy {
  @ViewChild('host', { static: true }) host!: ElementRef<HTMLElement>;

  @Input() value = '';
  /** Guide text shown only while the editor is empty. */
  @Input() placeholder = '';
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
      placeholder: this.placeholder,
    });
    this.editor.setValue(this.value ?? '', -1);

    // Shift-Alt-F is the conventional "format document" chord. Formatting is
    // teacher-triggered on purpose (see format()), never automatic on load.
    this.editor.commands.addCommand({
      name: 'formatC',
      bindKey: { win: 'Shift-Alt-F', mac: 'Shift-Alt-F' },
      exec: () => this.format(),
    });

    this.editor.on('change', () => {
      const current = this.editor!.getValue();
      if (current !== this.value) {
        this.value = current;
        this.valueChange.emit(current);
      }
    });
  }

  /**
   * Re-indent the current buffer to canonical C by brace depth. This is a
   * *display* normalization the teacher runs on demand, not part of OCR
   * extraction. Extraction is paper-faithful: it reconstructs the student's
   * own handwritten indentation and blank-line spacing, so the editor mirrors
   * the paper -- which need not match how C is written in an IDE. Format
   * overrides that layout with brace-depth structure so the teacher can read
   * it as IDE-style C. The original OCR text is kept separately; Format only
   * touches the editable working copy.
   *
   * It only rewrites leading whitespace — never any other character — and is a
   * single undoable edit (Ctrl+Z reverts it). Because it keys off braces, it's
   * only as correct as the braces in the buffer; OCR frequently misreads `}`
   * (see the OCR brace error profile), so it's most useful after the teacher
   * has fixed the braces, not before. It covers all of C's indentation (brace
   * depth, `switch`/`case`, line continuations, labels, preprocessor) but stays
   * a predictable reindent, not a full C beautifier — it never changes
   * intra-line spacing, wraps lines, or inserts/removes braces.
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
   * Re-measure the editor after its container was hidden (an inactive
   * program tab). Ace sizes itself on show, so without this a tab switched
   * to can render blank until the window resizes.
   */
  refresh(): void {
    this.editor?.resize(true);
  }

  /**
   * Complete C indentation reindenter -- whitespace-only. It rewrites ONLY the
   * leading whitespace of each line; every other character is emitted verbatim,
   * so it can never change the student's code content. It covers all of C's
   * indentation rules:
   *   1. Brace nesting: `{` opens a level, `}` closes; a line starting with `}`
   *      dedents itself.
   *   2. switch/case: `case`/`default:` labels sit at the switch's content
   *      level, their bodies one level deeper (case labels are not brace-scoped,
   *      so they are tracked as a per-switch "case body open" level).
   *   3. Line continuation: a line reached with unbalanced `(`/`[` open from
   *      prior lines is a continuation and indents one level deeper.
   *   4. Labels: a bare `goto` target (`name:`) sits one level out.
   *   5. Preprocessor: a line starting with `#` sits at column 0 and is opaque
   *      (does not affect brace/continuation state).
   * Braces/parens inside string/char literals and `//` or block comments are
   * ignored. Degenerate input (unbalanced braces) never throws. It remains a
   * predictable reindenter, NOT a full beautifier: it never reflows lines,
   * inserts/removes braces, or changes intra-line spacing.
   */
  private static readonly CASE_LABEL = /^(case\b[^:]*|default)\s*:/;
  private static readonly GOTO_LABEL = /^[A-Za-z_]\w*\s*:\s*$/;

  private static reindent(source: string, unit = '  '): string {
    const out: string[] = [];
    // One frame per open `{ }` block; caseOpen adds a body level inside a switch.
    const frames: { isSwitch: boolean; caseOpen: boolean }[] = [];
    let contDepth = 0; // net unclosed ( or [ carried from prior lines
    let pendingSwitch = false; // a `switch` whose `{` is on a later line
    let inBlockComment = false;

    for (const raw of source.split('\n')) {
      // Strip ONLY leading whitespace -- trailing whitespace and every other
      // character are preserved verbatim, so reindent changes nothing but a
      // line's indentation.
      const trimmed = raw.replace(/^\s+/, '');
      if (trimmed === '') {
        out.push('');
        continue;
      }

      const caseOpen = frames.reduce((n, f) => n + (f.caseOpen ? 1 : 0), 0);
      const blockLevel = frames.length + caseOpen;
      const top = frames[frames.length - 1];
      const startsWithClose = !inBlockComment && trimmed[0] === '}';
      const isCaseLabel = CodeEditorComponent.CASE_LABEL.test(trimmed);

      let level: number;
      if (!inBlockComment && trimmed[0] === '#') {
        // Rule 5: preprocessor -> column 0, opaque (no state change).
        out.push(trimmed);
        continue;
      } else if (startsWithClose) {
        // Rule 1 close: dedent for the brace, and for an open case body if this
        // `}` closes the switch.
        const closesCaseBody = !!top && top.isSwitch && top.caseOpen;
        level = Math.max(0, blockLevel - 1 - (closesCaseBody ? 1 : 0));
      } else if (top && top.isSwitch && isCaseLabel) {
        // Rule 2: label at the switch's content level; dedent past a body that
        // is already open.
        level = Math.max(0, blockLevel - (top.caseOpen ? 1 : 0));
      } else if (CodeEditorComponent.GOTO_LABEL.test(trimmed)) {
        // Rule 4: a goto label sits one level out.
        level = Math.max(0, blockLevel - 1);
      } else {
        // Rule 1 statement + Rule 3 continuation.
        level = Math.max(0, blockLevel + (contDepth > 0 ? 1 : 0));
      }
      out.push(unit.repeat(level) + trimmed);

      // A case/default label opens a body level for the lines beneath it.
      if (top && top.isSwitch && isCaseLabel) {
        top.caseOpen = true;
      }

      // Walk the line to update block/continuation state for the lines below,
      // skipping braces/parens inside literals and comments. A `switch` keyword
      // on this line (or pending from a prior line) marks the next `{` as a
      // switch body.
      let switchMark: boolean =
        !inBlockComment && (/\bswitch\b/.test(trimmed) || pendingSwitch);
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
        if (ch === '{') {
          frames.push({ isSwitch: switchMark, caseOpen: false });
          switchMark = false; // only the first brace after `switch` is its body
        } else if (ch === '}') {
          frames.pop();
        } else if (ch === '(' || ch === '[') {
          contDepth++;
        } else if (ch === ')' || ch === ']') {
          contDepth = Math.max(0, contDepth - 1);
        }
      }
      // A `switch` seen with no `{` yet stays pending for a later-line brace.
      pendingSwitch = switchMark;
    }
    return out.join('\n');
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (this.editor && changes['placeholder']) {
      this.editor.setOption('placeholder', this.placeholder);
    }
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
