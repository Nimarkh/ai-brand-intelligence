import { Injectable, inject, signal } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { ActivatedRouteSnapshot, Data, NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class PageContextService {
  private readonly router = inject(Router);
  private readonly documentTitle = inject(Title);
  private readonly titleState = signal('AI Brand Intelligence');
  private readonly sectionState = signal('');

  readonly title = this.titleState.asReadonly();
  readonly section = this.sectionState.asReadonly();

  constructor() {
    this.sync();
    this.router.events
      .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
      .subscribe(() => this.sync());
  }

  private sync(): void {
    let current: ActivatedRouteSnapshot | null = this.router.routerState.snapshot?.root ?? null;
    let title = '';
    let section = '';

    while (current) {
      title = this.readString(current.data, 'title') ?? title;
      section = this.readString(current.data, 'section') ?? section;
      current = current.firstChild;
    }

    const pageTitle = title || 'AI Brand Intelligence';
    this.titleState.set(pageTitle);
    this.sectionState.set(title ? section : '');
    this.documentTitle.setTitle(
      pageTitle === 'AI Brand Intelligence' ? pageTitle : `${pageTitle} · AI Brand Intelligence`,
    );
  }

  private readString(data: Data, key: string): string | null {
    const value: unknown = data[key];
    return typeof value === 'string' && value.length > 0 ? value : null;
  }
}
