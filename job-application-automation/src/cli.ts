import { readFile } from 'node:fs/promises';
import { applyToJob } from './apply.js';
import type { CandidateProfile } from './types.js';

/**
 * Usage:
 *   tsx src/cli.ts <jobUrl> <profile.json> [--headed] [--submit] [--out ./out]
 *
 * profile.json shape: see CandidateProfile in src/types.ts. Example in
 * profile.example.json.
 *
 * Defaults to a dry run (fills the form, screenshots it, does not click
 * submit) and to headless=false is NOT the default — headed mode must be
 * requested explicitly with --headed. See README for why.
 */
async function main() {
  const [jobUrl, profilePath, ...rest] = process.argv.slice(2);

  if (!jobUrl || !profilePath) {
    console.error(
      'Usage: tsx src/cli.ts <jobUrl> <profile.json> [--headed] [--submit] [--out ./out]',
    );
    process.exit(1);
  }

  const headed = rest.includes('--headed');
  const submit = rest.includes('--submit');
  const outIdx = rest.indexOf('--out');
  const outputDir = outIdx !== -1 ? rest[outIdx + 1] : './out';

  const profile = JSON.parse(await readFile(profilePath, 'utf-8')) as CandidateProfile;

  const result = await applyToJob({
    jobUrl,
    profile,
    dryRun: !submit,
    headed,
    outputDir,
  });

  console.log(JSON.stringify(result, null, 2));

  if (result.notes.some((n) => n.startsWith('Dry run'))) {
    console.log(
      '\nThis was a dry run. Review the screenshot and answers above, then ' +
        're-run with --submit to actually send this application.',
    );
  }
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exit(1);
});
