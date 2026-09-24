import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Brand, BrandListResponse, BrandWritePayload } from './brand.models';

@Injectable({ providedIn: 'root' })
export class BrandService {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = environment.apiBaseUrl;

  listBrands(): Observable<BrandListResponse> {
    return this.http.get<BrandListResponse>(`${this.apiBaseUrl}/brands`);
  }

  getBrand(id: string): Observable<Brand> {
    return this.http.get<Brand>(`${this.apiBaseUrl}/brands/${id}`);
  }

  createBrand(data: BrandWritePayload): Observable<Brand> {
    return this.http.post<Brand>(`${this.apiBaseUrl}/brands`, data);
  }

  updateBrand(id: string, data: BrandWritePayload): Observable<Brand> {
    return this.http.patch<Brand>(`${this.apiBaseUrl}/brands/${id}`, data);
  }

  deleteBrand(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiBaseUrl}/brands/${id}`);
  }
}
