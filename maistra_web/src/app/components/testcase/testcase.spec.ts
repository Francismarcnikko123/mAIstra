import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Component } from '@angular/core';

import { Testcase } from './testcase';
import { CodeEditorComponent } from '../code-editor/code-editor';

@Component({
  selector: 'app-code-editor',
  standalone: true,
  template: '<div data-testid="code-editor-stub"></div>',
})
class CodeEditorStub {}

describe('Testcase', () => {
  let component: Testcase;
  let fixture: ComponentFixture<Testcase>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Testcase],
    })
      .overrideComponent(Testcase, {
        remove: { imports: [CodeEditorComponent] },
        add: { imports: [CodeEditorStub] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(Testcase);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('renders the code editor', () => {
    const codeEditor = fixture.nativeElement.querySelector(
      '[data-testid="code-editor-stub"]',
    );

    expect(codeEditor).toBeTruthy();
  });
});
