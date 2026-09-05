import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SubmissionsListComponent } from './components/submissions-list/submissions-list';
import { QuestionFormComponent } from './components/question-form/question-form';
import { QuestionBankComponent } from './components/question-bank/question-bank';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, SubmissionsListComponent, QuestionFormComponent, QuestionBankComponent],
  templateUrl: './app.html',
})
export class App {
  activeTab: 'submissions' | 'bank' | 'create' = 'submissions';
  sidebarOpen = false;

  setTab(tab: 'submissions' | 'bank' | 'create') {
    this.activeTab = tab;
    this.sidebarOpen = false;
  }

  toggleSidebar() {
    this.sidebarOpen = !this.sidebarOpen;
  }

  closeSidebar() {
    this.sidebarOpen = false;
  }
}
