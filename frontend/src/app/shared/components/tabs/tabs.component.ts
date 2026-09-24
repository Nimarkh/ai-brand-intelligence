import { Component, ElementRef, input, model, viewChildren } from '@angular/core';

export interface TabItem {
  id: string;
  label: string;
}

@Component({
  selector: 'app-tabs',
  template: `
    <div class="tabs" role="tablist" [attr.aria-label]="label()">
      @for (tab of tabs(); track tab.id; let index = $index) {
        <button
          #tabButton
          type="button"
          class="tabs__tab"
          role="tab"
          [id]="'tab-' + tab.id"
          [attr.aria-selected]="tab.id === activeId()"
          [attr.aria-controls]="'panel-' + tab.id"
          [attr.tabindex]="tab.id === activeId() ? 0 : -1"
          (click)="select(tab.id)"
          (keydown)="onKeydown($event, index)"
        >
          {{ tab.label }}
        </button>
      }
    </div>
  `,
})
export class TabsComponent {
  readonly tabs = input.required<readonly TabItem[]>();
  readonly label = input('Sections');
  readonly activeId = model('');

  private readonly tabButtons = viewChildren<ElementRef<HTMLButtonElement>>('tabButton');

  select(id: string): void {
    this.activeId.set(id);
  }

  onKeydown(event: KeyboardEvent, index: number): void {
    const items = this.tabs();
    let nextIndex = index;

    switch (event.key) {
      case 'ArrowRight':
        nextIndex = (index + 1) % items.length;
        break;
      case 'ArrowLeft':
        nextIndex = (index - 1 + items.length) % items.length;
        break;
      case 'Home':
        nextIndex = 0;
        break;
      case 'End':
        nextIndex = items.length - 1;
        break;
      default:
        return;
    }

    event.preventDefault();
    const next = items[nextIndex];
    if (!next) {
      return;
    }
    this.activeId.set(next.id);
    queueMicrotask(() => this.tabButtons()[nextIndex]?.nativeElement.focus());
  }
}
