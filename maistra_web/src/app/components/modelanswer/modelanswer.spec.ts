import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Component } from '@angular/core';

import { Modelanswer } from './modelanswer';
import { Judge0 } from '../judge0/judge0';

@Component({
  selector: 'app-judge0',
  standalone: true,
  template: '<div data-testid="judge0-stub"></div>',
})
class Judge0Stub {}

describe('Modelanswer', () => {
  let component: Modelanswer;
  let fixture: ComponentFixture<Modelanswer>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Modelanswer],
    })
      .overrideComponent(Modelanswer, {
        remove: { imports: [Judge0] },
        add: { imports: [Judge0Stub] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(Modelanswer);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('renders the Judge0 runner', () => {
    const judge0 = fixture.nativeElement.querySelector(
      '[data-testid="judge0-stub"]',
    );

    expect(judge0).toBeTruthy();
  });
});
