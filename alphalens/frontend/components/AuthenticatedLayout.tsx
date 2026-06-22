import { Protect, useUser } from "@clerk/nextjs";
import type { ReactNode } from "react";
import { HAS_CLERK } from "../lib/config";
import Layout from "./Layout";

interface AuthenticatedLayoutProps {
  children: ReactNode;
}

function SignedInShell({ children }: { children: ReactNode }) {
  const { user } = useUser();

  return (
    <Layout>
      <div className="auth-bar">
        <div className="auth-bar-user">
          <span className="muted">
            Signed in as{" "}
            {user?.firstName ||
              user?.primaryEmailAddress?.emailAddress ||
              "user"}
          </span>
        </div>
      </div>
      {children}
    </Layout>
  );
}

export default function AuthenticatedLayout({ children }: AuthenticatedLayoutProps) {
  if (!HAS_CLERK) {
    return <Layout>{children}</Layout>;
  }

  return (
    <Protect
      fallback={
        <Layout>
          <p className="page-lead">Redirecting to sign in…</p>
        </Layout>
      }
    >
      <SignedInShell>{children}</SignedInShell>
    </Protect>
  );
}
