import { Component } from '@angular/core';
import { NgIf } from '@angular/common';
import { SubmissionsListComponent } from './components/submissions-list/submissions-list';
import { QuestionFormComponent } from './components/question-form/question-form';
import { QuestionBankComponent } from './components/question-bank/question-bank';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [NgIf, SubmissionsListComponent, QuestionFormComponent, QuestionBankComponent],
  templateUrl: './app.html',
  styles: `
    :host {
      display: block;
      min-height: 100vh;
      background: #f0f0f0;
    }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      align-items: center;
      gap: 24px;
      padding: 8px 24px;
      background: #f8f8f8;
      border-bottom: 1px solid #e5e7eb;
    }
    .brand {
      color: #b71c1c;
      font-size: 20px;
      font-weight: 700;
    }
    .topnav {
      display: flex;
      gap: 8px;
    }
    .topnav button {
      min-height: 44px;
      padding: 8px 16px;
      border: 1px solid transparent;
      border-radius: 8px;
      background: none;
      color: #6b7280;
      font: inherit;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
    }
    .topnav button:hover {
      color: #1a1a1a;
    }
    .topnav button.active {
      border-color: #1a1a1a;
      background: white;
      color: #1a1a1a;
    }
    .page {
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
      box-sizing: border-box;
    }
    .back-link {
      min-height: 40px;
      margin-bottom: 8px;
      padding: 8px 0;
      border: none;
      background: none;
      color: #2563eb;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
    }
    @media (max-width: 640px) {
      .topbar {
        gap: 8px;
        padding: 8px 16px;
      }
      .page {
        padding: 16px;
      }
    }
  `,
})
export class App {
  /** Which page is showing. Create opens from the bank's button. */
  page: 'bank' | 'submissions' | 'create' = 'submissions';
}