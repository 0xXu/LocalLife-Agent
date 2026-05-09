export function redactPrivateText(text: string) {
  return text
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[redacted_email]')
    .replace(/1[3-9]\d{9}/g, '[redacted_phone]')
    .replace(/[一-龥A-Za-z]+区[一-龥A-Za-z0-9-]+(?:\d+-){1,}\d+/g, '[redacted_address]');
}
