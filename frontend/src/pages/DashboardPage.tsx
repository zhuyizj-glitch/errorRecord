/** 统计仪表盘页面 */

import { useEffect, useState } from 'react'
import { useStore } from '../store/useStore'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, Legend,
} from 'recharts'

interface OverviewStats {
  total: number
  by_subject: Record<string, number>
  by_mastery_level: { low: number; medium: number; high: number }
  by_error_type: Record<string, number>
  recent_trend: Array<{ date: string; count: number }>
  due_for_review: number
  avg_mastery_score: number
}

const COLORS = {
  primary: '#6366f1',
  success: '#10b981',
  warning: '#f59e0b',
  error: '#ef4444',
  chart: ['#6366f1', '#a855f7', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899'],
}

const MASTERY_COLORS = {
  low: '#ef4444',
  medium: '#f59e0b',
  high: '#10b981',
}

export default function DashboardPage() {
  const { currentChild } = useStore()
  const [stats, setStats] = useState<OverviewStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!currentChild) return
    setLoading(true)
    fetch(`/api/stats/overview?child=${currentChild}`)
      .then(r => r.json())
      .then(data => setStats(data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [currentChild])

  if (loading) return (
    <div style={{ textAlign: 'center', padding: '60px', color: 'var(--color-text-secondary)' }}>
      <div style={{ fontSize: '32px', marginBottom: '12px' }}>⏳</div>
      加载中...
    </div>
  )

  if (!stats || stats.total === 0) return (
    <div>
      <h2>📊 学习统计</h2>
      <div style={{
        textAlign: 'center', padding: '80px 20px',
        background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-border)',
      }}>
        <div style={{ fontSize: '64px', marginBottom: '16px' }}>📭</div>
        <p style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
          还没有错题数据
        </p>
        <p style={{ color: 'var(--color-text-secondary)', marginTop: '8px' }}>
          去上传一些错题，统计图表就会显示在这里
        </p>
      </div>
    </div>
  )

  // 准备图表数据
  const subjectData = Object.entries(stats.by_subject).map(([name, value]) => ({ name, value }))
  const masteryData = [
    { name: '薄弱', value: stats.by_mastery_level.low, color: MASTERY_COLORS.low },
    { name: '待加强', value: stats.by_mastery_level.medium, color: MASTERY_COLORS.medium },
    { name: '已掌握', value: stats.by_mastery_level.high, color: MASTERY_COLORS.high },
  ].filter(d => d.value > 0)
  const errorTypeData = Object.entries(stats.by_error_type).map(([name, value]) => ({ name, value }))
  const trendData = stats.recent_trend.map(d => ({
    date: d.date.slice(5), // MM-DD
    新增错题: d.count,
  }))

  return (
    <div>
      <h2>📊 学习统计</h2>
      <p style={{ color: 'var(--color-text-secondary)', marginBottom: '24px' }}>
        {currentChild === 'daughter' ? '👧 女儿' : '👦 儿子'}的学习数据总览
      </p>

      {/* 概览卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <StatCard title="错题总数" value={stats.total} icon="📝" color={COLORS.primary} />
        <StatCard title="平均掌握度" value={stats.avg_mastery_score} suffix="分" icon="📊" color={COLORS.success} />
        <StatCard title="待复习" value={stats.due_for_review} icon="🔄" color={COLORS.warning} />
        <StatCard
          title="已掌握率"
          value={stats.total > 0 ? Math.round(stats.by_mastery_level.high / stats.total * 100) : 0}
          suffix="%"
          icon="✅"
          color={COLORS.success}
        />
      </div>

      {/* 图表区域 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* 学科分布 */}
        <ChartCard title="📚 学科分布">
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={subjectData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={90}
                paddingAngle={2}
                dataKey="value"
                label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
              >
                {subjectData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS.chart[index % COLORS.chart.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* 掌握度分布 */}
        <ChartCard title="📊 掌握度分布">
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={masteryData}
                cx="50%"
                cy="50%"
                outerRadius={90}
                dataKey="value"
                label={({ name, value }) => `${name}: ${value}`}
              >
                {masteryData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* 错误类型分布 */}
        {errorTypeData.length > 0 && (
          <ChartCard title="🏷 错误类型分布">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={errorTypeData} layout="vertical" margin={{ left: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis type="number" stroke="#94a3b8" />
                <YAxis type="category" dataKey="name" stroke="#94a3b8" width={80} />
                <Tooltip
                  contentStyle={{ background: '#1a1a2e', border: '1px solid #333', borderRadius: '8px' }}
                />
                <Bar dataKey="value" fill={COLORS.error} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {/* 最近 7 天趋势 */}
        <ChartCard title="📈 最近 7 天趋势">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="date" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" allowDecimals={false} />
              <Tooltip
                contentStyle={{ background: '#1a1a2e', border: '1px solid #333', borderRadius: '8px' }}
              />
              <Legend />
              <Line type="monotone" dataKey="新增错题" stroke={COLORS.primary} strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  )
}

// 统计卡片组件
function StatCard({ title, value, suffix = '', icon, color }: {
  title: string
  value: number
  suffix?: string
  icon: string
  color: string
}) {
  return (
    <div style={{
      background: 'var(--color-surface)',
      borderRadius: 'var(--radius-lg)',
      padding: '20px',
      border: '1px solid var(--color-border)',
      boxShadow: 'var(--shadow-sm)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '8px' }}>
            {title}
          </div>
          <div style={{ fontSize: '28px', fontWeight: 800, color }}>
            {value}<span style={{ fontSize: '14px', fontWeight: 400 }}>{suffix}</span>
          </div>
        </div>
        <div style={{ fontSize: '28px' }}>{icon}</div>
      </div>
    </div>
  )
}

// 图表卡片组件
function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--color-surface)',
      borderRadius: 'var(--radius-lg)',
      padding: '20px',
      border: '1px solid var(--color-border)',
      boxShadow: 'var(--shadow-sm)',
    }}>
      <h3 style={{ margin: '0 0 16px 0', fontSize: '15px', fontWeight: 600 }}>{title}</h3>
      {children}
    </div>
  )
}
