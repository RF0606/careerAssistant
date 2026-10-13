import { readFile, realpath } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

export function parseCredentials(text) {
  const pairs = [];
  for (const [index, line] of text.replace(/^\uFEFF/, '').split(/\r?\n/).entries()) {
    if (!line.trim()) continue;
    const match = /^\s*username\s*[:：]\s*(.*?)\s*[,，]\s*password\s*[:：]\s*(.+?)\s*$/i.exec(line);
    if (!match || !match[1] || /[\x00-\x1F\x7F]/.test(match[1] + match[2])) {
      throw new Error(`Invalid credential line ${index + 1}; values omitted`);
    }
    if (!pairs.some(p => p.username === match[1] && p.password === match[2])) {
      pairs.push({ username: match[1], password: match[2] });
    }
  }
  if (!pairs.length) throw new Error('Credential file is empty; values omitted');
  return pairs;
}

export async function loadCredentials(workspace) {
  let text;
  try {
    const root = await realpath(workspace);
    const directory = path.join(root, '.career-assistant', 'credentials', 'workday');
    const file = await realpath(path.join(directory, 'accounts.txt'));
    const relative = path.relative(directory, file);
    if (path.isAbsolute(relative) || relative === '..' || relative.startsWith('..' + path.sep)) throw new Error('scope');
    text = await readFile(file, 'utf8');
  } catch {
    throw new Error('Cannot read local Workday credentials; values omitted');
  }
  return parseCredentials(text);
}

// Import this only in the approved local browser runtime. Never serialize its return values.
// Selectors must come from observed controls in the current authorized browser session.
export async function fillWorkday(page, workspace, expectedOrigin, pairIndex, usernameSelector, passwordSelector) {
  try {
    const expected = new URL(expectedOrigin);
    const actual = new URL(await page.url());
    if (expected.protocol !== 'https:' || !/(^|\.)(myworkdayjobs|myworkdaysite)\.com$/.test(expected.hostname) || actual.origin !== expected.origin) {
      throw new Error('origin');
    }
    if (!Number.isInteger(pairIndex) || pairIndex < 0 || pairIndex >= 8) throw new Error('attempt');
    const pairs = await loadCredentials(workspace);
    if (!pairs[pairIndex]) throw new Error('pair');
    const username = page.locator(usernameSelector);
    const password = page.locator(passwordSelector);
    if (usernameSelector === passwordSelector || await username.count() !== 1 || await password.count() !== 1 || await password.getAttribute('type') !== 'password') throw new Error('controls');
    await username.fill(pairs[pairIndex].username);
    if (new URL(await page.url()).origin !== expected.origin) throw new Error('navigation');
    await password.fill(pairs[pairIndex].password);
    return { filled: true, values_omitted: true };
  } catch {
    // Browser exceptions can embed fill arguments; never propagate their raw messages.
    throw new Error('Safe Workday fill failed. Verify authorized origin, observed controls and local file; values omitted.');
  }
}

// Codex's supported tab API has asynchronous url() and a playwright locator surface.
// Keep the tab handle in its approved runtime; never open an arbitrary debug port.
export function hostBrowserPage(tab) {
  if (typeof tab?.url !== 'function' || typeof tab?.playwright?.locator !== 'function') {
    throw new Error('Supported host tab APIs are unavailable; use manual login. Values omitted.');
  }
  return { url: () => tab.url(), locator: selector => tab.playwright.locator(selector) };
}

// Keep this object in the approved browser runtime for the ENTIRE run, across jobs.
// A filled pair is reserved before Sign in. Only an observed rejection permits another.
export function createWorkdayLoginSession() {
  const tenants = new Map();
  function tenantKey(origin) {
    try {
      const url = new URL(origin);
      if (url.protocol !== 'https:' || !/(^|\.)(myworkdayjobs|myworkdaysite)\.com$/.test(url.hostname) || url.username || url.password) throw new Error();
      return url.origin;
    } catch { throw new Error('Invalid Workday origin; values omitted.'); }
  }
  return {
    async fill(page, workspace, origin, pairIndex, usernameSelector, passwordSelector) {
      origin = tenantKey(origin);
      let state = tenants.get(origin);
      if (!state) { state = { used: new Set(), outcome: 'new' }; tenants.set(origin, state); }
      if (!['new', 'rejected'].includes(state.outcome) || state.used.has(pairIndex) || state.used.size >= 8) {
        throw new Error('Workday login is pending, stopped or already attempted; values omitted.');
      }
      state.used.add(pairIndex);
      state.outcome = 'pending';
      try { return await fillWorkday(page, workspace, origin, pairIndex, usernameSelector, passwordSelector); }
      catch { state.outcome = 'stopped'; throw new Error('Safe Workday login stopped; values omitted.'); }
    },
    observe(origin, outcome) {
      origin = tenantKey(origin);
      const state = tenants.get(origin);
      if (!state || state.outcome !== 'pending' || !['rejected', 'success', 'captcha', '2fa', 'sso', 'locked', 'network', 'unknown'].includes(outcome)) {
        throw new Error('Invalid Workday login observation; values omitted.');
      }
      state.outcome = outcome === 'rejected' ? 'rejected' : 'stopped';
      return { attempts: state.used.size, stopped: state.outcome === 'stopped', values_omitted: true };
    }
  };
}

if (typeof process !== 'undefined' && process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    if (!process.argv[2]) throw new Error('Provide a workspace path; values omitted');
    const pairs = await loadCredentials(process.argv[2]);
    console.log(JSON.stringify({ valid: true, pairs: pairs.length, values_omitted: true }));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
