import { Component } from '@angular/core';
import { SubmissionsListComponent } from './components/submissions-list/submissions-list';
import { QuestionFormComponent } from './components/question-form/question-form';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [SubmissionsListComponent, QuestionFormComponent],
  templateUrl: './app.html',
})
export class App {}