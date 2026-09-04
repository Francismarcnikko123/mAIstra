import '@angular/compiler';
import { ElementRef, SimpleChange } from '@angular/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CodeEditorComponent } from './code-editor';

const aceHarness = vi.hoisted(() => {
  const state: {
    value: string;
    changeHandler?: (delta: unknown) => void;
    nextMarkerId: number;
  } = {
    value: '',
    nextMarkerId: 1,
  };

  const session = {
    setMode: vi.fn(),
    setUseWorker: vi.fn(),
    getLength: vi.fn(() => 3),
    getLine: vi.fn(() => ''),
    addMarker: vi.fn(() => state.nextMarkerId++),
    removeMarker: vi.fn(),
    addGutterDecoration: vi.fn(),
    removeGutterDecoration: vi.fn(),
    replace: vi.fn(),
  };

  const editor = {
    session,
    setTheme: vi.fn(),
    setOptions: vi.fn(),
    setValue: vi.fn((value: string) => {
      state.value = value;
      state.changeHandler?.({
        start: { row: 0 },
        end: { row: 0 },
        lines: [value],
      });
    }),
    getValue: vi.fn(() => state.value),
    on: vi.fn((event: string, handler: (delta: unknown) => void) => {
      if (event === 'change') state.changeHandler = handler;
    }),
    clearSelection: vi.fn(),
    destroy: vi.fn(),
    commands: { addCommand: vi.fn() },
  };

  return {
    state,
    session,
    editor,
    emitChange(delta: unknown, value = state.value) {
      state.value = value;
      state.changeHandler?.(delta);
    },
  };
});

vi.mock('ace-builds', () => ({
  edit: vi.fn(() => aceHarness.editor),
  require: vi.fn(() => ({
    Range: class Range {
      constructor(
        public startRow: number,
        public startColumn: number,
        public endRow: number,
        public endColumn: number,
      ) {}
    },
  })),
}));
vi.mock('ace-builds/src-noconflict/mode-c_cpp', () => ({}));
vi.mock('ace-builds/src-noconflict/theme-monokai', () => ({}));

describe('CodeEditorComponent OCR review markers', () => {
  beforeEach(() => {
    aceHarness.state.value = '';
    aceHarness.state.changeHandler = undefined;
    aceHarness.state.nextMarkerId = 1;
    for (const mock of [
      ...Object.values(aceHarness.session),
      ...Object.values(aceHarness.editor),
    ]) {
      if (typeof mock === 'function' && 'mockClear' in mock) {
        (mock as ReturnType<typeof vi.fn>).mockClear();
      }
    }
    aceHarness.session.getLength.mockReturnValue(3);
    aceHarness.session.getLine.mockReturnValue('');
    aceHarness.session.addMarker.mockImplementation(
      () => aceHarness.state.nextMarkerId++,
    );
    aceHarness.editor.getValue.mockImplementation(() => aceHarness.state.value);
    aceHarness.editor.setValue.mockImplementation((value: string) => {
      aceHarness.state.value = value;
      aceHarness.state.changeHandler?.({
        start: { row: 0 },
        end: { row: 0 },
        lines: [value],
      });
    });
    aceHarness.editor.on.mockImplementation(
      (event: string, handler: (delta: unknown) => void) => {
        if (event === 'change') aceHarness.state.changeHandler = handler;
      },
    );
  });

  function createComponent() {
    const component = new CodeEditorComponent();
    component.host = {
      nativeElement: {} as HTMLElement,
    } as ElementRef<HTMLElement>;
    return component;
  }

  it('renders one violet marker for each normalized flag', () => {
    const component = createComponent();
    component.value = '3\nprinte();\nreturn 0;';
    component.lineReviewFlags = [
      {
        line: 1,
        strength: 'strong',
        primarySource: 'anomaly',
        reasons: ['lone token'],
      },
      {
        line: 2,
        strength: 'soft',
        primarySource: 'suggestion',
        reasons: ['possible spelling mismatch'],
      },
    ];

    component.ngAfterViewInit();

    expect(aceHarness.session.addMarker).toHaveBeenCalledTimes(2);
    expect(aceHarness.session.addGutterDecoration).toHaveBeenCalledWith(
      0,
      'ocr-review-strong-gutter',
    );
    expect(aceHarness.session.addGutterDecoration).toHaveBeenCalledWith(
      1,
      'ocr-review-soft-gutter',
    );
  });

  it('reports an inline teacher edit using one-based lines', () => {
    const component = createComponent();
    component.value = 'a();\nb();';
    component.lineReviewFlags = [
      {
        line: 2,
        strength: 'soft',
        primarySource: 'confidence-low',
        reasons: ['low confidence'],
      },
    ];
    component.ngAfterViewInit();
    const editSpy = vi.spyOn(component.reviewEvidenceEdited, 'emit');

    aceHarness.emitChange(
      { start: { row: 1 }, end: { row: 1 }, lines: ['x'] },
      'a();\nbx();',
    );

    expect(editSpy).toHaveBeenCalledWith({
      startLine: 2,
      endLine: 2,
      lineStructureChanged: false,
    });
    expect(aceHarness.session.removeMarker).toHaveBeenCalled();
  });

  it('invalidates all row mappings when an edit crosses lines', () => {
    const component = createComponent();
    component.value = 'a();\nb();';
    component.lineReviewFlags = [
      {
        line: 1,
        strength: 'soft',
        primarySource: 'confidence-low',
        reasons: ['low confidence'],
      },
      {
        line: 2,
        strength: 'soft',
        primarySource: 'suggestion',
        reasons: ['possible spelling mismatch'],
      },
    ];
    component.ngAfterViewInit();
    const editSpy = vi.spyOn(component.reviewEvidenceEdited, 'emit');

    aceHarness.emitChange(
      { start: { row: 0 }, end: { row: 1 }, lines: ['a();', ''] },
      'a();\n\nb();',
    );

    expect(editSpy).toHaveBeenCalledWith({
      startLine: 1,
      endLine: 2,
      lineStructureChanged: true,
    });
    expect(aceHarness.session.removeMarker).toHaveBeenCalledTimes(2);
  });

  it('does not report an externally supplied value as a teacher edit', () => {
    const component = createComponent();
    component.value = 'old';
    component.ngAfterViewInit();
    const editSpy = vi.spyOn(component.reviewEvidenceEdited, 'emit');

    component.value = 'fresh OCR text';
    component.ngOnChanges({
      value: new SimpleChange('old', 'fresh OCR text', false),
    });

    expect(editSpy).not.toHaveBeenCalled();
  });
});
