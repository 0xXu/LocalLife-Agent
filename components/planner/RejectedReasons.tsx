import React from 'react';

type RejectedReasonsProps = {
  rejected: Array<{ place_id?: string; name?: string; reason: string }>;
};

const reasonLabels: Record<string, string> = {
  closed_at_requested_time: '营业时间不匹配',
  outside_radius: '超出半径',
  age_mismatch: '年龄限制不匹配',
  capacity_mismatch: '人数容量不足',
  wait_exceeds_threshold: '等待时间过长',
};

export function RejectedReasons({ rejected }: RejectedReasonsProps) {
  if (!rejected.length) {
    return null;
  }

  return (
    <section className="rejected-reasons">
      <h3>被筛掉原因</h3>
      <ul>
        {rejected.map((item, index) => (
          <li key={`${item.place_id ?? item.name}_${index}`}>
            <strong>{item.name ?? item.place_id}</strong>
            <span>{reasonLabels[item.reason] ?? item.reason}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
