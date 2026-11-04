import { defineConfig, devices } from '@playwright/test';
import { fileURLToPath } from 'node:url';
const baseURL=process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5175';
const python=fileURLToPath(new URL(process.platform==='win32'?'../backend/.venv/Scripts/python.exe':'../backend/.venv/bin/python',import.meta.url));
export default defineConfig({testDir:'./tests/e2e',workers:1,timeout:60000,expect:{timeout:10000},use:{baseURL,actionTimeout:15000},webServer:process.env.RF_E2E_EXTERNAL?undefined:process.env.PLAYWRIGHT_BASE_URL?{command:'node node_modules/vite/bin/vite.js --host 127.0.0.1',url:baseURL,reuseExistingServer:!process.env.CI}:[{command:`"${python}" -m app.e2e_server`,url:'http://127.0.0.1:8001/api/v1/health/ready',timeout:60000},{command:'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5175 --strictPort',url:baseURL,env:{RF_API_PROXY:'http://127.0.0.1:8001'}}],projects:[{name:'desktop',use:{...devices['Desktop Chrome']}},{name:'mobile',use:{...devices['iPhone 13']}}]});



