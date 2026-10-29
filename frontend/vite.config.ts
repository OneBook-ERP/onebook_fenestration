import path from 'node:path'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [
    frappeui({
      frontendRoute: '/fenestration',
      buildConfig: {
        outDir: '../onebook_fenestration/public/frontend',
        indexHtmlPath: '../onebook_fenestration/www/fenestration.html',
      },
    }),
    vue(),
  ],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  test: {
    environment: 'jsdom',
    server: { deps: { inline: ['frappe-ui'] } },
  },
})
