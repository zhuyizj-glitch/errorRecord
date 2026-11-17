/** 真题页（v2.0）：导入 / 题库 / 针对性练习 三个标签页 */

import { useState } from 'react'
import { FileUp, Library, Target } from 'lucide-react'
import ZhentiImport from '../components/zhenti/ZhentiImport'
import ZhentiBank from '../components/zhenti/ZhentiBank'
import ZhentiPractice from '../components/zhenti/ZhentiPractice'

type Tab = 'import' | 'bank' | 'practice'

const TABS: Array<{ key: Tab; label: string; Icon: typeof FileUp }> = [
  { key: 'practice', label: '针对性练习', Icon: Target },
  { key: 'bank', label: '题库', Icon: Library },
  { key: 'import', label: '导入', Icon: FileUp },
]

export default function ZhentiPage() {
  const [tab, setTab] = useState<Tab>('practice')

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 18, borderBottom: '1px solid var(--color-border)', paddingBottom: 10 }}>
        {TABS.map(({ key, label, Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 16px', fontSize: 14, fontWeight: tab === key ? 600 : 400,
              background: tab === key ? 'var(--color-primary-light)' : 'transparent',
              color: tab === key ? 'var(--color-primary)' : 'var(--color-text-secondary)',
              border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
            }}
          >
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>
      {tab === 'import' && <ZhentiImport />}
      {tab === 'bank' && <ZhentiBank />}
      {tab === 'practice' && <ZhentiPractice />}
    </div>
  )
}
