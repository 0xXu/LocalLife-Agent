import React from 'react';

type ReceiptStackProps = {
  receipts: Array<Record<string, any>>;
};

export function ReceiptStack({ receipts }: ReceiptStackProps) {
  if (!receipts.length) {
    return null;
  }

  return (
    <section className="receipt-stack-panel">
      <h3>执行回执</h3>
      <div className="receipt-stack">
        {receipts.map((receipt) => (
          <div className="receipt" key={receipt.id}>
            <strong>{receipt.id}</strong>
            <span>{receipt.tool} · {receipt.status}</span>
            <p>{receipt.detail}</p>
            <code>{JSON.stringify(receipt.payload ?? {})}</code>
          </div>
        ))}
      </div>
    </section>
  );
}
