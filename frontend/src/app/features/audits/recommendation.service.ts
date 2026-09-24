import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  RecommendationListResponse,
  RecommendationRunResponse,
} from './recommendation.models';

@Injectable({ providedIn: 'root' })
export class RecommendationService {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = environment.apiBaseUrl;

  calculateRecommendations(auditId: string): Observable<RecommendationRunResponse> {
    return this.http.post<RecommendationRunResponse>(
      `${this.apiBaseUrl}/audits/${auditId}/calculate-recommendations`,
      {},
    );
  }

  getRecommendations(auditId: string): Observable<RecommendationListResponse> {
    return this.http.get<RecommendationListResponse>(
      `${this.apiBaseUrl}/audits/${auditId}/recommendations`,
    );
  }
}
