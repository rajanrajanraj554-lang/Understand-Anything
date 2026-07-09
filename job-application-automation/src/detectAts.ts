import type { AtsPlatform } from './types.js';

export function detectAts(jobUrl: string): AtsPlatform {
  const host = new URL(jobUrl).hostname;

  if (host.includes('greenhouse.io') || host.includes('grnh.se')) {
    return 'greenhouse';
  }
  if (host.includes('lever.co')) {
    return 'lever';
  }
  if (host.includes('ashbyhq.com')) {
    return 'ashby';
  }
  return 'unknown';
}
