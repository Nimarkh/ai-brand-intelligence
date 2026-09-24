import { Component, ElementRef, effect, input, output, viewChild } from '@angular/core';

import { IconComponent } from '../icon/icon.component';

@Component({
  selector: 'app-modal',
  imports: [IconComponent],
  template: `
    <dialog
      #dialog
      class="modal"
      aria-modal="true"
      [attr.aria-labelledby]="titleId"
      (close)="onDialogClose()"
      (click)="onBackdrop($event)"
    >
      <div class="modal__header">
        <h2 [id]="titleId">{{ title() }}</h2>
        <button type="button" class="icon-btn" aria-label="Close dialog" (click)="requestClose()">
          <app-icon name="close" [size]="18" />
        </button>
      </div>
      <div class="modal__body">
        <ng-content />
      </div>
      <div class="modal__actions">
        <ng-content select="[modalActions]" />
      </div>
    </dialog>
  `,
})
export class ModalComponent {
  readonly title = input.required<string>();
  readonly open = input(false);
  readonly openChange = output<boolean>();

  readonly titleId = `modal-title-${Math.random().toString(36).slice(2, 8)}`;

  private readonly dialogRef = viewChild<ElementRef<HTMLDialogElement>>('dialog');

  constructor() {
    effect(() => {
      const isOpen = this.open();
      const dialog = this.dialogRef()?.nativeElement;
      if (!dialog) {
        return;
      }
      if (isOpen && !dialog.open) {
        dialog.showModal();
      } else if (!isOpen && dialog.open) {
        dialog.close();
      }
    });
  }

  requestClose(): void {
    this.openChange.emit(false);
  }

  onDialogClose(): void {
    if (this.open()) {
      this.openChange.emit(false);
    }
  }

  onBackdrop(event: MouseEvent): void {
    if (event.target === this.dialogRef()?.nativeElement) {
      this.requestClose();
    }
  }
}
