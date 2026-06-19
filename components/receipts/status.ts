export function isSuccessfulReceiptStatus(status: string) {
  return ['success', 'ok', 'succeeded', 'confirmed', 'completed', 'sent'].includes(status);
}
