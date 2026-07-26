import { createSession } from "./session";

export function login(email: string, password: string) {
  if (!email || !password) {
    throw new Error("Invalid credentials");
  }
  return createSession(email);
}
