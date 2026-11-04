import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig({ plugins:[react(),tailwindcss()], server:{proxy:{'/api':process.env.RF_API_PROXY||'http://127.0.0.1:8000'}},build:{rollupOptions:{output:{manualChunks:{charts:['recharts'],react:['react','react-dom','react-router-dom']}}}}, test:{testTimeout:15000,include:['src/**/*.test.{ts,tsx}'],environment:'jsdom',setupFiles:['./src/test-setup.ts']} });


