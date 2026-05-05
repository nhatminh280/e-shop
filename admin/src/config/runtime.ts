const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "");

const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
const configuredSocketUrl = import.meta.env.VITE_SOCKET_URL?.trim();

export const apiBaseUrl = configuredApiBaseUrl
  ? trimTrailingSlash(configuredApiBaseUrl)
  : import.meta.env.DEV
    ? "http://localhost:8080"
    : window.location.origin;

export const socketUrl = configuredSocketUrl
  ? trimTrailingSlash(configuredSocketUrl)
  : import.meta.env.DEV
    ? "http://localhost:8080/ws"
    : `${window.location.origin}/ws`;
