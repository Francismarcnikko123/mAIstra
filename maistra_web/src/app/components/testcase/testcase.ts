import { Component } from '@angular/core';
import { CodeEditorComponent } from '../code-editor/code-editor';
@Component({
  selector: 'app-testcase',
  standalone: true,
  imports: [CodeEditorComponent],
  templateUrl: './testcase.html',
  styleUrl: './testcase.css',
})
export class Testcase {}
