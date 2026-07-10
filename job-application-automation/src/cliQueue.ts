import { readFile } from 'node:fs/promises';
import { runQueue } from './queue.js';
import type { CandidateProfile } from './types.js';

/**
 * Usage:
 *   tsx src/cliQueue.ts <urls.txt> <profile.json> [--out ./out] [--captcha-timeout 300]
 *
 * urls.txt: one job URL per line (blank lines and lines starting with # are
 * ignored).
 *
 * Always runs headed — queue mode's whole point is a human reviewing and
 * clearing CAPTCHAs in one sitting, which requires a visible browser.
 */
async function main() {
  const [urlsPath, profilePath, ...rest] = process.argv.slice(2);

  if (!urlsPath || !profilePath) {
    console.error(
      'Usage: tsx src/cliQueue.ts <urls.txt> <profile.json> [--out ./out] [--captcha-timeout 300]',
    );
    process.exit(1);
  }

  const outIdx = rest.indexOf('--out');
  const outputDir = outIdx !== -1 ? rest[outIdx + 1] : './out';

  const timeoutIdx = rest.indexOf('--captcha-timeout');
  const captchaTimeoutSeconds =
    timeoutIdx !== -1 ? Number(rest[timeoutIdx + 1]) : undefined;

  const jobUrls = (await readFile(urlsPath, 'utf-8'))
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'));

  const profile = JSON.parse(await readFile(profilePath, 'utf-8')) as CandidateProfile;

  const results = await runQueue({
    jobUrls,
    profile,
    outputDir,
    captchaTimeoutSeconds,
  });

  console.log('\n=== Summary ===');
  for (const r of results) {
    console.log(`${r.status.padEnd(16)} ${r.jobUrl}${r.error ? `  (${r.error})` : ''}`);
  }
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exit(1);
});
