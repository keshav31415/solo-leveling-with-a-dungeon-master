// ============================================================
// PlayerInput — Dialogue + action input for player interactions
// ============================================================

import { useState, useEffect, useRef } from 'react';
import { CANVAS_WIDTH } from '../engine/types';

interface PlayerInputProps {
  npcName: string;
  isVisible: boolean;
  onSubmit: (message: string, action: string) => void;
  onCancel: () => void;
}

export function PlayerInput({ npcName, isVisible, onSubmit, onCancel }: PlayerInputProps) {
  const [sayText, setSayText] = useState('');
  const [doText, setDoText] = useState('');
  const sayRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isVisible && sayRef.current) {
      setTimeout(() => sayRef.current?.focus(), 50);
    }
    if (!isVisible) {
      setSayText('');
      setDoText('');
    }
  }, [isVisible]);

  useEffect(() => {
    if (!isVisible) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); onCancel(); }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isVisible, onCancel]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(sayText.trim(), doText.trim());
  };

  if (!isVisible) return null;

  const inputStyle: React.CSSProperties = {
    flex: 1,
    background: 'rgba(30, 30, 60, 0.8)',
    border: '1px solid #4a4a6a',
    borderRadius: '4px',
    padding: '6px 10px',
    fontFamily: 'monospace',
    fontSize: '13px',
    color: '#d0d0f0',
    outline: 'none',
    caretColor: '#8080ff',
  };

  const labelStyle: React.CSSProperties = {
    fontFamily: '"Press Start 2P", monospace',
    fontSize: '8px',
    color: '#5050a0',
    minWidth: '28px',
    textAlign: 'right',
    paddingTop: '2px',
  };

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 0,
        left: '50%',
        transform: 'translateX(-50%)',
        width: CANVAS_WIDTH,
        background: 'linear-gradient(180deg, rgba(10, 10, 30, 0.95) 0%, rgba(5, 5, 20, 0.98) 100%)',
        border: '2px solid #4a4a6a',
        borderBottom: 'none',
        borderRadius: '8px 8px 0 0',
        padding: '16px 20px 10px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        zIndex: 200,
        boxShadow: '0 -4px 20px rgba(0, 0, 0, 0.5)',
      }}
    >
      {/* NPC name tag */}
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
        {npcName}
      </div>

      {/* SAY row */}
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <span style={labelStyle}>SAY</span>
        <input
          ref={sayRef}
          type="text"
          value={sayText}
          onChange={(e) => setSayText(e.target.value)}
          placeholder="What do you say? (leave blank to just listen)"
          style={inputStyle}
        />
      </form>

      {/* DO row */}
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <span style={labelStyle}>DO</span>
        <input
          type="text"
          value={doText}
          onChange={(e) => setDoText(e.target.value)}
          placeholder="What do you do? (optional)"
          style={inputStyle}
        />
      </form>

      {/* Footer row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontFamily: 'monospace', fontSize: '11px', color: '#505070' }}>
          ESC to cancel
        </span>
        <button
          onClick={handleSubmit as any}
          style={{
            fontFamily: '"Press Start 2P", monospace',
            fontSize: '9px',
            padding: '6px 16px',
            background: 'linear-gradient(180deg, #2a1a4e 0%, #1a0a3e 100%)',
            color: '#8080ff',
            border: '1px solid #4a4a6a',
            borderRadius: '4px',
            cursor: 'pointer',
            letterSpacing: '1px',
          }}
        >
          SEND
        </button>
      </div>
    </div>
  );
}
