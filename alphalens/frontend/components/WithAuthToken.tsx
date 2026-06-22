import { useAuth } from "@clerk/nextjs";
import { useEffect, type ReactNode } from "react";
import { getMe } from "../lib/api";
import { HAS_CLERK } from "../lib/config";

export type GetTokenFn = () => Promise<string | null>;

interface WithAuthTokenProps {
  children: (getToken: GetTokenFn) => ReactNode;
}

function ClerkTokenInner({ children }: WithAuthTokenProps) {
  const { getToken, isSignedIn } = useAuth();

  useEffect(() => {
    if (!isSignedIn) return;
    getToken()
      .then((token) => (token ? getMe(token) : null))
      .catch(() => undefined);
  }, [isSignedIn, getToken]);

  return <>{children(getToken)}</>;
}

/** Supplies Clerk getToken when auth is enabled; otherwise a no-op token getter. */
export default function WithAuthToken({ children }: WithAuthTokenProps) {
  if (!HAS_CLERK) {
    return <>{children(async () => null)}</>;
  }
  return <ClerkTokenInner>{children}</ClerkTokenInner>;
}
