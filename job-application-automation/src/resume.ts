import { readFile } from 'node:fs/promises';
import pdfParse from 'pdf-parse';

export async function extractResumeText(resumePath: string): Promise<string> {
  const buffer = await readFile(resumePath);

  if (resumePath.toLowerCase().endsWith('.pdf')) {
    const parsed = await pdfParse(buffer);
    return parsed.text;
  }

  return buffer.toString('utf-8');
}
