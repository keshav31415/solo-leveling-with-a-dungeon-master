// ============================================================
// DialogueBox — Retro RPG text box for AI narrative
// ============================================================

import { useState, useEffect, useRef } from 'react';
import { CANVAS_WIDTH } from '../engine/types';

interface DialogueBoxProps {
  text: string;
  speaker?: string;
  isVisible: boolean;
  onDismiss: () => void;
}

export function DialogueBox({ text, speaker, isVisible, onDismiss }: DialogueBoxProps) {
  const [displayedText, setDisplayedText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const fullTextRef = useRef(text);
  const charIndexRef = useRef(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Typewriter effect
  useEffect(() => {
    if (!isVisible || !text) return;

    fullTextRef.current = text;
    charIndexRef.current = 0;
    setDisplayedText('');
    setIsTyping(true);

    intervalRef.current = setInterval(() => {
      charIndexRef.current++;
      setDisplayedText(fullTextRef.current.slice(0, charIndexRef.current));

      if (charIndexRef.current >= fullTextRef.current.length) {
        setIsTyping(false);
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    }, 30); // 30ms per character

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [text, isVisible]);

  // Handle click/key to skip or dismiss
  const handleClick = () => {
    if (isTyping) {
      // Skip to full text
      if (intervalRef.current) clearInterval(intervalRef.current);
      setDisplayedText(fullTextRef.current);
      setIsTyping(false);
    } else {
      // Dismiss
      onDismiss();
    }
  };

  // Also listen for Space/Enter to advance
  useEffect(() => {
    if (!isVisible) return;

    const handleKey = (e: KeyboardEvent) => {
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        handleClick();
      }
    };

    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isVisible, isTyping]);

  if (!isVisible) return null;

  return (
    <div
      onClick={handleClick}
      style={{
        position: 'fixed',
        bottom: 0,
        left: '50%',
        transform: 'translateX(-50%)',
        width: CANVAS_WIDTH,
        height: '140px',
        background: 'linear-gradient(180deg, rgba(10, 10, 30, 0.95) 0%, rgba(5, 5, 20, 0.98) 100%)',
        border: '2px solid #4a4a6a',
        borderBottom: 'none',
        borderRadius: '8px 8px 0 0',
        padding: '16px 20px',
        display: 'flex',
        flexDirection: 'column',
        cursor: 'pointer',
        zIndex: 150,
        boxShadow: '0 -4px 20px rgba(0, 0, 0, 0.5)',
      }}
    >
      {/* Speaker name */}
      {speaker && (
        <div
          style={{
            position: 'absolute',
            top: '-14px',
            left: '16px',
            background: '#1a1a3e',
            border: '2px solid #4a4a6a',
            borderRadius: '4px',
            padding: '2px 12px',
            fontFamily: '"Press Start 2P", monospace',
            fontSize: '10px',
            color: '#e0e0ff',
            letterSpacing: '1px',
          }}
        >
          {speaker}
        </div>
      )}

      {/* Narrative text */}
      <div
        style={{
          fontFamily: 'monospace',
          fontSize: '14px',
          lineHeight: '1.6',
          color: '#d0d0f0',
          flex: 1,
          overflow: 'hidden',
        }}
      >
        {displayedText}
        {isTyping && (
          <span style={{ animation: 'blink 0.5s infinite', color: '#8080ff' }}>▌</span>
        )}
      </div>

      {/* Continue indicator */}
      {!isTyping && (
        <div
          style={{
            textAlign: 'right',
            fontFamily: 'monospace',
            fontSize: '11px',
            color: '#6060a0',
            animation: 'blink 1s infinite',
          }}
        >
          ▼ Press Space
        </div>
      )}
    </div>
  );
}
