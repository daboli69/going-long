import {readFile} from 'node:fs/promises';
import {sendJson} from '../server/vercel-response.mjs';

// Read-only NFL Ensemble Lab feed (schema going-nfl-lab-feed 1.x). The lab publishes it to the `nfl-lab-feed` branch;
// this route never writes anything and never contacts the owner's PC. Freshness is judged by the client from generated_at.
export const FEED_URL = 'https://raw.githubusercontent.com/daboli69/going-long/nfl-lab-feed/nfl_lab_feed.json';

export function validFeed(body) {
  return Boolean(body && body.schema === 'going-nfl-lab-feed' && /^1\./.test(String(body.schema_version || '')) &&
    Array.isArray(body.games) && typeof body.generated_at === 'string');
}

export default async function handler(req, res, deps = {}) {
  if (req.method !== 'GET') return sendJson(req, res, {error: 'Method not allowed'}, 405);
  const fetcher = deps.fetch || fetch;
  try {
    const r = await fetcher(FEED_URL, {signal: AbortSignal.timeout(8000)});
    if (r.ok) {
      const body = await r.json();
      if (validFeed(body)) { res.setHeader('X-Feed-Source', 'published'); return sendJson(req, res, body, 200, 120); }
    }
  } catch { /* fall back to the copy packaged with the deployment, if any */ }
  try {
    const body = JSON.parse(await readFile(new URL('../data/nfl_lab.json', import.meta.url), 'utf8'));
    if (validFeed(body)) { res.setHeader('X-Feed-Source', 'packaged'); return sendJson(req, res, body, 200, 30); }
  } catch { /* no packaged copy */ }
  return sendJson(req, res, {status: 'unavailable', error: 'NFL lab feed not published yet'}, 503);
}
