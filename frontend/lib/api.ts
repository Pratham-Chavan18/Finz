/**
 * Centralized API Client for FinReview
 * 
 * - In-memory access token storage (NEVER in localStorage/sessionStorage)
 * - Automatic Authorization header injection
 * - Credentials included for HttpOnly refresh cookie transmission
 * - Automatic single-attempt 401 token refresh & retry loop protection
 * - Global session expiration redirect
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface RefreshPayload {
  access_token: string;
  token_type?: string;
  user?: any;
}

let inMemoryAccessToken: string | null = null;
let refreshPromise: Promise<RefreshPayload | null> | null = null;
let onAuthFailureCallback: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
}

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

export function setOnAuthFailure(callback: () => void): void {
  onAuthFailureCallback = callback;
}

/**
 * Invokes the backend refresh endpoint with credentials: 'include'.
 * The backend validates the HttpOnly cookie and returns a new short-lived access JWT
 * along with user information. Deduplicates concurrent calls via shared promise.
 */
export async function refreshAccessToken(): Promise<RefreshPayload | null> {
  // Deduplicate concurrent refresh calls
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include", // Send HttpOnly refresh cookie
      });

      if (!res.ok) {
        setAccessToken(null);
        if (onAuthFailureCallback) {
          onAuthFailureCallback();
        }
        return null;
      }

      const data = await res.json();
      if (data?.access_token) {
        setAccessToken(data.access_token);
        return data as RefreshPayload;
      }

      setAccessToken(null);
      return null;
    } catch {
      setAccessToken(null);
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export interface ApiFetchOptions extends RequestInit {
  skipAuth?: boolean;
}

/**
 * Standard fetch wrapper that handles authentication headers, cookies,
 * and automatic 401 token refresh with retry.
 */
export async function apiFetch(
  endpoint: string,
  options: ApiFetchOptions = {}
): Promise<Response> {
  const url = endpoint.startsWith("http")
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  const headers = new Headers(options.headers || {});

  // Add Bearer token if present and not explicitly skipped
  if (!options.skipAuth && inMemoryAccessToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${inMemoryAccessToken}`);
  }

  const fetchOptions: RequestInit = {
    ...options,
    headers,
    credentials: "include", // Always include cookies for session support
  };

  let response = await fetch(url, fetchOptions);

  // If unauthorized and this is not an auth endpoint, attempt token refresh once
  const isAuthEndpoint =
    url.includes("/api/v1/auth/login") ||
    url.includes("/api/v1/auth/register") ||
    url.includes("/api/v1/auth/refresh") ||
    url.includes("/api/v1/auth/logout");

  if (response.status === 401 && !options.skipAuth && !isAuthEndpoint) {
    const refreshResult = await refreshAccessToken();
    if (refreshResult?.access_token) {
      // Retry original request with the new access token
      const retryHeaders = new Headers(options.headers || {});
      retryHeaders.set("Authorization", `Bearer ${refreshResult.access_token}`);
      response = await fetch(url, {
        ...options,
        headers: retryHeaders,
        credentials: "include",
      });
    } else {
      // Refresh failed completely: trigger auth failure callback and redirect if in browser
      if (onAuthFailureCallback) {
        onAuthFailureCallback();
      }
      if (
        typeof window !== "undefined" &&
        window.location.pathname !== "/" &&
        !window.location.pathname.startsWith("/login") &&
        !window.location.pathname.startsWith("/register")
      ) {
        window.location.href = "/login";
      }
    }
  }

  return response;
}
