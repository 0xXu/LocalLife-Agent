'use client';

import React, { useRef, useState } from 'react';
import { Mic, SendHorizontal, Square } from 'lucide-react';

type GoalInputProps = {
  onSubmit: (goal: string) => void;
  disabled?: boolean;
};

export function GoalInput({ onSubmit, disabled }: GoalInputProps) {
  const [value, setValue] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState('');
  const recognitionRef = useRef<any>(null);

  function handleSubmit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue('');
  }

  function handleKeyDown(event: React.KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  }

  function toggleVoice() {
    if (isListening) {
      recognitionRef.current?.stop();
      return;
    }
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceStatus('浏览器不支持语音输入');
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = 'zh-CN';
    recognition.interimResults = false;
    recognition.onstart = () => { setIsListening(true); setVoiceStatus(''); };
    recognition.onresult = (event: any) => {
      const transcript = Array.from(event.results).map((r: any) => r[0]?.transcript ?? '').join('').trim();
      if (transcript) setValue(transcript);
    };
    recognition.onerror = () => { setVoiceStatus('语音识别失败'); };
    recognition.onend = () => { setIsListening(false); };
    recognition.start();
    recognitionRef.current = recognition;
  }

  return (
    <div className="goal-input-wrapper">
      <div className="goal-input-container">
        <textarea
          className="goal-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="描述你的周末安排..."
          disabled={disabled}
          rows={1}
          aria-label="输入出行需求"
        />
        <div className="goal-input-actions">
          <button
            className={`goal-input-voice${isListening ? ' listening' : ''}`}
            type="button"
            onClick={toggleVoice}
            disabled={disabled}
            aria-label={isListening ? '停止录音' : '语音输入'}
          >
            {isListening ? <Square size={18} /> : <Mic size={18} />}
          </button>
          <button
            className="goal-input-send"
            type="button"
            onClick={handleSubmit}
            disabled={disabled || !value.trim()}
            aria-label="发送"
          >
            <SendHorizontal size={18} />
          </button>
        </div>
      </div>
      {voiceStatus && <div className="goal-input-status" role="status">{voiceStatus}</div>}
    </div>
  );
}
