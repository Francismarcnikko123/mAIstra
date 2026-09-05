import { HttpClient } from '@angular/common/http';
import { describe, expect, it, vi } from 'vitest';
import { similarityApiUrl } from './similarity-api.config';
import { SimilarityService } from './similarity.service';

describe('SimilarityService', () => {
  it('sends only submission IDs to the configured scoped endpoints', () => {
    const post = vi.fn();
    const get = vi.fn();
    const service = new SimilarityService({
      post,
      get,
    } as unknown as HttpClient);
    const base = similarityApiUrl;
    service.scanSubmission('answer-1');
    service.getSubmissionSimilarity('answer-1');
    service.getMatchDetail('answer-1', 'answer-2');
    expect(post).toHaveBeenCalledWith(`${base}/submissions/answer-1/scan`, {});
    expect(get).toHaveBeenCalledWith(`${base}/submissions/answer-1`);
    expect(get).toHaveBeenCalledWith(
      `${base}/submissions/answer-1/matches/answer-2`,
    );
  });
});
