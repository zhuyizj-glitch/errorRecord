/** 图片上传组件 */

import { useState, useRef, useEffect } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { ImagePlus } from 'lucide-react'

interface Props {
  files: File[]
  setFiles: Dispatch<SetStateAction<File[]>>
}

// 与后端 app/api/routes/upload.py 的校验规则保持一致
const MAX_FILES = 10
const MAX_FILE_BYTES = 20 * 1024 * 1024
const ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'heic', 'heif', 'webp']
const ACCEPT_ATTR = '.jpg,.jpeg,.png,.heic,.heif,.webp'

const extensionOf = (name: string) => name.split('.').pop()?.toLowerCase() ?? ''

function validate(file: File, currentCount: number): string | null {
  if (!ALLOWED_EXTENSIONS.includes(extensionOf(file.name))) {
    return `${file.name} 格式不受支持，请上传 jpg / png / heic / webp 图片`
  }
  if (file.size > MAX_FILE_BYTES) {
    return `${file.name} 超过 20MB，请压缩后重试`
  }
  if (currentCount >= MAX_FILES) {
    return `一次最多上传 ${MAX_FILES} 张图片`
  }
  return null
}

export default function ImageUploader({ files, setFiles }: Props) {
  const [previews, setPreviews] = useState<string[]>([])
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  // 当外部 files 被清空时，同步清空预览
  useEffect(() => {
    if (files.length === 0) {
      setPreviews([])
      setError('')
      // 清空 input 的 value，允许再次选择同一文件
      if (inputRef.current) {
        inputRef.current.value = ''
      }
    }
  }, [files.length])

  const handleFiles = (newFiles: FileList | null) => {
    if (!newFiles) return

    const rejected: string[] = []
    const accepted: File[] = []
    for (const file of Array.from(newFiles)) {
      const problem = validate(file, files.length + accepted.length)
      if (problem) {
        if (!rejected.includes(problem)) rejected.push(problem)
      } else {
        accepted.push(file)
      }
    }

    if (accepted.length > 0) {
      setPreviews(prev => [...prev, ...accepted.map(f => URL.createObjectURL(f))])
      setFiles(prev => [...prev, ...accepted])
    }
    setError(rejected.join('；'))

    // 允许再次选择同一个文件
    if (inputRef.current) {
      inputRef.current.value = ''
    }
  }

  const removeImage = (index: number) => {
    setPreviews(prev => prev.filter((_, i) => i !== index))
    setFiles(prev => prev.filter((_, i) => i !== index))
    setError('')
  }

  return (
    <div>
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
        style={{
          border: `2px dashed ${dragOver ? 'var(--color-primary)' : 'var(--color-border)'}`,
          borderRadius: 'var(--radius-md)',
          padding: '32px',
          textAlign: 'center',
          cursor: 'pointer',
          background: dragOver ? 'var(--color-primary-light)' : '#fafbfc',
          transition: 'all 0.2s',
        }}
      >
        <div style={{ marginBottom: '10px' }}>
          <ImagePlus size={32} color="var(--color-text-tertiary)" />
        </div>
        <p style={{ margin: '0 0 4px 0', fontSize: '15px', fontWeight: 500, color: 'var(--color-text)' }}>
          点击上传或拖拽图片到此处
        </p>
        <p style={{ margin: 0, fontSize: '13px', color: 'var(--color-text-secondary)' }}>
          支持 jpg / png / heic / webp，单张 ≤ 20MB，最多 {MAX_FILES} 张
        </p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_ATTR}
        multiple
        style={{ display: 'none' }}
        onChange={e => handleFiles(e.target.files)}
      />
      {error && (
        <p className="form-error" style={{ marginTop: '10px' }}>{error}</p>
      )}
      {previews.length > 0 && (
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginTop: '16px' }}>
          {previews.map((src, i) => (
            <div key={i} style={{ position: 'relative' }}>
              <img
                src={src}
                alt=""
                style={{
                  width: '90px',
                  height: '90px',
                  objectFit: 'cover',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)',
                }}
              />
              <button
                onClick={(e) => { e.stopPropagation(); removeImage(i) }}
                style={{
                  position: 'absolute',
                  top: '-6px',
                  right: '-6px',
                  background: 'var(--color-error)',
                  color: '#fff',
                  border: '2px solid #fff',
                  borderRadius: '50%',
                  width: '20px',
                  height: '20px',
                  cursor: 'pointer',
                  fontSize: '11px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  lineHeight: 1,
                }}
              >×</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
