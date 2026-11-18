import { useMutation } from '@tanstack/react-query'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { aiApi } from '../api'
import type { AiToolCall, ChatMessage } from '../api/types'
import { ErrorBox, PageHeader } from '../components/ui'
import { describeToolCall } from '../lib/assistant'

interface Turn extends ChatMessage {
  toolCalls?: AiToolCall[]
}

const SUGGESTIONS = [
  'Which active listings are under $1,000,000?',
  'Which buyers could afford the most expensive active listing?',
  'Summarise the deals in negotiation and what is holding them up.',
  'Find buyers who mentioned wanting a pool.',
]

export default function AssistantPage() {
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  const ask = useMutation({
    mutationFn: (history: ChatMessage[]) => aiApi.ask(history),
    onSuccess: (res) => setTurns((t) => [...t, { role: 'assistant', content: res.answer, toolCalls: res.tool_calls }]),
  })

  useEffect(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), [turns, ask.isPending])

  const send = (question: string) => {
    const q = question.trim()
    if (!q || ask.isPending) return
    const next: Turn[] = [...turns, { role: 'user', content: q }]
    setTurns(next)
    setInput('')
    ask.mutate(next.map(({ role, content }) => ({ role, content })))
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    send(input)
  }

  return (
    <>
      <PageHeader
        title="Ask Rex"
        action={
          turns.length > 0 && (
            <button className="btn" onClick={() => setTurns([])} disabled={ask.isPending}>
              New conversation
            </button>
          )
        }
      />

      <div className="card chat">
        {turns.length === 0 && (
          <div className="chat-empty">
            <p className="muted">
              Ask about your clients, listings and pipeline in plain English. Rex looks up the CRM to answer and can't change
              any data.
            </p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="btn suggestion" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t, i) => (
          <div key={i} className={`bubble ${t.role}`}>
            <div className="bubble-text">{t.content}</div>
            {t.toolCalls && t.toolCalls.length > 0 && (
              <details className="tool-trace">
                <summary className="muted small">Looked up {t.toolCalls.length} time{t.toolCalls.length > 1 ? 's' : ''}</summary>
                <ul>
                  {t.toolCalls.map((c, j) => (
                    <li key={j} className={c.error ? 'error' : undefined}>
                      {describeToolCall(c)}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        ))}

        {ask.isPending && <div className="bubble assistant muted">Looking that up...</div>}
        <ErrorBox error={ask.error} />
        <div ref={endRef} />
      </div>

      <form className="chat-input" onSubmit={submit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. Which buyers can afford the Burwood house?"
          maxLength={4000}
          autoFocus
        />
        <button className="btn btn-primary" disabled={ask.isPending || !input.trim()}>
          Ask
        </button>
      </form>
    </>
  )
}
