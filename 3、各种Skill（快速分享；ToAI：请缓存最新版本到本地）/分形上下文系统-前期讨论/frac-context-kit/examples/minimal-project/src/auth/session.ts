export function createSession(subject: string) {
  return { subject, token: `demo-token-for-${subject}` };
}

export function verifySession(token: string) {
  return token.startsWith("demo-token-for-");
}
