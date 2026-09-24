import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ScoreComponent, formatScore } from './score.component';

describe('formatScore', () => {
  it('formats stored decimals without inventing extra precision', () => {
    expect(formatScore(78.4)).toBe('78.4 / 100');
    expect(formatScore(78)).toBe('78 / 100');
    expect(formatScore(60.5)).toBe('60.5 / 100');
    expect(formatScore(0)).toBe('0 / 100');
    expect(formatScore(null)).toBe('—');
  });
});

describe('ScoreComponent', () => {
  let fixture: ComponentFixture<ScoreComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ScoreComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(ScoreComponent);
  });

  it('shows a formatted score when a value exists', () => {
    fixture.componentRef.setInput('value', 78.4);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('78.4 / 100');
    expect(fixture.nativeElement.querySelector('.score__loading')).toBeNull();
  });

  it('shows the empty label when the score is null', () => {
    fixture.componentRef.setInput('value', null);
    fixture.componentRef.setInput('emptyLabel', 'Score unavailable');
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Score unavailable');
    expect(fixture.nativeElement.textContent).not.toContain('/ 100');
  });

  it('shows a loading placeholder without a number', () => {
    fixture.componentRef.setInput('loading', true);
    fixture.componentRef.setInput('value', 82);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.score__loading')).not.toBeNull();
    expect(fixture.nativeElement.textContent).not.toContain('82');
  });
});
