import CodeMirror from '@uiw/react-codemirror'
import { StreamLanguage } from '@codemirror/language'
import { stex } from '@codemirror/legacy-modes/mode/stex'
import { EditorView } from '@codemirror/view'
import { useEffect, useState } from 'react'

const lang = StreamLanguage.define(stex)

export function LatexEditor({ value, onChange, minHeight = '160px', placeholder }: { value: string; onChange: (v: string) => void; minHeight?: string; placeholder?: string }) {
  const [dark, setDark] = useState(document.documentElement.classList.contains('dark'))
  useEffect(() => {
    const obs = new MutationObserver(() => setDark(document.documentElement.classList.contains('dark')))
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])
  return (
    <div className="overflow-hidden rounded-lg border">
      <CodeMirror value={value} onChange={onChange} theme={dark ? 'dark' : 'light'} placeholder={placeholder}
        extensions={[lang, EditorView.lineWrapping]} minHeight={minHeight}
        basicSetup={{ foldGutter: false, highlightActiveLine: false }} />
    </div>
  )
}
