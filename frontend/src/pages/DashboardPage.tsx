/** 统计仪表盘页面 */

import { useEffect, useState } from 'react'
import {
  BarChart3,
  CircleCheck,
  FileText,
  LoaderCircle,
  PieChart as PieChartIcon,
  RefreshCw,
  Tag,
  Target,
  TrendingUp,
  Inbox,
  type LucideIcon,
} from 'lucide-react'
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
  /** 只对「已摸底」（重做过至少一次）的题求平均 —— 新题的 0 分不算进去 */
  avg_mastery_score: number
  /** 已摸底 / 从未重做过的题数 */
  attempted_total?: number
  untested_total?: number
}

/** 薄弱知识点接口的一行 */
interface WeakPointRow {
  knowledge_point: string
  /** null 表示该知识点下还没有任何题被重做过（「未知」而非「薄弱」） */
  avg_score: number | null
  question_count: number
  rated_count: number
  untested_count: number
  wrong_total: number
  last_rated_at?: string
}

interface WeakPoints {
  /** 已摸底的知识点，按均分升序（最薄弱在前） */
  weak_points: WeakPointRow[]
  /** 还没摸过底的知识点，不参与「最薄弱」排名 */
  untested_points: WeakPointRow[]
  rated_total: number
  untested_total: number
}

const COLORS = {
  primary: '#007aff',
  success: '#34c759',
  warning: '#ff9500',
  error: '#ff3b30',
  // 图表色板：取自苹果系统色系，彼此和谐且有足够区分度
  chart: ['#007aff', '#5e5ce6', '#34c759', '#ff9500', '#ff3b30', '#30b0c7', '#af52de', '#ff2d55'],
}

const MASTERY_COLORS = {
  low: '#ff3b30',
  medium: '#ff9500',
  high: '#34c759',
}

/** 图表内部统一使用的浅色主题样式 */
const CHART_GRID = 'rgba(84, 84, 88, 0.5)'
const CHART_AXIS = 'rgba(235, 235, 245, 0.45)'
const TOOLTIP_STYLE: React.CSSProperties = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: '10px',
  boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
  fontSize: '13px',
}

