import { writeFile } from 'node:fs/promises';

const input = process.argv[2] || process.env.RF_BACKEND_ORIGIN;
let origin;
try {
  const url = new URL(input);
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/' || url.port || url.hostname === 'localhost' || url.hostname.endsWith('.internal')) throw new Error();
  origin = url.origin;
} catch {
  console.error('Supply the deployed backend HTTPS origin, without a path, credentials or query.');
  process.exit(1);
}
const response = await fetch(`${origin}/api/v1/health/ready`, { signal: AbortSignal.timeout(20000), redirect: 'error' });
if (!response.ok || (await response.json()).status !== 'ready') throw new Error('Backend is not ready; Vercel configuration was not changed.');
const config = {
  $schema: 'https://openapi.vercel.sh/vercel.json',
  framework: 'vite',
  buildCommand: 'npm run build',
  outputDirectory: 'dist',
  rewrites: [
    { source: '/api/:path*', destination: `${origin}/api/:path*` },
    { source: '/((?!api(?:/|$)).*)', destination: '/index.html' },
  ],
  headers: [
    { source: '/(.*)', headers: [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'same-origin' },
      { key: 'X-Frame-Options', value: 'DENY' },
    ] },
    { source: '/api/:path*', headers: [{ key: 'Cache-Control', value: 'no-store' }] },
  ],
};
await writeFile(new URL('../vercel.json', import.meta.url), JSON.stringify(config, null, 2) + '\n');
console.log('Prepared frontend/vercel.json with the verified backend origin. Deploy with frontend as the Vercel root.');
