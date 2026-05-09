import React from 'react';
import { LocateFixed, Send } from 'lucide-react';

type PromptComposerProps = {
  goal: string;
};

export function PromptComposer({ goal }: PromptComposerProps) {
  return (
    <section className="prompt-composer" aria-label="当前输入">
      <div className="prompt-location"><LocateFixed size={17} /> 当前位置</div>
      <p>{goal}</p>
      <button className="icon-button" type="button" aria-label="发送">
        <Send size={17} />
      </button>
    </section>
  );
}
