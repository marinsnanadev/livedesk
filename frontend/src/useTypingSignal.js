import { useRef, useCallback } from 'react'

const STOP_TYPING_DELAY_MS = 1500

/**
 * Emits "typing" on the first keystroke and "stopped typing" after a
 * quiet period — without this debounce you'd fire a socket message on
 * every single keystroke, which is noisy and unnecessary.
 */
export function useTypingSignal(send) {
  const isTypingRef = useRef(false)
  const timeoutRef = useRef(null)

  const notifyTyping = useCallback(() => {
    if (!isTypingRef.current) {
      isTypingRef.current = true
      send({ type: 'typing', is_typing: true })
    }
    clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      isTypingRef.current = false
      send({ type: 'typing', is_typing: false })
    }, STOP_TYPING_DELAY_MS)
  }, [send])

  const notifyStopped = useCallback(() => {
    clearTimeout(timeoutRef.current)
    if (isTypingRef.current) {
      isTypingRef.current = false
      send({ type: 'typing', is_typing: false })
    }
  }, [send])

  return { notifyTyping, notifyStopped }
}
