import { Injectable, Pipe, PipeTransform, computed, inject, signal } from '@angular/core';
import { de } from './lang.de';
import { en } from './lang.en';
import { fr, Key } from './lang.fr';

export type Lang = 'fr' | 'en' | 'de';
export type Params = Record<string, string | number>;
/** A translator, for the plain functions that build a sentence. */
export type Translate = (key: Key, params?: Params) => string;

const LOCALES: Record<Lang, string> = { fr: 'fr-FR', en: 'en-GB', de: 'de-DE' };
const TEXTS: Record<Lang, Record<Key, string>> = { fr, en, de };

/** FR/EN/DE texts. The language comes from the site, through the `lang` attribute of the element. */
@Injectable({ providedIn: 'root' })
export class I18n {
  readonly lang = signal<Lang>('fr');
  readonly locale = computed(() => LOCALES[this.lang()]);

  /** `fr` and `de` are the site's other languages; any other code falls back to English. */
  setLang(code: string): void {
    this.lang.set(code === 'fr' || code === 'de' ? code : 'en');
  }

  readonly t: Translate = (key, params) => {
    const text = TEXTS[this.lang()][key];
    return params ? text.replace(/\{(\w+)\}/g, (m, p: string) => String(params[p] ?? m)) : text;
  };
}

/** `{{ 'key' | t }}` or `{{ 'key' | t: { n: 3 } }}`. Impure: it must follow the language signal. */
@Pipe({ name: 't', pure: false })
export class T implements PipeTransform {
  private readonly i18n = inject(I18n);
  transform(key: Key, params?: Params): string {
    return this.i18n.t(key, params);
  }
}
