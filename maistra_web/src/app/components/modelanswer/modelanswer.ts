import { Component } from '@angular/core';
import { CodeEditorComponent} from '../code-editor/code-editor';
import { Judge0 } from '../judge0/judge0';
@Component({
  selector: 'app-modelanswer',
  standalone: true,
  imports: [Judge0,],
  templateUrl: './modelanswer.html',
  styleUrl: './modelanswer.css',
})
export class Modelanswer {}