export default function DashboardPage() {
  const { currentChild } = useStore()
  const [stats, setStats] = useState<OverviewStats | null>(null)
  const [weak, setWeak] = useState<WeakPoints | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!currentChild) return
    setLoading(true)
    // 两个接口并行请求，避免首屏串行等待
    Promise.all([
      fetch(`/api/stats/overview?child_id=${currentChild}`).then(r => r.json()),
      fetch(`/api/stats/weak-points?child_id=${currentChild}&limit=10`).then(r => r.json()),
    ])
      .then(([overview, weakPoints]) => {
        setStats(overview)
        setWeak(weakPoints)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [currentChild])

  if (loading) return (
    <div style={{ textAlign: 'center', padding: '60px', color: 'var(--color-text-secondary)' }}>
      <div style={{ marginBottom: '12px' }}>
        <LoaderCircle size={32} color="var(--color-text-tertiary)" />
      </div>
      加载中...
    </div>
  )

  if (!stats || stats.total === 0) return (
    <div>
      <h2 style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <BarChart3 size={20} />
        学习统计
      </h2>
      <div style={{
        textAlign: 'center', padding: '80px 20px',
        background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-border)',
      }}>
        <div style={{ marginBottom: '16px' }}>
          <Inbox size={56} strokeWidth={1.2} color="var(--color-text-tertiary)" />
        </div>
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
      <h2 style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <BarChart3 size={20} />
        学习统计
      </h2>
      <p style={{ color: 'var(--color-text-secondary)', marginBottom: '24px' }}>
        {useStore.getState().children.find(child => child.id === currentChild)?.name}的学习数据总览
      </p>

      {/* 概览卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <StatCard title="错题总数" value={stats.total} Icon={FileText} color={COLORS.primary} />
        <StatCard title="平均掌握度" value={stats.avg_mastery_score} suffix="分" Icon={Target} color={COLORS.success} />
        <StatCard title="待复习" value={stats.due_for_review} Icon={RefreshCw} color={COLORS.warning} />
        <StatCard
          title="已掌握率"
          value={stats.total > 0 ? Math.round(stats.by_mastery_level.high / stats.total * 100) : 0}
          suffix="%"
          Icon={CircleCheck}
          color={COLORS.success}
        />
      </div>

      {/* 图表区域 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* 学科分布 */}
        <ChartCard title="学科分布" Icon={PieChartIcon}>
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
        <ChartCard title="掌握度分布" Icon={BarChart3}>
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
          <ChartCard title="错误类型分布" Icon={Tag}>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={errorTypeData} layout="vertical" margin={{ left: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis type="number" stroke={CHART_AXIS} />
                <YAxis type="category" dataKey="name" stroke={CHART_AXIS} width={80} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="value" fill={COLORS.error} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {/* 最近 7 天趋势 */}
        <ChartCard title="最近 7 天趋势" Icon={TrendingUp}>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
              <XAxis dataKey="date" stroke={CHART_AXIS} />
              <YAxis stroke={CHART_AXIS} allowDecimals={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend />
              <Line type="monotone" dataKey="新增错题" stroke={COLORS.primary} strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* 薄弱知识点 —— 手册承诺的第 6 项统计，此前后端有接口但前端一直没做 */}
        {weak && (weak.rated_total > 0 || weak.untested_total > 0) && (
          <div style={{ gridColumn: '1 / -1' }}>
            <ChartCard title="薄弱知识点（按已摸底题平均）" Icon={Target}>
              {weak.weak_points.length > 0 ? (
                <ResponsiveContainer width="100%" height={Math.max(240, weak.weak_points.length * 36)}>
                  <BarChart data={weak.weak_points} layout="vertical" margin={{ left: 8, right: 52 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} horizontal={false} />
                    <XAxis type="number" domain={[0, 100]} stroke={CHART_AXIS} />
                    <YAxis
                      type="category"
                      dataKey="knowledge_point"
                      stroke={CHART_AXIS}
                      width={132}
                      tick={{ fontSize: 12 }}
                    />
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                    <Bar
                      dataKey="avg_score"
                      radius={[0, 4, 4, 0]}
                      label={{ position: 'right', fontSize: 12, fill: CHART_AXIS }}
                    >
                      {weak.weak_points.map(row => (
                        <Cell
                          key={row.knowledge_point}
                          fill={(row.avg_score ?? 0) < 50 ? MASTERY_COLORS.low
                            : (row.avg_score ?? 0) < 80 ? MASTERY_COLORS.medium
                            : MASTERY_COLORS.high}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p style={{ color: 'var(--color-text-secondary)', fontSize: 14, margin: 0 }}>
                  还没有重做过的题，暂时判断不出哪个知识点薄弱。
                </p>
              )}

              {/* 未摸底的知识点单独说明，不混进排名 ——
                  「还没练过」和「练了不会」是两回事，用 0 分表示前者会误导 */}
              {weak.untested_points.length > 0 && (
                <p style={{
                  fontSize: 13, color: 'var(--color-text-secondary)',
                  marginTop: 14, marginBottom: 0, lineHeight: 1.7,
                }}>
                  另有{' '}
                  <strong style={{ color: 'var(--color-text)' }}>{weak.untested_total}</strong>{' '}
                  个知识点只有新题、还没重做过，暂不参与排名：
                  {weak.untested_points.slice(0, 8).map(p => `${p.knowledge_point}(${p.untested_count})`).join('、')}
                  {weak.untested_total > 8 ? ' 等' : ''}
                </p>
              )}
            </ChartCard>
          </div>
        )}
      </div>
    </div>
  )
}

// 统计卡片组件
function StatCard({ title, value, suffix = '', Icon, color }: {
  title: string
  value: number
  suffix?: string
  Icon: LucideIcon
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
        <div style={{
          width: 36,
          height: 36,
          borderRadius: 10,
          background: color + '18',
          display: 'grid',
          placeItems: 'center',
          flexShrink: 0,
        }}>
          <Icon size={18} color={color} />
        </div>
      </div>
    </div>
  )
}

// 图表卡片组件
function ChartCard({ title, Icon, children }: { title: string; Icon: LucideIcon; children: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--color-surface)',
      borderRadius: 'var(--radius-lg)',
      padding: '20px',
      border: '1px solid var(--color-border)',
      boxShadow: 'var(--shadow-sm)',
    }}>
      <h3 style={{
        margin: '0 0 16px 0', fontSize: '15px', fontWeight: 600,
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <Icon size={16} color="var(--color-text-secondary)" />
        {title}
      </h3>
      {children}
    </div>
  )
}
