/** 设置页面 */

import { useEffect, useState } from 'react'
import { fetchSettings, saveSettings, testConnection } from '../api/client'

export default function SettingsPage() {
  const [apiBase, setApiBase] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState({ type: '', text: '' })

  useEffect(() => {
    fetchSettings()
      .then(res => {
        const llm = res.llm || {}
        setApiBase(llm.api_base || '')
        // API Key 从服务端获取时已脱敏，不清空
        setApiKey(llm.api_key || '')
        setModel(llm.model || '')
      })
      .catch(console.error)
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await saveSettings({
        llm: { api_base: apiBase, api_key: apiKey, model, timeout: 60 },
      })
      setMessage({ type: 'success', text: '✅ 设置已保存' })
      setTimeout(() => setMessage({ type: '', text: '' }), 3000)
    } catch {
      setMessage({ type: 'error', text: '❌ 保存失败' })
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setMessage({ type: '', text: '' })
    try {
      const res = await testConnection({ api_base: apiBase, api_key: apiKey, model })
      setMessage({ type: 'success', text: '✅ 连接成功: ' + (res.data?.reply || 'ok') })
    } catch (e: any) {
      setMessage({ type: 'error', text: '❌ 连接失败: ' + (e.response?.data?.detail || e.message) })
    } finally {
      setTesting(false)
    }
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '10px 14px',
    marginTop: '6px',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--color-border)',
    fontSize: '14px',
    transition: 'border-color 0.2s',
  }

  return (
    <div>
      <h2>⚙️ AI 模型设置</h2>
      <p style={{ color: 'var(--color-text-secondary)', marginBottom: '24px', fontSize: '14px' }}>
        配置多模态 LLM 接口（兼容 OpenAI API 格式）
      </p>

      <div style={{
        background: 'var(--color-surface)',
        borderRadius: 'var(--radius-lg)',
        padding: '24px',
        boxShadow: 'var(--shadow-sm)',
        border: '1px solid var(--color-border)',
        maxWidth: '560px',
      }}>
        <div style={{ marginBottom: '20px' }}>
          <label style={{ fontSize: '14px', fontWeight: 500 }}>API 地址</label>
          <input
            value={apiBase}
            onChange={e => setApiBase(e.target.value)}
            placeholder="https://api.openai.com/v1"
            style={inputStyle}
          />
        </div>

        <div style={{ marginBottom: '20px' }}>
          <label style={{ fontSize: '14px', fontWeight: 500 }}>API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            placeholder="sk-..."
            style={inputStyle}
          />
        </div>

        <div style={{ marginBottom: '24px' }}>
          <label style={{ fontSize: '14px', fontWeight: 500 }}>模型名称</label>
          <input
            value={model}
            onChange={e => setModel(e.target.value)}
            placeholder="gpt-4o"
            style={inputStyle}
          />
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              padding: '10px 28px',
              background: 'var(--color-primary)',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius-md)',
              fontSize: '14px',
              fontWeight: 600,
            }}
          >
            {saving ? '保存中...' : '💾 保存设置'}
          </button>
          <button
            onClick={handleTest}
            disabled={testing || !apiBase || !apiKey}
            style={{
              padding: '10px 24px',
              background: 'transparent',
              color: 'var(--color-primary)',
              border: '1px solid var(--color-primary)',
              borderRadius: 'var(--radius-md)',
              fontSize: '14px',
              fontWeight: 500,
            }}
          >
            {testing ? '⏳ 测试中...' : '🔌 测试连接'}
          </button>
        </div>

        {message.text && (
          <div style={{
            marginTop: '16px',
            padding: '10px 16px',
            borderRadius: 'var(--radius-sm)',
            fontSize: '14px',
            background: message.type === 'success' ? '#e8f5e9' : '#fff3f3',
            color: message.type === 'success' ? 'var(--color-success)' : 'var(--color-error)',
            border: `1px solid ${message.type === 'success' ? '#a5d6a7' : '#ffcdd2'}`,
          }}>
            {message.text}
          </div>
        )}
      </div>
    </div>
  )
}
