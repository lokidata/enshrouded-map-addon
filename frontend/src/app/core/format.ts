import { Translate } from './i18n';

export const fmtSize = (n: number, t: Translate): string =>
  n >= 2 ** 30
    ? `${(n / 2 ** 30).toFixed(2)} ${t('unit.gb')}`
    : `${(n / 2 ** 20).toFixed(1)} ${t('unit.mb')}`;

export const fmtGo = (n: number, t: Translate): string =>
  `${(n / 2 ** 30).toFixed(2)} ${t('unit.gb')}`;

export function fmtUptime(ms: number, t: Translate): string {
  const m = Math.floor(ms / 60000);
  return `${Math.floor(m / 1440)} ${t('unit.d')} ${Math.floor((m % 1440) / 60)} ${t('unit.h')} ${m % 60} ${t('unit.min')}`;
}

export const fmtDate = (iso: string, locale: string): string =>
  new Date(iso).toLocaleString(locale);
