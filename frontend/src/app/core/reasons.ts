import { ApiError } from './api';
import { Key } from './lang.fr';
import { Translate } from './i18n';

const CODES = new Set<string>([
  'confirmation_required',
  'full_backup_confirmation_required',
  'invalid_request',
  'wrong_state',
  'pelican_rejected',
  'pelican_denied',
  'pelican_not_found',
  'pelican_unavailable',
  'pelican_timeout',
  'busy',
  'forbidden',
  'backup_not_ready',
]);

/** The sentence for an error of the add-on (reasons first, then the status). */
export function failure(err: unknown, t: Translate): string {
  if (!(err instanceof ApiError)) return t('err.unexpected');
  if (err.status === 429) {
    return err.wait === undefined
      ? t('err.too_fast_unknown')
      : t('err.too_fast', { wait: err.wait });
  }
  if (err.detail && CODES.has(err.detail)) return t(`err.${err.detail}` as Key);
  if (err.status === 401 || err.status === 503 || err.status === 502) return t(`err.${err.status}`);
  return t('err.unexpected_code', { code: err.status });
}
