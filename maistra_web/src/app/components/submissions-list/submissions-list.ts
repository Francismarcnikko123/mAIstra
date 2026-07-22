import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SupabaseService } from '../../services/supabase';

interface Submission {
  id: string;
  image_url: string;
  student_name: string;
  captured_at: string;
  status: string;
}

@Component({
  selector: 'app-submissions-list',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './submissions-list.html',
})
export class SubmissionsListComponent implements OnInit, OnDestroy {
  submissions: Submission[] = [];
  isLoading = true;
  private subscription: any;

  constructor(private supabase: SupabaseService, private cdr: ChangeDetectorRef) {}

  async ngOnInit() {
    await this.loadSubmissions();
    this.subscribeToRealtime();
  }

  async loadSubmissions() {
    this.isLoading = true;
    const { data, error } = await this.supabase.getSubmissions();
    if (data) this.submissions = data;
    this.isLoading = false;
    this.cdr.detectChanges();
  }

  subscribeToRealtime() {
    this.subscription = this.supabase
      .subscribeToSubmissions((payload: any) => {
        this.submissions.unshift(payload.new);
        this.cdr.detectChanges();
      });
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