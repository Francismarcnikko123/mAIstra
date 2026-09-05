import {
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  SimilarityDetail,
  SimilarityMatchType,
  SimilarityState,
  SimilaritySummary,
} from '../../services/similarity.service';
import { highlightSource, SourceLine } from './similarity-highlight';

@Component({
  selector: 'app-similarity-panel',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './similarity-panel.html',
  styleUrl: './similarity-panel.css',
})
export class SimilarityPanelComponent implements OnChanges {
  @Input() state: SimilarityState = 'not_checked';
  @Input() summary?: SimilaritySummary;
  @Input() selectedPeer = '';
  @Input() detail?: SimilarityDetail;
  @Input() detailLoading = false;
  @Input() detailError = '';
  @Input() studentName = 'Current student';
  @Input() sectionName = '';
  @Input() imageUrl = '';
  @Input() hasUnsavedCode = false;
  @Output() retry = new EventEmitter<void>();
  @Output() inspect = new EventEmitter<string>();
  leftLines: SourceLine[] = [];
  rightLines: SourceLine[] = [];

  ngOnChanges() {
    this.leftLines = this.detail
      ? highlightSource(
          this.detail.submission_code,
          this.detail.submission_ranges,
        )
      : [];
    this.rightLines = this.detail
      ? highlightSource(this.detail.peer_code, this.detail.peer_ranges)
      : [];
  }

  matchLabel(type: SimilarityMatchType): string {
    return {
      exact_duplicate: 'Exact duplicate',
      normalized_duplicate: 'Same tokens',
      similar_code: 'Similar code',
    }[type];
  }

  get message(): string {
    if (this.state === 'complete') {
      if ((this.summary?.eligible_submission_count ?? 0) < 2)
        return 'No other eligible saved answers yet. Check again after another student’s answer is verified.';
      if (!this.summary?.matches?.length)
        return 'No significant matches found in the completed comparisons for this answer.';
      return 'Matching passages are available for optional review.';
    }
    return {
      missing_metadata:
        'Complete and save the assessment, question, student and block section in Details.',
      not_checked:
        'No check yet. Compare saved answers to this question across the assessment’s block sections.',
      checking:
        'Checking saved answers. You can keep grading while the check runs.',
      outdated: this.hasUnsavedCode
        ? 'Code has changed. Save it in Review code before checking again.'
        : 'Saved answers or comparison details have changed. Run a new check for current evidence.',
      unavailable:
        'Similarity is unavailable. You can keep grading and retry later.',
    }[this.state];
  }
}
