// Test-only loopback adapter for actual host-browser APIs. Production Workday
// HTTPS/tenant guards remain unchanged in local_credentials.mjs.
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { loadCredentials } from '../skills/career-assistant/scripts/local_credentials.mjs';

export function createMockHostLoginSession(workspace, expectedOrigin) {
  const url = new URL(expectedOrigin);
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || url.username || url.password || expectedOrigin !== url.origin) {
    throw new Error('Host fixture must use an exact loopback origin; values omitted.');
  }
  let outcome = 'new';
  const used = new Set();
  return {
    async fill(tab, index, usernameSelector, passwordSelector) {
      try {
        if (!['new', 'rejected'].includes(outcome) || used.has(index) || index !== 0) throw new Error();
        const fixture = JSON.parse(await readFile(path.join(workspace, '.career-assistant/host-browser-fixture.json'), 'utf8'));
        if (fixture.fictional_test !== true || !path.basename(workspace).startsWith('host-browser-')) throw new Error();
        if (new URL(await tab.url()).origin !== expectedOrigin) throw new Error();
        const username = tab.playwright.locator(usernameSelector);
        const password = tab.playwright.locator(passwordSelector);
        if (usernameSelector === passwordSelector || await username.count() !== 1 || await password.count() !== 1 || await password.getAttribute('type') !== 'password') throw new Error();
        used.add(index); outcome = 'pending';
        const pairs = await loadCredentials(workspace);
        if (pairs.length !== 1 || pairs[0].username !== 'fixture@example.invalid') throw new Error();
        await username.fill(pairs[index].username);
        if (new URL(await tab.url()).origin !== expectedOrigin) throw new Error();
        await password.fill(pairs[index].password);
        return {filled: true, values_omitted: true, scope: 'Fictional loopback fixture only'};
      } catch {
        outcome = 'stopped';
        throw new Error('Host fixture login stopped; values omitted.');
      }
    },
    observe(result) {
      if (outcome !== 'pending' || !['success', 'rejected', 'captcha', '2fa', 'unknown'].includes(result)) {
        throw new Error('Invalid host fixture login observation; values omitted.');
      }
      outcome = result === 'rejected' ? 'rejected' : 'stopped';
      return {attempts: used.size, stopped: outcome === 'stopped', values_omitted: true};
    }
  };
}
