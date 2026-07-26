import { login } from "./auth/login";

export function main() {
  return login("demo@example.com", "password");
}
