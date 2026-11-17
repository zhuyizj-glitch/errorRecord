import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon-192x192.png', 'icon-512x512.png'],
      manifest: {
        name: '错题集 - AI 智能错题管理系统',
        short_name: '错题集',
        description: '拍照上传，AI 自动分析，智能复习计划',
        theme_color: '#1c1c1e',
        background_color: '#000000',
        display: 'standalone',
        orientation: 'portrait',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: 'icon-192x192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any maskable',
          },
          {
            src: 'icon-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        // 刻意不缓存 /api/*：
        //
        // 原先这里有一条 urlPattern: /\/api\/.*/i 的 NetworkFirst 规则，
        // 会把 API 响应写进浏览器 Cache Storage 并保留 1 天。而错题响应是
        // 带鉴权的个人数据——多账号共用一台设备时（比如共用平板、爸妈的手机），
        // 换账号登录后仍可能从缓存里读到上一个人的错题内容。这是隐私问题，
        // 不只是性能问题，所以整条规则移除，API 一律走网络。
        //
        // 同时移除两条 Google Fonts 缓存规则：项目里并没有引用 Google Fonts
        // （字体栈是系统字体 -apple-system / PingFang SC / Microsoft YaHei），
        // 那两条属于永远不会命中的死配置。
        runtimeCaching: [],
      },
    }),
  ],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
})
