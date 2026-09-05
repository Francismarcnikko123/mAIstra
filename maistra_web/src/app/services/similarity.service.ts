import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { similarityApiUrl } from './similarity-api.config';

export type SimilarityState =
  | 'missing_metadata'
  | 'not_checked'
  | 'checking'
  | 'complete'
  | 'outdated'
  | 'unavailable';
export type SimilarityMatchType =
  'exact_duplicate' | 'normalized_duplicate' | 'similar_code';
export interface SourcePoint {
  row: number;
  column: number;
}
export interface SourceRange {
  start: SourcePoint;
  end: SourcePoint;
}
export interface SimilarityMatch {
  peer_submission_id: string;
  peer_student_name: string | null;
  peer_block_section_name: string | null;
  match_type: SimilarityMatchType;
  matched_token_count: number;
  submission_coverage: number;
  peer_coverage: number;
}
export interface SimilaritySummary {
  status: SimilarityState;
  submission_id: string;
  scan_id?: string;
  eligible_submission_count?: number;
  compared_pair_count?: number;
  skipped_pair_count?: number;
  skipped_reasons?: Record<string, number>;
  error?: string;
  matches?: SimilarityMatch[];
}
export interface SimilarityDetail {
  scan_id: string;
  submission_id: string;
  peer_submission_id: string;
  match_type: SimilarityMatchType;
  submission_code: string;
  peer_code: string;
  submission_ranges: SourceRange[];
  peer_ranges: SourceRange[];
}

@Injectable({ providedIn: 'root' })
export class SimilarityService {
  constructor(private http: HttpClient) {}
  scanSubmission(id: string) {
    return this.http.post<SimilaritySummary>(
      `${similarityApiUrl}/submissions/${encodeURIComponent(id)}/scan`,
      {},
    );
  }
  getSubmissionSimilarity(id: string) {
    return this.http.get<SimilaritySummary>(
      `${similarityApiUrl}/submissions/${encodeURIComponent(id)}`,
    );
  }
  getMatchDetail(id: string, peerId: string) {
    return this.http.get<SimilarityDetail>(
      `${similarityApiUrl}/submissions/${encodeURIComponent(id)}/matches/${encodeURIComponent(peerId)}`,
    );
  }
}
