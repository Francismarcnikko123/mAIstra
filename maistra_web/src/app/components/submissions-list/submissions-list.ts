import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { SupabaseService } from '../../services/supabase';

interface Submission {
  id: string;
  image_url: string;
  student_name?: string;
  captured_at: string;
  status?: string;
  text_content?: string;
  topic?: string;
}

interface TopicGroup {
  topic: string;
  submissions: Submission[];
}

@Component({
  selector: 'app-submissions-list',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './submissions-list.html',
  styleUrl: './submissions-list.css'
})
export class SubmissionsListComponent implements OnInit, OnDestroy {
  submissions: Submission[] = [];
  groupedSubmissions: TopicGroup[] = [];
  collapsedFolders: Record<string, boolean> = {};

  // Modal state
  selectedSubmission: Submission | null = null;
  editableTopic: string = '';
  savingTopic = false;

  // OCR state
  extractingId: string | null = null;
  savingId: string | null = null;
  extractedText: Record<string, string> = {};
  editableText: Record<string, string> = {};

  private subscription: any;

  constructor(
    private supabase: SupabaseService,
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  async ngOnInit() {
    await this.loadSubmissions();

    this.subscription = this.supabase.subscribeToSubmissions((payload: any) => {
      this.loadSubmissions();
    });
  }

  ngOnDestroy() {
    if (this.subscription) {
      this.subscription.unsubscribe();
    }
  }

  async loadSubmissions() {
    const { data, error } = await this.supabase.getSubmissions();
    if (error) { console.error(error); return; }
    this.submissions = (data ?? []) as Submission[];
    this.groupSubmissions();
    this.cdr.detectChanges();
  }

  groupSubmissions() {
    const map = new Map<string, Submission[]>();
    for (const s of this.submissions) {
      const topic = s.topic?.trim() || 'Uncategorized';
      if (!map.has(topic)) map.set(topic, []);
      map.get(topic)!.push(s);
    }

    this.groupedSubmissions = Array.from(map.entries())
      .sort(([a], [b]) => {
        if (a === 'Uncategorized') return 1;
        if (b === 'Uncategorized') return -1;
        return a.localeCompare(b);
      })
      .map(([topic, submissions]) => ({ topic, submissions }));
  }

  toggleFolder(topic: string) {
    this.collapsedFolders[topic] = !this.collapsedFolders[topic];
  }

  openModal(submission: Submission) {
    this.selectedSubmission = { ...submission };
    this.editableTopic = submission.topic || 'Uncategorized';
    if (submission.text_content && !this.editableText[submission.id]) {
      this.editableText[submission.id] = submission.text_content;
    }
  }

  closeModal() {
    this.selectedSubmission = null;
  }

  async saveTopic() {
    if (!this.selectedSubmission) return;
    this.savingTopic = true;
    try {
      await this.supabase.updateSubmissionTopic(this.selectedSubmission.id, this.editableTopic);
      const s = this.submissions.find(x => x.id === this.selectedSubmission!.id);
      if (s) s.topic = this.editableTopic;
      this.selectedSubmission.topic = this.editableTopic;
      this.groupSubmissions();
      this.cdr.detectChanges();
    } catch (err) {
      console.error('Failed to save topic:', err);
    } finally {
      this.savingTopic = false;
    }
  }

  async extractText() {
    if (!this.selectedSubmission) return;
    const id = this.selectedSubmission.id;
    this.extractingId = id;
    try {
      const res: any = await this.http
        .post('http://localhost:8000/api/ocr/extract-from-url', {
          image_url: this.selectedSubmission.image_url,
          submission_id: id
        })
        .toPromise();
      const text = res?.cleaned_text ?? '';
      this.extractedText[id] = text;
      this.editableText[id] = text;
    } catch (err) {
      console.error('OCR failed:', err);
      this.extractedText[id] = 'Error extracting text.';
      this.editableText[id] = 'Error extracting text.';
    } finally {
      this.extractingId = null;
      this.cdr.detectChanges();
    }
  }

  async saveVerifiedText() {
    if (!this.selectedSubmission) return;
    const id = this.selectedSubmission.id;
    this.savingId = id;
    try {
      const text = this.editableText[id];
      await this.supabase.updateSubmissionText(id, text, text);
      const s = this.submissions.find(x => x.id === id);
      if (s) s.text_content = text;
      if (this.selectedSubmission) this.selectedSubmission.text_content = text;
    } catch (err) {
      console.error('Save failed:', err);
    } finally {
      this.savingId = null;
      this.cdr.detectChanges();
    }
  }

  hasExtractedText(id: string): boolean {
    return !!this.editableText[id];
  }

  isExtracting(id: string): boolean {
    return this.extractingId === id;
  }

  isSaving(id: string): boolean {
    return this.savingId === id;
  }
}