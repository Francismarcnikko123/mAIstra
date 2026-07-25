import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SupabaseService } from '../../services/supabase';
import { FormsModule } from '@angular/forms';
import { CodeEditorComponent } from '../code-editor/code-editor';


interface Submission {
  id: string;
  image_url: string;
  student_name: string;
  captured_at: string;
  status: string;
  extracted_text?: string;
  verified_text?: string;
}

@Component({
  selector: 'app-submissions-list',
  standalone: true,
  imports: [CommonModule, FormsModule, CodeEditorComponent],
  templateUrl: './submissions-list.html',
  styleUrls: ['./submissions-list.css'],
})
export class SubmissionsListComponent implements OnInit, OnDestroy {
  submissions: Submission[] = [];
  isLoading = true;
  private subscription: any; 

  extractingId: string | null = null;
  savingId: string | null = null;

  editableText: { [submissionId: string]: string } = {};
  rawExtractedText: { [submissionId: string]: string } = {};

  constructor(private supabase: SupabaseService, private cdr: ChangeDetectorRef) {}

  async ngOnInit() {
    await this.loadSubmissions();
    this.subscribeToRealtime();
  }

  async loadSubmissions() {
    this.isLoading = true;
    const { data, error } = await this.supabase.getSubmissions();

    if (error){
      console.error(error);
    }

    if (data) {
       this.submissions = data;

       this.submissions.forEach((s) => {
        this.editableText[s.id] = s.verified_text || s.extracted_text || '';
        this.rawExtractedText[s.id] = s.extracted_text || '';
      });
    }

    this.isLoading = false;
    this.cdr.detectChanges();
  }

  subscribeToRealtime() {
    this.subscription = this.supabase
      .subscribeToSubmissions((payload: any) => {
        this.submissions.unshift(payload.new);

       this.editableText[payload.new.id] =
          payload.new.verified_text || payload.new.extracted_text || '';

        this.rawExtractedText[payload.new.id] =
          payload.new.extracted_text || '';

        this.cdr.detectChanges();
      });
  }

async extractText(submission: Submission) {
    try {
      this.extractingId = submission.id;
      this.cdr.detectChanges();

      const response = await fetch('http://localhost:8000/api/ocr/extract-from-url', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
       body: JSON.stringify({
        submission_id: submission.id,
        image_url: submission.image_url,
        }),
      });

      if (!response.ok) {
        throw new Error('OCR extraction failed.');
      }

      const result = await response.json();

      this.rawExtractedText[submission.id] = result.raw_text || '';
      this.editableText[submission.id] =
        result.cleaned_text || result.raw_text || '';

    } catch (error) {
      console.error(error);
      alert('Failed to extract text. Make sure the FastAPI OCR backend is running.');
    } finally {
      this.extractingId = null;
      this.cdr.detectChanges();
    }
  }


async saveVerifiedText(submission: Submission) {
    try {
      this.savingId = submission.id;
      this.cdr.detectChanges();

      const { error } = await this.supabase.updateSubmissionText(
        submission.id,
        this.rawExtractedText[submission.id],
        this.editableText[submission.id]
      );

      if (error) {
        throw error;
      }

      submission.status = 'verified';
      submission.extracted_text = this.rawExtractedText[submission.id];
      submission.verified_text = this.editableText[submission.id];

      alert('Verified text saved successfully.');

    } catch (error) {
      console.error(error);
      alert('Failed to save verified text.');
    } finally {
      this.savingId = null;
      this.cdr.detectChanges();
    }
  }

  ngOnDestroy() {
    if (this.subscription) this.subscription.unsubscribe();
  }

  formatDate(date: string) {
    return new Date(date).toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit', hour12: true
    });
  }
}