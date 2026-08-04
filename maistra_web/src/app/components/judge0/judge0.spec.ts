import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Judge0 } from './judge0';

describe('Judge0', () => {
  let component: Judge0;
  let fixture: ComponentFixture<Judge0>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Judge0],
    }).compileComponents();

    fixture = TestBed.createComponent(Judge0);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
