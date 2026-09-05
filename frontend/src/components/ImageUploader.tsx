/** 图片上传组件 */

import { useState, useRef, useEffect } from 'react'
import type { Dispatch, SetStateAction } from 'react'

interface Props {
  files: File[]
  setFiles: Dispatch<SetStateAction<File[]>>
}

export default function ImageUploader({ files, setFiles }: Props) {
  const [previews, setPreviews] = useState<string[]>([])
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  // 当外部 files 被清空时，同步清空预览
  useEffect(() => {
    if (files.length === 0) {
      setPreviews([])
      // 清空 input 的 value，允许再次选择同一文件
      if (inputRef.current) {
        inputRef.current.value = ''
      }
    }
  }, [files.length])

  const handleFiles = (newFiles: FileList | null) => {
    if (!newFiles) return
    const arr = Array.from(newFiles)
    const newPreviews = arr.map(f => URL.createObjectURL(f))
    setPreviews(prev => [...prev, ...newPreviews])
    setFiles(prev => [...prev, ...arr])
  }

  const removeImage = (index: number) => {
    setPreviews(prev => prev.filter((_, i) => i !== index))
    setFiles(prev => prev.filter((_, i) => i !== index))
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
        <div style={{ fontSize: '36px', marginBottom: '8px' }}>📷</div>
        <p style={{ margin: '0 0 4px 0', fontSize: '15px', fontWeight: 500, color: 'var(--color-text)' }}>
          点击上传或拖拽图片到此处
        </p>
        <p style={{ margin: 0, fontSize: '13px', color: 'var(--color-text-secondary)' }}>
          支持 jpg / png / heic / webp，单张 ≤ 20MB，最多 10 张
        </p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        style={{ display: 'none' }}
        onChange={e => handleFiles(e.target.files)}
      />
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
