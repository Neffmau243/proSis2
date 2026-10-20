import { readFile } from 'node:fs/promises'
import { inflateSync } from 'node:zlib'
import { expect, type Page } from '@playwright/test'

/** Inspect the downloaded file, rather than substituting window.print() for a PDF export. */
export async function downloadFuaPdf(page: Page) {
  const pending = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Descargar FUA PDF', exact: true }).click()
  const download = await pending
  const path = await download.path()
  expect(path).toBeTruthy()
  const raw = (await readFile(path!)).toString('latin1')
  expect(raw.startsWith('%PDF-')).toBe(true)
  expect(raw).toMatch(/\/Count 1\b/)
  expect(raw).toContain('/Subtype /Image')
  const stream = raw.match(/stream\r?\n([\s\S]*?)\r?\nendstream/)![1]!
  const content = inflateSync(Buffer.from(stream, 'latin1')).toString('latin1')
  return { download, content }
}
